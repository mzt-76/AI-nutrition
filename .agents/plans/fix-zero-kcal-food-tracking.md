# Feature: Fix 0 kcal silent insertion in food tracking

## Feature Description

When `match_ingredient()` fails to find a confident OFF match (confidence < 0.5), `log_food_entries.py` silently inserts rows with 0 calories into `daily_food_log`. This corrupts the user's daily macro balance, misleads the agent's dietary advice, and degrades downstream features (weekly coaching, remaining macros). The fix introduces a two-tier LLM fallback: (1) when OFF has low-confidence candidates (0.3-0.49), the LLM picks the best one from the list (keeping reliable OFF macros), (2) when OFF has no candidates at all, the LLM estimates macros directly.

## User Story

As a user tracking my meals
I want every logged food item to have accurate macro values
So that my daily balance and coaching advice are reliable

## Problem Statement

`log_food_entries.py` line 171+ inserts items with `calories=0` when OFF returns no confident match (`confidence=0`). The UPDATE branch (line 118) already guards against this — the INSERT branch simply forgot the check. This causes silent data corruption: the tracker shows 0 kcal items, the daily summary underreports, and the agent gives wrong "remaining macros" advice.

## Solution Statement

Three-layer fix:
1. **Guard**: Never insert 0 kcal rows — skip items with `confidence == 0` from direct insertion.
2. **LLM selector**: When OFF returns candidates at 0.3-0.49 confidence, send them to Claude Haiku to pick the semantically best match. Use the chosen candidate's OFF macros (verified data).
3. **LLM estimator**: When OFF returns nothing at all, ask Claude Haiku to estimate macros. Insert with `source="llm_estimated"`.

## Feature Metadata

**Feature Type**: Bug Fix + Enhancement
**Estimated Complexity**: Medium
**Primary Systems Affected**: `skills/food-tracking/scripts/log_food_entries.py` (main change), `skills/food-tracking/SKILL.md`
**Dependencies**: `anthropic` (already injected into skill scripts)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `skills/food-tracking/scripts/log_food_entries.py` (full file) — Bug location. Line 118-119: existing confidence guard in UPDATE branch. Line 171-216: INSERT branch missing the guard.
- `src/nutrition/openfoodfacts_client.py` (lines 422-471) — `search_food_local()`: returns raw candidates with confidence scores. Called directly from `log_food_entries` to get low-confidence candidates (no modification needed to this file).
- `src/nutrition/openfoodfacts_client.py` (lines 240-261) — `_unit_to_multiplier()`: converts quantity+unit to per-100g multiplier. Imported by `log_food_entries`.
- `src/nutrition/openfoodfacts_client.py` (lines 575-629) — `_passes_atwater_check()`: validates candidate data quality.
- `src/nutrition/openfoodfacts_client.py` (lines 314-352) — `_calorie_density_plausible()`: rejects implausible calorie densities.
- `skills/meal-planning/scripts/generate_custom_recipe.py` (lines 59-104, 131-178) — **Pattern reference** for calling Claude Haiku. Uses `anthropic_client.messages.create()`, model `claude-haiku-4-5-20251001`, JSON response parsing.
- `sql/0-all-tables.sql` (lines 372-388) — `daily_food_log` schema. Column `source TEXT DEFAULT 'openfoodfacts'` already supports custom values — use `"llm_estimated"` for LLM-based entries.
- `tests/test_log_food_entries.py` — Existing tests. **Note line 127-154**: `test_log_food_entries_unmatched_ingredient` currently asserts that 0-calorie items ARE inserted with `success=True`. This test must be updated to expect the new behavior.
- `skills/food-tracking/SKILL.md` — Skill documentation for agent routing/behavior.

### New Files to Create

None. All changes go into existing files.

### Key Design Decision: Don't modify `openfoodfacts_client.py`

The low-confidence candidates are needed ONLY by `log_food_entries`. Instead of modifying the shared `match_ingredient()` API to return them (which would pollute the interface for all callers), `log_food_entries` calls `search_food_local()` directly when it needs candidates. This is one extra DB call (~5ms) but only on the failure path, and it keeps the shared API clean.

### Patterns to Follow

**LLM call pattern** (from `generate_custom_recipe.py:172-178`):
```python
message = await anthropic_client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=200,
    temperature=0.0,  # deterministic for selection
    messages=[{"role": "user", "content": prompt}],
)
raw_content = message.content[0].text.strip()
```

**Skill script kwargs pattern** (all scripts):
```python
anthropic_client = kwargs.get("anthropic_client")  # already injected by run_skill_script
```

**Test mock pattern** (from `test_log_food_entries.py`):
```python
_PATCH_TARGET = "log_food_entries.match_ingredient"
with patch(_PATCH_TARGET, new_callable=AsyncMock) as mock_match:
    mock_match.return_value = {...}
```

---

## IMPLEMENTATION PLAN

### Phase 1: Add LLM fallback helpers in `log_food_entries.py`

Two small async functions: one to ask the LLM to pick from a list of OFF candidates, one to estimate macros from scratch.

### Phase 2: Rewrite the INSERT branch

The loop at lines 171-216 gets a confidence check. When `confidence == 0`, it tries LLM selection (tier 1), then LLM estimation (tier 2), then skips.

### Phase 3: Update tests and docs

- Update the existing test that asserts 0-calorie insertion.
- Add new tests for both LLM fallback paths.
- Update SKILL.md with `skipped_items` documentation.

---

## STEP-BY-STEP TASKS

### Task 1: ADD LLM fallback helpers in `log_food_entries.py`

- **IMPLEMENT**: Add imports and two async helper functions at the top of the file (after existing imports, before `execute`):

  ```python
  import re

  from src.nutrition.openfoodfacts_client import (
      _passes_atwater_check,
      _calorie_density_plausible,
      _unit_to_multiplier,
      search_food_local,
  )

  _LLM_MODEL = "claude-haiku-4-5-20251001"

  _LLM_SELECT_PROMPT = """L'utilisateur veut logger "{ingredient_name}".
  Voici les produits OpenFoodFacts les plus proches :
  {candidates_text}

  Quel numéro correspond le mieux à "{ingredient_name}" ?
  Réponds UNIQUEMENT avec le numéro (ex: 1). Si aucun ne correspond, réponds "0"."""

  _LLM_ESTIMATE_PROMPT = """Estime les macronutriments pour 100g de "{ingredient_name}".
  Réponds UNIQUEMENT en JSON : {{"calories": X, "protein_g": X, "carbs_g": X, "fat_g": X}}"""


  async def _llm_select_candidate(
      anthropic_client, ingredient_name: str, candidates: list[dict]
  ) -> dict | None:
      """Ask LLM to pick the best OFF candidate for an ingredient."""
      if not anthropic_client or not candidates:
          return None
      lines = []
      for i, c in enumerate(candidates, 1):
          lines.append(
              f"{i}. {c['name']} — {c['calories_per_100g']:.0f} kcal/100g "
              f"(P:{c['protein_g_per_100g']:.1f} G:{c['carbs_g_per_100g']:.1f} "
              f"L:{c['fat_g_per_100g']:.1f})"
          )
      prompt = _LLM_SELECT_PROMPT.format(
          ingredient_name=ingredient_name,
          candidates_text="\n".join(lines),
      )
      try:
          message = await anthropic_client.messages.create(
              model=_LLM_MODEL,
              max_tokens=10,
              temperature=0.0,
              messages=[{"role": "user", "content": prompt}],
          )
          choice = message.content[0].text.strip()
          m = re.search(r"\d+", choice)
          if not m:
              return None
          idx = int(m.group()) - 1
          if 0 <= idx < len(candidates):
              logger.info(
                  "LLM selected candidate #%d '%s' for '%s'",
                  idx + 1, candidates[idx]["name"], ingredient_name,
              )
              return candidates[idx]
          return None  # LLM said "0" or out of range
      except Exception as e:
          logger.warning("LLM select failed for '%s': %s", ingredient_name, e)
          return None


  async def _llm_estimate_macros(
      anthropic_client, ingredient_name: str
  ) -> dict | None:
      """Ask LLM to estimate macros when OFF has no data at all."""
      if not anthropic_client:
          return None
      prompt = _LLM_ESTIMATE_PROMPT.format(ingredient_name=ingredient_name)
      try:
          message = await anthropic_client.messages.create(
              model=_LLM_MODEL,
              max_tokens=80,
              temperature=0.0,
              messages=[{"role": "user", "content": prompt}],
          )
          raw = message.content[0].text.strip()
          if raw.startswith("```"):
              raw = "\n".join(raw.split("\n")[1:-1])
          data = json.loads(raw)
          logger.info("LLM estimated macros for '%s': %s", ingredient_name, data)
          return {
              "calories": float(data.get("calories", 0)),
              "protein_g": float(data.get("protein_g", 0)),
              "carbs_g": float(data.get("carbs_g", 0)),
              "fat_g": float(data.get("fat_g", 0)),
          }
      except Exception as e:
          logger.warning("LLM estimate failed for '%s': %s", ingredient_name, e)
          return None
  ```

- **PATTERN**: Mirrors `generate_custom_recipe.py:172-178` (same model, same try/except/parse pattern).
- **NOTE on `re.search`**: Extracts the first digit from LLM response instead of `int(choice)`. Handles cases like "Le numéro 1" or "1." gracefully.
- **VALIDATE**: `python -c "import importlib.util; spec = importlib.util.spec_from_file_location('x', 'skills/food-tracking/scripts/log_food_entries.py'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); print('OK')"`

### Task 2: UPDATE INSERT branch in `log_food_entries.py`

- **IMPLEMENT**: Replace the loop and return at lines 164-239 with:

  ```python
      # Build rows and insert
      logged_items = []
      skipped_items = []
      total_calories = 0.0
      total_protein = 0.0
      total_carbs = 0.0
      total_fat = 0.0

      anthropic_client = kwargs.get("anthropic_client")

      for item, macros in zip(items, macro_results):
          food_name = item.get("name", "")
          confidence = macros.get("confidence", 0) if macros else 0
          source = "openfoodfacts"

          if confidence == 0:
              # --- LLM fallback ---
              resolved = None

              # Tier 1: fetch low-confidence OFF candidates, let LLM pick
              try:
                  raw_candidates = await search_food_local(food_name, supabase)
                  valid_candidates = [
                      c for c in raw_candidates
                      if c["confidence"] >= 0.3
                      and _passes_atwater_check(c)
                      and _calorie_density_plausible(food_name, c["calories_per_100g"])
                  ]
              except Exception:
                  valid_candidates = []

              if valid_candidates:
                  selected = await _llm_select_candidate(
                      anthropic_client, food_name, valid_candidates[:5]
                  )
                  if selected:
                      multiplier = _unit_to_multiplier(
                          item.get("quantity", 100), item.get("unit", "g"), food_name
                      )
                      resolved = {
                          "calories": round(selected["calories_per_100g"] * multiplier, 1),
                          "protein_g": round(selected["protein_g_per_100g"] * multiplier, 1),
                          "carbs_g": round(selected["carbs_g_per_100g"] * multiplier, 1),
                          "fat_g": round(selected["fat_g_per_100g"] * multiplier, 1),
                      }
                      confidence = 0.6
                      source = "openfoodfacts"  # macros are still from OFF

              # Tier 2: LLM estimates macros directly
              if not resolved:
                  estimated = await _llm_estimate_macros(anthropic_client, food_name)
                  if estimated:
                      multiplier = _unit_to_multiplier(
                          item.get("quantity", 100), item.get("unit", "g"), food_name
                      )
                      resolved = {
                          "calories": round(estimated["calories"] * multiplier, 1),
                          "protein_g": round(estimated["protein_g"] * multiplier, 1),
                          "carbs_g": round(estimated["carbs_g"] * multiplier, 1),
                          "fat_g": round(estimated["fat_g"] * multiplier, 1),
                      }
                      confidence = 0.4
                      source = "llm_estimated"

              # Both OFF and LLM failed → skip
              if not resolved:
                  skipped_items.append({"food_name": food_name, "reason": "no_match"})
                  continue

              cal = resolved["calories"]
              prot = resolved["protein_g"]
              carbs = resolved["carbs_g"]
              fat = resolved["fat_g"]
          else:
              # Normal OFF match
              cal = macros.get("calories", 0) if macros else 0
              prot = macros.get("protein_g", 0) if macros else 0
              carbs = macros.get("carbs_g", 0) if macros else 0
              fat = macros.get("fat_g", 0) if macros else 0

          row = {
              "user_id": user_id,
              "log_date": log_date,
              "meal_type": meal_type,
              "food_name": food_name,
              "quantity": item.get("quantity", 100),
              "unit": item.get("unit", "g"),
              "calories": round(cal, 1),
              "protein_g": round(prot, 1),
              "carbs_g": round(carbs, 1),
              "fat_g": round(fat, 1),
              "source": source,
          }

          # Upsert: insert or update if same user/date/meal/food already exists
          await (
              supabase.table("daily_food_log")
              .upsert(row, on_conflict="user_id,log_date,meal_type,food_name")
              .execute()
          )

          total_calories += cal
          total_protein += prot
          total_carbs += carbs
          total_fat += fat

          logged_items.append({
              "food_name": food_name,
              "quantity": item.get("quantity", 100),
              "unit": item.get("unit", "g"),
              "calories": round(cal, 1),
              "protein_g": round(prot, 1),
              "carbs_g": round(carbs, 1),
              "fat_g": round(fat, 1),
              "matched_name": macros.get("matched_name") if macros else None,
              "confidence": confidence,
              "source": source,
          })

      logger.info(
          f"Logged {len(logged_items)} food items for user {user_id} "
          f"on {log_date}: {round(total_calories)} kcal"
          + (f" ({len(skipped_items)} skipped)" if skipped_items else "")
      )

      result_data = {
          "success": len(logged_items) > 0,
          "logged_items": logged_items,
          "skipped_items": skipped_items,
          "totals": {
              "calories": round(total_calories, 1),
              "protein_g": round(total_protein, 1),
              "carbs_g": round(total_carbs, 1),
              "fat_g": round(total_fat, 1),
          },
          "log_date": log_date,
          "meal_type": meal_type,
          "item_count": len(logged_items),
      }
      if not logged_items and skipped_items:
          result_data["error"] = "Aucun aliment matché"
          result_data["code"] = "ALL_SKIPPED"

      return json.dumps(result_data, indent=2, ensure_ascii=False)
  ```

- **VALIDATE**: `python -m pytest tests/test_log_food_entries.py -x -q`

### Task 3: UPDATE tests — `tests/test_log_food_entries.py`

- **UPDATE**: Replace `test_log_food_entries_unmatched_ingredient` (line 127) with:
  ```python
  @pytest.mark.asyncio
  async def test_log_food_entries_unmatched_ingredient_skipped(mock_supabase):
      """Unmatched ingredient with no LLM client is skipped, not logged at 0 kcal."""
      with patch(_PATCH_TARGET, new_callable=AsyncMock) as mock_match:
          mock_match.return_value = {
              "ingredient_name": "mystery food",
              "matched_name": None,
              "openfoodfacts_code": None,
              "quantity": 100, "unit": "g",
              "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0,
              "confidence": 0, "cache_hit": False,
          }
          with patch("log_food_entries.search_food_local", new_callable=AsyncMock, return_value=[]):
              result = await execute(
                  supabase=mock_supabase, user_id="user-123",
                  items=[{"name": "mystery food", "quantity": 100, "unit": "g"}],
              )
          data = json.loads(result)
          assert data["success"] is False
          assert data["code"] == "ALL_SKIPPED"
          assert len(data["skipped_items"]) == 1
          assert mock_supabase.table.return_value.upsert.call_count == 0
  ```

- **ADD**: Test for LLM selector path:
  ```python
  @pytest.mark.asyncio
  async def test_log_food_entries_llm_selects_off_candidate(mock_supabase):
      """When OFF has low-confidence candidates, LLM picks the best one."""
      mock_anthropic = AsyncMock()
      mock_anthropic.messages.create.return_value = MagicMock(
          content=[MagicMock(text="1")]
      )
      candidates = [
          {"name": "Pain aux graines", "code": "123",
           "calories_per_100g": 265, "protein_g_per_100g": 8.5,
           "carbs_g_per_100g": 44, "fat_g_per_100g": 5.2, "confidence": 0.42},
          {"name": "Baguette blanche", "code": "456",
           "calories_per_100g": 250, "protein_g_per_100g": 8.0,
           "carbs_g_per_100g": 50, "fat_g_per_100g": 1.0, "confidence": 0.38},
      ]
      with patch(_PATCH_TARGET, new_callable=AsyncMock) as mock_match:
          mock_match.return_value = {
              "ingredient_name": "baguette aux graines",
              "matched_name": None,
              "confidence": 0, "calories": 0, "protein_g": 0,
              "carbs_g": 0, "fat_g": 0, "cache_hit": False,
          }
          with patch("log_food_entries.search_food_local", new_callable=AsyncMock, return_value=candidates):
              result = await execute(
                  supabase=mock_supabase, user_id="user-123",
                  anthropic_client=mock_anthropic,
                  items=[{"name": "baguette aux graines", "quantity": 80, "unit": "g"}],
                  meal_type="petit-dejeuner",
              )
          data = json.loads(result)
          assert data["success"] is True
          assert data["logged_items"][0]["calories"] > 0
          assert data["logged_items"][0]["source"] == "openfoodfacts"
          assert mock_supabase.table.return_value.upsert.call_count == 1
  ```

- **ADD**: Test for LLM estimator path:
  ```python
  @pytest.mark.asyncio
  async def test_log_food_entries_llm_estimates_macros(mock_supabase):
      """When OFF has zero candidates, LLM estimates macros directly."""
      mock_anthropic = AsyncMock()
      mock_anthropic.messages.create.return_value = MagicMock(
          content=[MagicMock(text='{"calories": 280, "protein_g": 9, "carbs_g": 48, "fat_g": 5}')]
      )
      with patch(_PATCH_TARGET, new_callable=AsyncMock) as mock_match:
          mock_match.return_value = {
              "ingredient_name": "plat maison exotique",
              "matched_name": None,
              "confidence": 0, "calories": 0, "protein_g": 0,
              "carbs_g": 0, "fat_g": 0, "cache_hit": False,
          }
          with patch("log_food_entries.search_food_local", new_callable=AsyncMock, return_value=[]):
              result = await execute(
                  supabase=mock_supabase, user_id="user-123",
                  anthropic_client=mock_anthropic,
                  items=[{"name": "plat maison exotique", "quantity": 100, "unit": "g"}],
              )
          data = json.loads(result)
          assert data["success"] is True
          assert data["logged_items"][0]["calories"] == 280
          assert data["logged_items"][0]["source"] == "llm_estimated"
  ```

- **ADD**: Test for mixed items (partial success):
  ```python
  @pytest.mark.asyncio
  async def test_log_food_entries_partial_success(mock_supabase):
      """One item matches OFF, one is skipped → success but skipped_items present."""
      with patch(_PATCH_TARGET, new_callable=AsyncMock) as mock_match:
          mock_match.side_effect = [
              _make_match_result("poulet", 200, 330, 62, 0, 7.2),
              {"ingredient_name": "xyz", "matched_name": None,
               "confidence": 0, "calories": 0, "protein_g": 0,
               "carbs_g": 0, "fat_g": 0, "cache_hit": False},
          ]
          with patch("log_food_entries.search_food_local", new_callable=AsyncMock, return_value=[]):
              result = await execute(
                  supabase=mock_supabase, user_id="user-123",
                  items=[
                      {"name": "poulet", "quantity": 200, "unit": "g"},
                      {"name": "xyz", "quantity": 100, "unit": "g"},
                  ],
              )
          data = json.loads(result)
          assert data["success"] is True
          assert len(data["logged_items"]) == 1
          assert len(data["skipped_items"]) == 1
  ```

- **VALIDATE**: `python -m pytest tests/test_log_food_entries.py -x -v`

### Task 4: UPDATE `skills/food-tracking/SKILL.md`

- **IMPLEMENT**: Add a rule after the existing "Decomposition obligatoire" rule:

  ```markdown
  **Echec de matching OFF** : Si `log_food_entries` retourne `skipped_items` non vide, mentionner explicitement a l'utilisateur les aliments non enregistres et proposer de reformuler le nom (plus generique, ex. "pain complet" au lieu de "baguette aux graines bio Carrefour") ou de fournir les macros manuellement.
  ```

- **VALIDATE**: Read the file and verify the rule is in the right section.

### Task 5: Lint and full test suite

- **VALIDATE**:
  ```bash
  ruff format skills/food-tracking/scripts/log_food_entries.py tests/test_log_food_entries.py
  ruff check skills/food-tracking/scripts/log_food_entries.py tests/test_log_food_entries.py
  python -m pytest tests/test_log_food_entries.py tests/test_openfoodfacts_client.py -x -v
  python -m pytest tests/ -x -q --timeout=30
  ```

---

## TESTING STRATEGY

### Unit Tests (deterministic, in `tests/`)

1. **Unmatched item without LLM** → skipped, not inserted at 0 kcal
2. **LLM selects OFF candidate** → inserted with OFF macros and `source="openfoodfacts"`
3. **LLM estimates macros** → inserted with `source="llm_estimated"` and estimated values
4. **Partial success** → some items logged, some skipped
5. **All items skipped** → `success: false`, `code: "ALL_SKIPPED"`
6. **Existing happy-path tests** → must still pass unchanged

### Edge Cases

- `anthropic_client` is `None` (CLI mode without API key) → items with no OFF match are skipped, no crash
- LLM returns invalid JSON for estimation → item skipped
- LLM returns "0" or "aucun" for selection → falls through to estimation tier
- LLM returns "Le numéro 1" → `re.search(r"\d+")` extracts "1" correctly
- All items have good OFF matches → no LLM calls at all (no cost/latency impact)

---

## VALIDATION COMMANDS

### Level 1: Lint

```bash
ruff format src/ tests/ skills/ && ruff check src/ tests/
```

### Level 2: Unit Tests

```bash
python -m pytest tests/test_log_food_entries.py -x -v
python -m pytest tests/test_openfoodfacts_client.py -x -v
```

### Level 3: Full Test Suite

```bash
python -m pytest tests/ -x -q --timeout=30
```

### Level 4: Manual Validation (optional, requires real DB)

```bash
# Test that search_food_local returns candidates for a tricky name
python -c "
import asyncio
from src.clients import get_async_supabase_client
from src.nutrition.openfoodfacts_client import search_food_local
async def test():
    sb = get_async_supabase_client()
    results = await search_food_local('baguette aux graines', sb)
    for r in results:
        print(f'  {r[\"name\"]}: {r[\"calories_per_100g\"]} kcal (conf={r[\"confidence\"]:.2f})')
asyncio.run(test())
"
```

---

## ACCEPTANCE CRITERIA

- [ ] No item with `calories=0` and `confidence=0` is ever inserted into `daily_food_log`
- [ ] When OFF has low-confidence candidates (0.3-0.49), the LLM selects the best one and OFF macros are used
- [ ] When OFF has no candidates, the LLM estimates macros with `source="llm_estimated"`
- [ ] When both fail, the item is skipped and reported in `skipped_items`
- [ ] Response includes `skipped_items` (empty list when all items matched)
- [ ] Existing happy-path tests still pass
- [ ] All new tests pass
- [ ] `ruff format` + `ruff check` clean
- [ ] No modifications to `src/nutrition/openfoodfacts_client.py`
- [ ] No new dependencies — uses existing `anthropic_client` injection

---

## NOTES

### Design decisions

- **No modification to `openfoodfacts_client.py`**: Low-confidence candidates are only needed by `log_food_entries`. Instead of adding a `low_confidence_candidates` field to the shared `match_ingredient()` API, we call `search_food_local()` directly in `log_food_entries` when confidence=0. One extra ~5ms DB call on the failure path only. Keeps the shared API clean.
- **LLM model**: Claude Haiku (`claude-haiku-4-5-20251001`) — fastest and cheapest. Same model used in `generate_custom_recipe.py`. Selection needs ~10 output tokens, estimation ~80.
- **Temperature 0.0**: Deterministic for both selection and estimation. We want reproducibility, not creativity.
- **`re.search(r"\d+")` for parsing LLM choice**: More robust than `int(choice)`. Handles "1", "1.", "Le numéro 1", etc.
- **No caching of LLM-estimated macros in `ingredient_mapping`**: Intentional. LLM estimates are approximate. If we cache them, future lookups for the same ingredient will use the estimate forever instead of potentially finding a real OFF match later (e.g., after DB is enriched with new products).
- **No `partial_success` field**: Removed to keep the response simple. `skipped_items` non-empty is sufficient signal. `success` is `true` if at least one item was logged, `false` only if ALL items failed.
- **No frontend changes in this PR**: The `source` field is already in `daily_food_log`. A follow-up PR can add a visual badge for `llm_estimated` entries in the tracker UI.
- **`_unit_to_multiplier` import**: Private function but stable and pure. Used within the same project. Importing avoids duplicating the conversion logic.
