# Feature: v2e — Pipeline d'Import de Recettes Multi-Sources

## User Story

En tant que développeur du système de meal-planning,
je veux importer automatiquement des recettes variées depuis 8+ sources (APIs + web scraping),
afin de combler les lacunes macro de la DB et améliorer la diversité des plans générés.

## Problem Statement

La DB actuelle (547 recettes) a un déséquilibre macro : ~44% des recettes dejeuner/diner sont high-fat (>35% fat calories). Le filtre fat_ratio ajouté en v2d rejette ces recettes, réduisant le pool disponible. Il faut importer 300-400 recettes ciblées (low-fat, high-protein, balanced, végétarien/vegan) pour rééquilibrer la distribution.

## Solution Statement

Pipeline modulaire LLM-free (rule 10) avec :
- **1 orchestrateur** (`scripts/import_recipes.py`) — gère le flux commun (OFF validate → post-filter → upsert)
- **8 adapteurs source** (`scripts/recipe_sources/`) — chacun sait fetcher et parser une source spécifique
- **OFF validation** comme unique arbitre des macros — peu importe la fiabilité de la source
- **Filtres post-OFF** — rejet des recettes hors cibles macro après calcul réel

Les macros source (Spoonacular, BBC Good Food) servent uniquement de pré-filtre optionnel. Seules les macros OFF font foi.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `scripts/`, `src/nutrition/openfoodfacts_client.py` (consommé, pas modifié)
**Dependencies**: httpx (existant), beautifulsoup4 + lxml (à ajouter), clés API (Spoonacular, Edamam — gratuit)

---

## SOURCES — 8 adapteurs

### APIs structurées (3)

| Source | Langue | Pré-filtre macro | Volume | Clé API |
|--------|--------|-------------------|--------|---------|
| **Spoonacular** (`api.spoonacular.com`) | EN | Oui (`minProtein`, `maxFat`) | 150 req/jour gratuit | `SPOONACULAR_API_KEY` |
| **Edamam** (`api.edamam.com`) | EN | Oui (`nutrients[FAT]`, `health=vegan`) | 10k req/mois gratuit | `EDAMAM_APP_ID` + `EDAMAM_APP_KEY` |
| **TheMealDB** (`themealdb.com`) | EN | Non | Illimité, ~300 recettes | Aucune |

### Sites français — scraping (3)

| Source | URL | Avantage | Ingrédients |
|--------|-----|----------|-------------|
| **Marmiton** | `marmiton.org` | Plus grand site FR, recettes populaires | Français natif |
| **750g** | `750g.com` | Bon catalogue, recettes bien structurées | Français natif |
| **Cuisine AZ** | `cuisineaz.com` | Large catalogue, format HTML propre | Français natif |

### Sites internationaux — scraping (2)

| Source | URL | Avantage | Ingrédients |
|--------|-----|----------|-------------|
| **BBC Good Food** | `bbcgoodfood.com` | Macros affichées, section "healthy" | Anglais → traduction |
| **AllRecipes** | `allrecipes.com` | Immense catalogue, ingrédients structurés | Anglais → traduction |

### Volume estimé

| Source | Fetched | Taux OFF estimé | Recettes utiles |
|--------|---------|-----------------|-----------------|
| Spoonacular | 100 | ~70% | ~70 |
| Edamam | 80 | ~65% | ~52 |
| TheMealDB | 50 | ~60% | ~30 |
| Marmiton | 100 | ~80% | ~80 |
| 750g | 60 | ~75% | ~45 |
| Cuisine AZ | 60 | ~75% | ~45 |
| BBC Good Food | 80 | ~60% | ~48 |
| AllRecipes | 60 | ~55% | ~33 |
| **Total** | **~590** | | **~403** |

### Stratégie par profil macro (quelles sources pour quels gaps)

| Gap à combler | Sources prioritaires | Requêtes |
|---|---|---|
| **Low-fat, high-protein** | Spoonacular `minProtein=25&maxFat=20`, BBC Good Food "healthy" | Fitness, grillades, salades protéinées |
| **Méditerranéen équilibré** | Marmiton "méditerranéen", Cuisine AZ "léger", Edamam `cuisineType=Mediterranean` | Poisson, légumes, céréales complètes |
| **Végétarien/vegan varié** | AllRecipes veggie, 750g "vegan", Edamam `health=vegan`, Spoonacular `diet=vegan` | Combler les 58-59 recettes actuelles |
| **Petit-déjeuner diversifié** | BBC Good Food breakfast, Marmiton "petit-déjeuner", TheMealDB Breakfast | Pool actuel = 137, beaucoup similaires |
| **Collations protéinées** | Spoonacular snacks, Edamam `mealType=Snack&minProtein=15` | Smoothies, barres, yaourts |

---

## CONTEXT REFERENCES

### Fichiers à lire OBLIGATOIREMENT avant d'implémenter

- `scripts/import_themealdb.py` — **Modèle complet** : même pattern (fetch → build row → OFF validate → upsert). 530+ lignes. Copier la structure. Contient `INGREDIENT_FR` (~100 traductions), `_parse_measure()`, `_auto_correct_portions()`, `_has_sane_macro_ratios()`, `_detect_allergens()`.
- `scripts/seed_recipes_batch.py` — Pattern batch JSON → `off_validate_recipe()` → upsert
- `src/nutrition/openfoodfacts_client.py` (lignes 729-823) — `off_validate_recipe()` : validation parallèle de tous les ingrédients
- `src/nutrition/openfoodfacts_client.py` (lignes 1-50) — `normalize_ingredient_name()`, `_PIECE_WEIGHTS`, `_ML_TO_G_DENSITY`
- `sql/create_recipes_table.sql` — Schéma complet recipes table
- `tests/test_scripts_no_llm.py` — Enforcement rule 10

### Fichiers créés

```
scripts/
  import_recipes.py                  ← orchestrateur unique (CLI principal)
  recipe_sources/
    __init__.py                      ← exporte RecipeSource + all adapters
    base.py                          ← ABC RecipeSource
    spoonacular.py                   ← API
    edamam.py                        ← API
    themealdb_adapter.py             ← API (refactor partiel de l'existant)
    marmiton.py                      ← scraping
    sept_cinquante_g.py              ← scraping (750g)
    cuisine_az.py                    ← scraping
    bbc_good_food.py                 ← scraping
    allrecipes.py                    ← scraping
  data/
    ingredient_translations.json     ← traductions EN→FR (~300 entrées)
tests/
  test_recipe_sources.py             ← tests unitaires des adapteurs
```

### Patterns existants à suivre

**Structure script** (copier de `import_themealdb.py`) :
```python
"""Import recipes from <source>. LLM-free (rule 10)."""
import argparse, asyncio, logging
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from src.clients import get_supabase_client
from src.nutrition.openfoodfacts_client import off_validate_recipe, normalize_ingredient_name
import httpx

logger = logging.getLogger(__name__)
```

**Upsert** : `supabase.table("recipes").upsert(row, on_conflict="name_normalized,meal_type").execute()`

**HTTP** : `async with httpx.AsyncClient(timeout=30.0) as client:`

**Logging** : `logger.info()`, `logger.warning()`, `logger.error()` — jamais `print()`

**Fonctions à réutiliser de `import_themealdb.py`** :
- `_auto_correct_portions(row)` — divise si > 900 kcal
- `_has_sane_macro_ratios(row)` — rejette fat>45%, protein<8%
- `_detect_allergens(ingredients)` — scan mots-clés allergènes
- `_parse_measure(measure_str)` — parse quantités libres → (float, str)
- `_normalize_name(name)` — normalise pour déduplication

Ces fonctions seront extraites dans `base.py` pour être partagées par tous les adapteurs.

---

## ARCHITECTURE DU PIPELINE

```
                    ┌──────────────────┐
                    │ import_recipes.py │  CLI : --source, --limit, --dry-run,
                    │  (orchestrateur)  │         --max-fat-pct, --min-protein-pct,
                    └────────┬─────────┘         --meal-type, --diet-type
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
         │Spoonac. │   │Marmiton │   │BBC Good │  ... (8 adapteurs)
         │Adapter  │   │ Adapter │   │  Food   │
         └────┬────┘   └────┬────┘   └────┬────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                     list[RawRecipe]
                             │
                    ┌────────▼─────────┐
                    │  Translate EN→FR  │  (si source anglaise)
                    │  + parse quantités│
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ Build recipe row  │  (schema DB)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │off_validate_recipe│  ← SEUL ARBITRE des macros
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ Post-filter       │  fat<35%, protein>15%, 150-900 kcal
                    │ + auto-correct    │  auto-divide si > 900 kcal
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ Upsert Supabase   │  on_conflict=name_normalized,meal_type
                    └──────────────────┘
```

### Interface RecipeSource (ABC)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
import httpx

@dataclass
class RawRecipe:
    """Recipe as fetched from source, before OFF validation."""
    name: str
    ingredients: list[dict]        # [{"name": str, "quantity": float, "unit": str}]
    instructions: str
    meal_type: str                 # "dejeuner" | "diner" | "petit-dejeuner" | "collation"
    cuisine_type: str              # "française", "italienne", etc.
    diet_type: str                 # "omnivore" | "végétarien" | "vegan"
    prep_time_minutes: int
    tags: list[str]
    source: str                    # "spoonacular", "marmiton", etc.
    source_url: str                # URL originale pour traçabilité

class RecipeSource(ABC):
    """Base class for recipe source adapters."""

    @abstractmethod
    async def fetch_recipes(
        self,
        client: httpx.AsyncClient,
        limit: int = 50,
        **filters,
    ) -> list[RawRecipe]:
        """Fetch recipes from this source."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Source identifier (e.g., 'spoonacular', 'marmiton')."""
        ...

    @property
    def requires_api_key(self) -> bool:
        """Whether this source needs an API key."""
        return False
```

---

## DÉTAILS PAR SOURCE

### APIs structurées

#### Spoonacular

**Endpoints** :
- `GET /recipes/complexSearch?apiKey=...&number=10&addRecipeNutrition=true&addRecipeInstructions=true&minProteinPercent=20&maxFatPercent=30`
- Réponse inclut `extendedIngredients[]` avec `name`, `amount`, `unit`, `measures.metric`

**Parsing ingrédients** :
```python
# Spoonacular fournit les mesures métriques directement
for ing in recipe["extendedIngredients"]:
    metric = ing.get("measures", {}).get("metric", {})
    yield {
        "name": translate_ingredient(ing["name"]),
        "quantity": metric.get("amount", ing["amount"]),
        "unit": _normalize_unit(metric.get("unitShort", ing["unit"])),
    }
```

#### Edamam

**Endpoint** : `GET /api/recipes/v2?type=public&app_id=...&app_key=...&q=chicken&health=low-fat&mealType=Lunch`
**Avantage** : Filtres nutritionnels très précis, supporte `health=vegan`, `cuisineType=`, `mealType=`

#### TheMealDB

**Déjà implémenté** dans `scripts/import_themealdb.py`. L'adapteur sera un thin wrapper qui réutilise les fonctions existantes.

### Sites français (scraping)

#### Marmiton

**Recherche** : `GET https://www.marmiton.org/recettes/recherche.aspx?aqt={query}&type=1`
**Page recette** : titre dans `h1.MRTN__sc-1kb3d02-0`, ingrédients dans `.MuiGrid-root .SHRD__sc-10plrl5-0`
**Rate limit** : 1 req / 2 sec, `User-Agent` réaliste

#### 750g

**Recherche** : `GET https://www.750g.com/recherche/?q={query}`
**Page recette** : titre, ingrédients dans les balises structurées
**Rate limit** : 1 req / 2 sec

#### Cuisine AZ

**Recherche** : `GET https://www.cuisineaz.com/recherche/recettes?q={query}`
**Page recette** : format HTML propre, ingrédients bien balisés

### Sites internationaux (scraping EN)

#### BBC Good Food

**Recherche** : `GET https://www.bbcgoodfood.com/search?q={query}`
**Avantage** : Macros affichées sur chaque recette (pré-filtre possible côté scraping)
**Page recette** : ingrédients structurés, nutrition dans `.nutrition` div

#### AllRecipes

**Recherche** : `GET https://www.allrecipes.com/search?q={query}`
**Page recette** : ingrédients dans `ul.mntl-structured-ingredients`, données JSON-LD dans `<script type="application/ld+json">`
**Avantage** : JSON-LD contient les ingrédients structurés → parsing plus fiable que HTML

---

## STEP-BY-STEP TASKS

### Task 1 : ADD dependencies

- **IMPLEMENT** : Ajouter dans `requirements.txt` :
  - `beautifulsoup4>=4.12`
  - `lxml>=5.0`
- **IMPLEMENT** : Ajouter dans `.env.example` :
  - `SPOONACULAR_API_KEY=`
  - `EDAMAM_APP_ID=`
  - `EDAMAM_APP_KEY=`
- **VALIDATE** : `pip install beautifulsoup4 lxml && python -c "from bs4 import BeautifulSoup; print('OK')"`

### Task 2 : CREATE `scripts/data/ingredient_translations.json`

- **IMPLEMENT** : Table de traduction EN→FR étendue (~300 ingrédients)
  - Fusionner le dict `INGREDIENT_FR` de `import_themealdb.py` (~100 entrées)
  - Ajouter ~200 ingrédients supplémentaires courants en cuisine
  - Inclure variantes : `chicken` ET `chicken breast` ET `boneless chicken` → `poulet`
- **FORMAT** : `{"chicken breast": "blanc de poulet", "olive oil": "huile d'olive", ...}`
- **GOTCHA** : Inclure les ingrédients fitness/healthy (whey, oats, Greek yogurt, etc.)
- **VALIDATE** : `python -c "import json; d=json.load(open('scripts/data/ingredient_translations.json')); print(f'{len(d)} translations'); assert len(d) >= 250"`

### Task 3 : CREATE `scripts/recipe_sources/base.py`

- **IMPLEMENT** :
  - Dataclass `RawRecipe` (voir interface ci-dessus)
  - ABC `RecipeSource` avec `fetch_recipes()` et `name` property
  - Fonctions utilitaires extraites de `import_themealdb.py` :
    - `auto_correct_portions(row: dict) -> dict`
    - `has_sane_macro_ratios(row: dict) -> bool`
    - `detect_allergens(ingredients: list[dict]) -> list[str]`
    - `parse_measure(measure_str: str) -> tuple[float, str]`
    - `build_recipe_row(raw: RawRecipe) -> dict` — convertit RawRecipe → dict DB
    - `translate_ingredient(name: str, translations: dict) -> str`
    - `normalize_unit(unit: str) -> str` — tbsp→ml, cup→ml, oz→g
  - Constantes : `ALLERGEN_KEYWORDS`, `UNIT_CONVERSIONS`, `MIN_SANE_CALORIES=150`, `MAX_SANE_CALORIES=900`
- **PATTERN** : Extraire de `scripts/import_themealdb.py` lignes 163-446
- **IMPORTS** : `unicodedata`, `re`, `math`, `dataclasses`, `abc`, `httpx`
- **GOTCHA** : Ne PAS importer de LLM. Ne PAS importer depuis `src/` dans ce fichier (les src imports restent dans l'orchestrateur).
- **VALIDATE** : `python -c "from scripts.recipe_sources.base import RecipeSource, RawRecipe; print('OK')"`

### Task 4 : CREATE `scripts/recipe_sources/__init__.py`

- **IMPLEMENT** : Exporter tous les adapteurs + `RecipeSource` + `RawRecipe`
- **VALIDATE** : `python -c "from scripts.recipe_sources import RecipeSource; print('OK')"`

### Task 5 : CREATE adapteurs API (3 fichiers)

#### `scripts/recipe_sources/spoonacular.py`
- **IMPLEMENT** : `SpoonacularSource(RecipeSource)` avec `fetch_recipes()`
  - `complexSearch` avec filtres macro
  - Parse `extendedIngredients` → `RawRecipe`
  - Traduction EN→FR via `ingredient_translations.json`
  - Rate limit : `await asyncio.sleep(0.5)` entre requêtes
- **GOTCHA** : `SPOONACULAR_API_KEY` optionnel — skip gracefully si absent

#### `scripts/recipe_sources/edamam.py`
- **IMPLEMENT** : `EdamamSource(RecipeSource)` avec `fetch_recipes()`
  - Endpoint v2 avec filtres `health=`, `cuisineType=`, `mealType=`
  - Parse `ingredientLines` → regex pour extraire quantité/unité/nom
- **GOTCHA** : `EDAMAM_APP_ID` + `EDAMAM_APP_KEY` requis — skip si absent

#### `scripts/recipe_sources/themealdb_adapter.py`
- **IMPLEMENT** : `TheMealDBSource(RecipeSource)` — thin wrapper
  - Réutilise la logique de `scripts/import_themealdb.py`
  - Pas de clé API nécessaire
- **GOTCHA** : Ne pas dupliquer les recettes déjà importées par l'ancien script

- **VALIDATE** (pour les 3) : `python -c "from scripts.recipe_sources.spoonacular import SpoonacularSource; print('OK')"`

### Task 6 : CREATE adapteurs scraping FR (3 fichiers)

#### `scripts/recipe_sources/marmiton.py`
- **IMPLEMENT** : `MarmitonSource(RecipeSource)` avec `fetch_recipes()`
  - Recherche par mot-clé : `?aqt={query}`
  - Parse HTML page recette : titre, ingrédients, instructions
  - Détection `meal_type` par catégorie/tags
  - Rate limit 1 req / 2 sec

#### `scripts/recipe_sources/sept_cinquante_g.py`
- **IMPLEMENT** : `SeptCinquanteGSource(RecipeSource)` — même pattern que Marmiton

#### `scripts/recipe_sources/cuisine_az.py`
- **IMPLEMENT** : `CuisineAZSource(RecipeSource)` — même pattern

- **IMPORTS** : `httpx`, `bs4.BeautifulSoup`
- **GOTCHA** : Ajouter `User-Agent: Mozilla/5.0 (...)` header. HTML fragile — try/except sur chaque page. Si parsing échoue → skip recette, log warning.
- **VALIDATE** : `python -c "from scripts.recipe_sources.marmiton import MarmitonSource; print('OK')"`

### Task 7 : CREATE adapteurs scraping EN (2 fichiers)

#### `scripts/recipe_sources/bbc_good_food.py`
- **IMPLEMENT** : `BBCGoodFoodSource(RecipeSource)`
  - Recherche "healthy" + scraping macros affichées pour pré-filtre
  - Traduction EN→FR

#### `scripts/recipe_sources/allrecipes.py`
- **IMPLEMENT** : `AllRecipesSource(RecipeSource)`
  - Parsing JSON-LD `<script type="application/ld+json">` (plus fiable que HTML)
  - Traduction EN→FR

- **VALIDATE** : `python -c "from scripts.recipe_sources.bbc_good_food import BBCGoodFoodSource; print('OK')"`

### Task 8 : CREATE `scripts/import_recipes.py` (orchestrateur)

- **IMPLEMENT** : CLI principal qui :
  1. Charge les adapteurs demandés (ou tous)
  2. Fetch les recettes brutes (`RawRecipe`)
  3. Traduit EN→FR si nécessaire
  4. Build recipe rows
  5. `off_validate_recipe()` sur chaque recette
  6. Post-filtre macros (`has_sane_macro_ratios()` + filtres CLI)
  7. `auto_correct_portions()` si > 900 kcal
  8. Upsert dans Supabase
  9. Log résumé final (fetched / validated / filtered / upserted / failed)

- **CLI arguments** :
  ```
  --source {all,spoonacular,edamam,themealdb,marmiton,750g,cuisineaz,bbcgoodfood,allrecipes}
  --limit INT          (par source, default 50)
  --dry-run            (validate only, no DB write)
  --max-fat-pct FLOAT  (post-OFF filter, default 35)
  --min-protein-pct FLOAT (post-OFF filter, default 15)
  --meal-type {dejeuner,diner,petit-dejeuner,collation}  (filter)
  --diet-type {omnivore,végétarien,vegan}  (filter)
  --query STR          (search keyword, e.g. "poulet grillé", "high protein")
  ```

- **PATTERN** : Suivre `scripts/import_themealdb.py` pour la structure main()
- **IMPORTS** : `argparse`, `asyncio`, `logging`, `json`, `httpx`, `src.clients.get_supabase_client`, `src.nutrition.openfoodfacts_client.off_validate_recipe`
- **GOTCHA** : Sources sans clé API → skip avec warning. `--dry-run` doit quand même appeler `off_validate_recipe()` pour valider.
- **VALIDATE** : `PYTHONPATH=. python scripts/import_recipes.py --source themealdb --dry-run --limit 3`

### Task 9 : CREATE `tests/test_recipe_sources.py`

- **IMPLEMENT** : Tests unitaires pour les fonctions de `base.py` et parsing
  - `test_parse_measure_grams()` — "200 g de poulet" → (200, "g")
  - `test_parse_measure_pieces()` — "3 tomates" → (3, "pièces")
  - `test_parse_measure_cups()` — "1 cup flour" → (240, "ml")
  - `test_parse_measure_tbsp()` — "2 tbsp oil" → (30, "ml")
  - `test_parse_measure_french()` — "1 c. à soupe" → (15, "ml")
  - `test_translate_ingredient()` — "chicken breast" → "blanc de poulet"
  - `test_translate_ingredient_unknown()` — "gochujang" → "gochujang" (inchangé)
  - `test_normalize_unit()` — "tablespoon" → "ml", "ounce" → "g"
  - `test_build_recipe_row()` — structure complète avec tous les champs
  - `test_has_sane_macro_ratios_accepts_balanced()` — fat 25%, protein 30% → True
  - `test_has_sane_macro_ratios_rejects_high_fat()` — fat 50% → False
  - `test_has_sane_macro_ratios_rejects_low_protein()` — protein 5% → False
  - `test_auto_correct_portions()` — 1200 kcal → divisé à ~500 kcal
  - `test_detect_allergens()` — "beurre de cacahuète" → ["arachides"]
  - `test_raw_recipe_dataclass()` — RawRecipe creation and fields
- **PATTERN** : Suivre `tests/test_portion_optimizer.py` pour les fixtures
- **VALIDATE** : `python -m pytest tests/test_recipe_sources.py -x -q`

### Task 10 : Exécuter les imports

```bash
# 1. Vérifier les clés API dans .env
# 2. Dry run toutes sources (celles sans clé sont skippées)
PYTHONPATH=. python scripts/import_recipes.py --dry-run --limit 5

# 3. Import par source avec filtres macro
PYTHONPATH=. python scripts/import_recipes.py --source spoonacular --limit 100 --max-fat-pct 30 --min-protein-pct 20
PYTHONPATH=. python scripts/import_recipes.py --source edamam --limit 80 --query "healthy lunch" --max-fat-pct 30
PYTHONPATH=. python scripts/import_recipes.py --source marmiton --limit 100 --query "poulet grillé salade légumes"
PYTHONPATH=. python scripts/import_recipes.py --source 750g --limit 60 --query "recette légère protéinée"
PYTHONPATH=. python scripts/import_recipes.py --source cuisineaz --limit 60 --query "recette fitness"
PYTHONPATH=. python scripts/import_recipes.py --source bbcgoodfood --limit 80 --query "healthy high protein"
PYTHONPATH=. python scripts/import_recipes.py --source allrecipes --limit 60 --query "lean protein meals"
PYTHONPATH=. python scripts/import_recipes.py --source themealdb --limit 50

# 4. Import ciblé vegan/végétarien
PYTHONPATH=. python scripts/import_recipes.py --source edamam --limit 50 --diet-type vegan --query "vegan protein"
PYTHONPATH=. python scripts/import_recipes.py --source marmiton --limit 30 --diet-type végétarien --query "végétarien protéiné"
```

### Task 11 : Vérification post-import

```bash
# Distribution des macros après import
PYTHONPATH=. python -c "
from src.clients import get_supabase_client
sb = get_supabase_client()
resp = sb.table('recipes').select('calories_per_serving,protein_g_per_serving,fat_g_per_serving,meal_type,source').in_('meal_type', ['dejeuner','diner']).execute()
low, mid, high = 0, 0, 0
sources = {}
for r in resp.data:
    cal = float(r.get('calories_per_serving') or 0)
    if cal <= 0: continue
    fat_ratio = (float(r.get('fat_g_per_serving') or 0) * 9) / cal
    if fat_ratio < 0.25: low += 1
    elif fat_ratio < 0.35: mid += 1
    else: high += 1
    src = r.get('source', 'unknown')
    sources[src] = sources.get(src, 0) + 1
total = low + mid + high
print(f'Low-fat (<25%): {low} ({100*low/total:.0f}%)')
print(f'Mid-fat (25-35%): {mid} ({100*mid/total:.0f}%)')
print(f'High-fat (>35%): {high} ({100*high/total:.0f}%)')
print(f'Total: {total}')
print(f'Par source: {sources}')
"
```

**Cible** : ≥40% low-fat, ≤30% high-fat (vs 31%/44% actuellement)

### Task 12 : Lint + tests complets

```bash
ruff format scripts/ tests/ && ruff check scripts/ tests/
python -m pytest tests/ -x -q
```

---

## TESTING STRATEGY

### Unit Tests (Task 9)
- Parsing de quantités françaises et anglaises (regex)
- Traduction EN→FR
- Conversion d'unités (cups, oz, tbsp → g/ml)
- Construction de recipe row (tous les champs)
- Post-filtre macros (accept/reject)
- Auto-correction portions
- Détection allergènes
- Dataclass RawRecipe

### Integration (Tasks 10-11)
- `--dry-run` mode valide le pipeline complet sans écriture DB
- Vérification post-import de la distribution macros
- Comptage par source

### Edge Cases
- Ingrédient sans traduction → fallback nom anglais
- Quantité vague ("un peu de", "a pinch") → quantité par défaut (5g)
- Recette > 900 kcal → auto-division portions
- OFF ne matche aucun ingrédient → recette skippée (`off_validated=False`)
- API rate limit atteint → graceful stop avec résumé partiel
- Clé API absente → source skippée avec warning
- HTML parsing fail → recette skippée, log warning
- Doublon (même recette de 2 sources) → upsert résout via `name_normalized`

---

## VALIDATION COMMANDS

### Level 1 : Syntax & Style
```bash
ruff format scripts/ tests/ && ruff check scripts/ tests/
```

### Level 2 : Unit Tests
```bash
python -m pytest tests/test_recipe_sources.py -x -q
python -m pytest tests/test_scripts_no_llm.py -x -q  # Rule 10 check
```

### Level 3 : Dry Run
```bash
PYTHONPATH=. python scripts/import_recipes.py --source themealdb --dry-run --limit 3
```

### Level 4 : Post-Import Verification
```bash
# Macro distribution check (Task 11)
# Total recipe count + source breakdown
```

---

## ACCEPTANCE CRITERIA

- [ ] Architecture modulaire : 1 orchestrateur + 8 adapteurs source
- [ ] `RecipeSource` ABC dans `base.py` avec fonctions utilitaires partagées
- [ ] `ingredient_translations.json` avec ≥250 traductions EN→FR
- [ ] `beautifulsoup4` + `lxml` ajoutés aux dépendances
- [ ] 3 adapteurs API (Spoonacular, Edamam, TheMealDB)
- [ ] 3 adapteurs scraping FR (Marmiton, 750g, Cuisine AZ)
- [ ] 2 adapteurs scraping EN (BBC Good Food, AllRecipes)
- [ ] CLI avec `--source`, `--limit`, `--dry-run`, `--max-fat-pct`, `--min-protein-pct`
- [ ] Tests unitaires pour parsing, traduction, filtering
- [ ] `--dry-run` mode fonctionnel
- [ ] ≥200 recettes importées et OFF-validées
- [ ] Distribution macro améliorée : ≥40% low-fat pour dejeuner/diner
- [ ] Aucune recette importée avec `off_validated=False`
- [ ] Rule 10 respectée (pas d'import LLM)
- [ ] `ruff format` + `ruff check` passent
- [ ] Tous les tests existants passent toujours

## COMPLETION CHECKLIST

- [ ] Tasks 1-9 implémentées
- [ ] Tasks 10-11 exécutées avec succès
- [ ] Task 12 validation complète
- [ ] Seam review : `off_validate_recipe()` appelé correctement, upsert conflict key correct
- [ ] Pas de régression sur les recettes existantes
- [ ] Sources sans clé API gracefully skippées

---

## NOTES

- **Priorité** : Ce plan est en standby — LP Optimizer v2 est prioritaire.
- **Spoonacular plan gratuit** : 150 points/jour. `complexSearch` = 1 pt. Donc ~75 recettes complètes par jour max (search + detail).
- **Edamam plan gratuit** : 10k req/mois. Largement suffisant.
- **Idempotence** : L'upsert sur `name_normalized,meal_type` garantit qu'un re-run ne crée pas de doublons.
- **Seuil de couverture OFF** : Si <100% des ingrédients matchent, la recette est rejetée (`off_validated=False`). C'est le comportement existant de `off_validate_recipe()`.
- **Pas de modification de `src/`** : Le pipeline utilise uniquement les fonctions existantes. Aucun changement dans le code source principal.
- **Refactor de `import_themealdb.py`** : L'ancien script reste intact. Le nouvel adapteur `themealdb_adapter.py` est un wrapper indépendant. On pourra supprimer l'ancien script après validation.
