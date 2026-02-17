# Feature: Migrate from FatSecret API to Open Food Facts Local Database

## Summary

Replace FatSecret API integration with Open Food Facts (OFF) local database in Supabase. Improve ingredient matching from 50% to 90%+, eliminate API rate limits, and achieve 7/7 days within ±5% macro tolerance.

**Problem**: FatSecret API has 50% ingredient miss rate (greek yogurt, quinoa, almonds, lettuce missing), causing 0/7 days to hit macro targets.

**Solution**: Import 200K French products from OFF JSONL into Supabase, use PostgreSQL full-text search instead of API calls.

**Impact**:
- Match rate: 50% → 90%+
- Latency: 100ms → <10ms per ingredient
- Macro accuracy: 0/7 days → 7/7 days within ±5%
- Reliability: No API failures, no rate limits

---

## Context

### Files to Read Before Starting

**Core Files to Refactor:**
- `4_Pydantic_AI_Agent/nutrition/fatsecret_client.py` - DELETE OAuth manager, REFACTOR search to SQL
- `4_Pydantic_AI_Agent/nutrition/meal_plan_optimizer.py` (line 6, 79, 142) - Update imports and signatures
- `4_Pydantic_AI_Agent/tools.py` (lines 59-73, 860) - Remove FatSecret manager

**Database Schema:**
- `4_Pydantic_AI_Agent/sql/create_ingredient_mapping_table.sql` - Cache table pattern to follow

**Data Source:**
- `4_Pydantic_AI_Agent/nutrition/openfood/openfoodfacts-products.jsonl.gz` - Already downloaded
- `4_Pydantic_AI_Agent/nutrition/openfood/format data extraction.txt` - Field documentation

**Testing Patterns:**
- `4_Pydantic_AI_Agent/tests/test_validators.py` - pytest patterns
- `4_Pydantic_AI_Agent/test_full_meal_plan.py` - Integration test (reuse for validation)

### Key Patterns to Preserve

**Cache-First Strategy** (from fatsecret_client.py:86-100):
```python
# 1. Check cache
cached = supabase.table("ingredient_mapping").select("*").eq("ingredient_name_normalized", normalized).execute()
if cached.data:
    return cached.data[0]

# 2. Query database if miss
result = await search_food_local(query, supabase)

# 3. Store in cache
supabase.table("ingredient_mapping").insert({...}).execute()
```

**Fuzzy Matching** (from fatsecret_client.py:238-254):
```python
from difflib import SequenceMatcher
similarity = SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
# Boost exact word matches
if word in product_name.split():
    similarity += 0.2
```

**Async Error Handling**:
```python
try:
    result = await operation()
    logger.info("Success", extra={"count": len(result)})
    return result
except Exception as e:
    logger.error(f"Failed: {e}", exc_info=True)
    return []  # Graceful degradation
```

---

## Implementation Plan

### Phase 1: Database Setup

**1.1 Create openfoodfacts_products table**
- Use `mcp__supabase__apply_migration`
- Schema:
  ```sql
  CREATE TABLE openfoodfacts_products (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      code TEXT UNIQUE NOT NULL,
      product_name TEXT NOT NULL,
      product_name_fr TEXT,
      countries_tags TEXT[],
      calories_per_100g NUMERIC(7,2) NOT NULL,
      protein_g_per_100g NUMERIC(6,2) NOT NULL,
      carbs_g_per_100g NUMERIC(6,2) NOT NULL,
      fat_g_per_100g NUMERIC(6,2) NOT NULL,
      search_vector tsvector,
      created_at TIMESTAMPTZ DEFAULT NOW()
  );

  CREATE INDEX idx_off_search ON openfoodfacts_products USING GIN(search_vector);
  CREATE INDEX idx_off_countries ON openfoodfacts_products USING GIN(countries_tags);

  CREATE TRIGGER tsvector_update_off
      BEFORE INSERT OR UPDATE ON openfoodfacts_products
      FOR EACH ROW EXECUTE FUNCTION
      tsvector_update_trigger(search_vector, 'pg_catalog.french', product_name, product_name_fr);
  ```

**1.2 Create search RPC function**
```sql
CREATE OR REPLACE FUNCTION search_openfoodfacts(search_query TEXT, max_results INT DEFAULT 5)
RETURNS TABLE (
    code TEXT, product_name TEXT, product_name_fr TEXT,
    calories_per_100g NUMERIC, protein_g_per_100g NUMERIC,
    carbs_g_per_100g NUMERIC, fat_g_per_100g NUMERIC,
    similarity_score FLOAT
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT p.code, p.product_name, p.product_name_fr,
           p.calories_per_100g, p.protein_g_per_100g, p.carbs_g_per_100g, p.fat_g_per_100g,
           GREATEST(
               similarity(unaccent(search_query), unaccent(p.product_name)),
               similarity(unaccent(search_query), unaccent(COALESCE(p.product_name_fr, '')))
           ) AS similarity_score
    FROM openfoodfacts_products p
    WHERE (search_vector @@ plainto_tsquery('french', search_query)
           OR similarity(unaccent(search_query), unaccent(p.product_name)) > 0.3
           OR similarity(unaccent(search_query), unaccent(COALESCE(p.product_name_fr, ''))) > 0.3)
          AND 'en:france' = ANY(p.countries_tags)
    ORDER BY similarity_score DESC LIMIT max_results;
END; $$;
```

**Validation**: `SELECT * FROM search_openfoodfacts('poulet', 3);`

### Phase 2: Data Import

**2.1 Create import script** `nutrition/openfoodfacts_import.py`:
```python
import gzip, json, logging
from pathlib import Path
from clients import get_supabase_client

JSONL_PATH = Path(__file__).parent / "openfood" / "openfoodfacts-products.jsonl.gz"
BATCH_SIZE = 1000

def filter_product(product: dict) -> dict | None:
    """Filter for France products with complete nutrition."""
    if "en:france" not in product.get("countries_tags", []): return None
    if not product.get("product_name"): return None

    nutrients = product.get("nutriments", {})
    try:
        cals = float(nutrients.get("energy-kcal_100g", 0))
        prot = float(nutrients.get("proteins_100g", 0))
        carbs = float(nutrients.get("carbohydrates_100g", 0))
        fat = float(nutrients.get("fat_100g", 0))
    except: return None

    if not (cals > 0 and prot >= 0 and carbs >= 0 and fat >= 0): return None

    return {
        "code": product.get("code", product.get("_id")),
        "product_name": product["product_name"],
        "product_name_fr": product.get("product_name_fr"),
        "countries_tags": product["countries_tags"],
        "calories_per_100g": round(cals, 2),
        "protein_g_per_100g": round(prot, 2),
        "carbs_g_per_100g": round(carbs, 2),
        "fat_g_per_100g": round(fat, 2),
    }

def import_openfoodfacts_data():
    supabase = get_supabase_client()
    batch = []
    total_processed = total_imported = 0

    with gzip.open(JSONL_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            total_processed += 1
            try:
                if filtered := filter_product(json.loads(line)):
                    batch.append(filtered)
                    if len(batch) >= BATCH_SIZE:
                        supabase.table("openfoodfacts_products").insert(batch).execute()
                        total_imported += len(batch)
                        logging.info(f"Imported {total_imported}/{total_processed}")
                        batch = []
            except Exception as e:
                logging.warning(f"Skip: {e}")

    if batch:
        supabase.table("openfoodfacts_products").insert(batch).execute()
        total_imported += len(batch)

    logging.info(f"Complete: {total_imported}/{total_processed}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import_openfoodfacts_data()
```

**Run**: `cd 4_Pydantic_AI_Agent && uv run python nutrition/openfoodfacts_import.py`

**Validation**: `SELECT COUNT(*) FROM openfoodfacts_products;` (expect 150K-250K)

### Phase 3: Client Refactor

**3.1 Create** `nutrition/openfoodfacts_client.py`:

Key changes from fatsecret_client.py:
- **DELETE**: `FatSecretAuthManager` class (lines 27-75)
- **KEEP**: `normalize_ingredient_name()`, `calculate_similarity()` unchanged
- **NEW**: `search_food_local()` - calls RPC instead of API
- **UPDATE**: `match_ingredient()` - remove `token`, `http_client` parameters

```python
import logging
from difflib import SequenceMatcher
from supabase import Client

logger = logging.getLogger(__name__)
MIN_CONFIDENCE_THRESHOLD = 0.5

def normalize_ingredient_name(name: str) -> str:
    """Normalize: lowercase, remove accents."""
    import unicodedata
    normalized = unicodedata.normalize("NFD", name)
    without_accents = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return without_accents.lower().strip()

def calculate_similarity(text1: str, text2: str) -> float:
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

async def search_food_local(query: str, supabase: Client, max_results: int = 5) -> list[dict]:
    """Search OFF database using RPC function."""
    try:
        result = supabase.rpc("search_openfoodfacts", {
            "search_query": query, "max_results": max_results
        }).execute()

        if not result.data: return []

        return [{
            "code": row["code"],
            "name": row["product_name_fr"] or row["product_name"],
            "calories_per_100g": float(row["calories_per_100g"]),
            "protein_g_per_100g": float(row["protein_g_per_100g"]),
            "carbs_g_per_100g": float(row["carbs_g_per_100g"]),
            "fat_g_per_100g": float(row["fat_g_per_100g"]),
            "confidence": float(row["similarity_score"])
        } for row in result.data]
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return []

async def match_ingredient(
    ingredient_name: str, quantity: float, unit: str, supabase: Client
) -> dict:
    """Match ingredient with cache-first strategy."""
    normalized = normalize_ingredient_name(ingredient_name)

    # Check cache
    cached = supabase.table("ingredient_mapping").select("*").eq("ingredient_name_normalized", normalized).execute()
    if cached.data:
        match = cached.data[0]
        supabase.table("ingredient_mapping").update({"usage_count": match["usage_count"] + 1}).eq("id", match["id"]).execute()

        multiplier = quantity / 100.0 if unit == "g" else 1.0
        return {
            "ingredient_name": ingredient_name,
            "matched_name": match["openfoodfacts_name"],
            "openfoodfacts_code": match["openfoodfacts_code"],
            "quantity": quantity, "unit": unit,
            "calories": round(match["calories_per_100g"] * multiplier, 1),
            "protein_g": round(match["protein_g_per_100g"] * multiplier, 1),
            "carbs_g": round(match["carbs_g_per_100g"] * multiplier, 1),
            "fat_g": round(match["fat_g_per_100g"] * multiplier, 1),
            "confidence": match["confidence_score"],
            "cache_hit": True
        }

    # Search database
    results = await search_food_local(ingredient_name, supabase)
    if not results or results[0]["confidence"] < MIN_CONFIDENCE_THRESHOLD:
        return {
            "ingredient_name": ingredient_name, "matched_name": None,
            "openfoodfacts_code": None, "quantity": quantity, "unit": unit,
            "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0,
            "confidence": 0, "cache_hit": False, "error": "No confident match"
        }

    best = results[0]

    # Cache it
    try:
        supabase.table("ingredient_mapping").insert({
            "ingredient_name": ingredient_name,
            "ingredient_name_normalized": normalized,
            "openfoodfacts_code": best["code"],
            "openfoodfacts_name": best["name"],
            "calories_per_100g": best["calories_per_100g"],
            "protein_g_per_100g": best["protein_g_per_100g"],
            "carbs_g_per_100g": best["carbs_g_per_100g"],
            "fat_g_per_100g": best["fat_g_per_100g"],
            "confidence_score": best["confidence"],
            "verified": False, "usage_count": 1
        }).execute()
    except: pass

    multiplier = quantity / 100.0 if unit == "g" else 1.0
    return {
        "ingredient_name": ingredient_name,
        "matched_name": best["name"],
        "openfoodfacts_code": best["code"],
        "quantity": quantity, "unit": unit,
        "calories": round(best["calories_per_100g"] * multiplier, 1),
        "protein_g": round(best["protein_g_per_100g"] * multiplier, 1),
        "carbs_g": round(best["carbs_g_per_100g"] * multiplier, 1),
        "fat_g": round(best["fat_g_per_100g"] * multiplier, 1),
        "confidence": best["confidence"],
        "cache_hit": False
    }
```

**3.2 Update cache schema**:
```sql
ALTER TABLE ingredient_mapping RENAME COLUMN fatsecret_food_id TO openfoodfacts_code;
ALTER TABLE ingredient_mapping RENAME COLUMN fatsecret_food_name TO openfoodfacts_name;
```

**3.3 Update** `nutrition/meal_plan_optimizer.py`:
- Line 6: `from nutrition.openfoodfacts_client import match_ingredient`
- Line 79: Remove `fatsecret_token, http_client` from signature
- Line 142: Remove `fatsecret_token, http_client` from call

**3.4 Update** `tools.py`:
- Lines 59-73: DELETE `from nutrition.fatsecret_client...` and `FATSECRET_AUTH_MANAGER`
- Line 860: Remove `fatsecret_token = ...` and token parameter from `calculate_meal_plan_macros()` call

**Validation**:
```bash
ruff format nutrition/openfoodfacts_client.py && ruff check nutrition/openfoodfacts_client.py
python -c "from nutrition.openfoodfacts_client import match_ingredient; print('✅')"
python -c "from agent import agent; print('✅')"
```

### Phase 4: Testing

**4.1 Create unit tests** `tests/test_openfoodfacts_client.py`:
```python
import pytest
from nutrition.openfoodfacts_client import search_food_local, match_ingredient
from clients import get_supabase_client

@pytest.mark.asyncio
@pytest.mark.parametrize("ingredient,should_match", [
    ("poulet", True), ("riz basmati", True), ("yaourt grec", True),
    ("fake-xyz-999", False)
])
async def test_search(ingredient, should_match):
    supabase = get_supabase_client()
    results = await search_food_local(ingredient, supabase)
    if should_match:
        assert len(results) > 0 and results[0]["confidence"] >= 0.5
    else:
        assert not results or results[0]["confidence"] < 0.5

@pytest.mark.asyncio
async def test_cache():
    supabase = get_supabase_client()
    test_ing = "test_cache_unique"
    supabase.table("ingredient_mapping").delete().eq("ingredient_name", test_ing).execute()

    r1 = await match_ingredient(test_ing, 100, "g", supabase)
    assert r1["cache_hit"] is False

    r2 = await match_ingredient(test_ing, 100, "g", supabase)
    assert r2["cache_hit"] is True

    supabase.table("ingredient_mapping").delete().eq("ingredient_name", test_ing).execute()
```

**Run**: `pytest tests/test_openfoodfacts_client.py -v`

**4.2 Full integration test**:
```bash
uv run python test_full_meal_plan.py
```

**Expected**:
```
✅ 7/7 days ±5%
✅ ≤1 complement/day
✅ Open Food Facts data present
```

**4.3 Check match rate**:
```sql
SELECT
    COUNT(*) FILTER (WHERE confidence_score >= 0.5) * 100.0 / COUNT(*) AS match_rate
FROM ingredient_mapping
WHERE created_at >= NOW() - INTERVAL '1 hour';
```
Expect: ≥90%

---

## Validation Commands

### Tier 1: Required (Must Pass)

```bash
# Linting
cd 4_Pydantic_AI_Agent
ruff format nutrition/openfoodfacts_client.py nutrition/openfoodfacts_import.py tests/test_openfoodfacts_client.py
ruff check nutrition/openfoodfacts_client.py nutrition/openfoodfacts_import.py tests/test_openfoodfacts_client.py

# Imports
python -c "from nutrition.openfoodfacts_client import match_ingredient; print('✅')"
python -c "from agent import agent; print('✅')"

# Unit tests
pytest tests/test_openfoodfacts_client.py -v

# Database
# Via mcp__supabase__execute_sql:
SELECT COUNT(*) FROM openfoodfacts_products;  -- Expect 150K-250K
```

### Tier 2: Recommended

```bash
# Type check (skip if all type hints present)
mypy nutrition/openfoodfacts_client.py --ignore-missing-imports

# Regression tests
pytest tests/test_validators.py tests/test_meal_planning.py -v

# Full integration
uv run python test_full_meal_plan.py
```

---

## Acceptance Criteria

- [ ] 150K-250K France products imported into `openfoodfacts_products`
- [ ] `search_openfoodfacts()` RPC returns results for French queries
- [ ] `openfoodfacts_client.py` implements local search (no API calls)
- [ ] Cache schema updated (fatsecret → openfoodfacts columns)
- [ ] Unit tests pass (100%)
- [ ] **Ingredient match rate ≥90%**
- [ ] **7/7 days within ±5% macro targets**
- [ ] **≤1 complement/day average**
- [ ] No regressions in existing tests
- [ ] 0 linting errors

---

## Rollback Plan

If migration fails:
```bash
# Revert tools.py (restore FatSecret manager lines 59-73)
# Revert meal_plan_optimizer.py (restore fatsecret_client import, add token param)
# Revert cache schema
ALTER TABLE ingredient_mapping RENAME COLUMN openfoodfacts_code TO fatsecret_food_id;
ALTER TABLE ingredient_mapping RENAME COLUMN openfoodfacts_name TO fatsecret_food_name;
```
Time: <5 minutes

---

**Estimated Time**: 3-4 hours
**Confidence**: 9/10
**Status**: Ready for execution
