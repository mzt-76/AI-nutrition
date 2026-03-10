# Feature: v2f — LP Optimizer v2 : MILP per-ingredient avec rôles culinaires

## User Story

En tant qu'utilisateur du meal-planning,
je veux que l'optimiseur ajuste les quantités d'ingrédients individuellement (pas la recette entière),
afin que les macros soient précis sans sacrifier la cohérence culinaire de la recette.

## Problem Statement

Le LP v1 (`portion_optimizer.py`) applique UN scale factor par recette entière. Si une recette a 40% de fat, scaler à ×0.5 réduit tout proportionnellement — le ratio fat reste 40%. Le seul moyen actuel de réduire le fat est le `fat_rebalancer.py` (heuristique post-LP basée sur des mots-clés), qui est déconnecté de l'optimisation mathématique et produit des résultats sous-optimaux.

**Conséquence** : Le système est limité lors de son optimisation pour atteidnre les macros cibles de l'utilsiateur

## Solution Statement

Remplacer le LP v1 (1 variable/recette) + fat_rebalancer (heuristique) par un **MILP unique** :
- **1 variable par ingrédient** — chaque ingrédient a son propre scale factor
- **Macros OFF réels** — le solveur utilise les `nutrition_per_100g` de chaque ingrédient
- **Rôles culinaires** — les ingrédients sont tagués (protein, starch, vegetable, fat_source, unknown) pour définir les bornes de scaling et les contraintes de cohérence
- **Items discrets** — œufs, avocats, etc. sont des variables entières (MILP)
- **Contrainte de divergence** — les groupes ne peuvent pas diverger au-delà de 2× entre eux
- Performance : ~15-20 variables, résolu en <10ms par `scipy.optimize.milp`

## Feature Metadata

**Feature Type**: Enhancement (remplacement majeur)
**Estimated Complexity**: High
**Primary Systems Affected**: `src/nutrition/portion_optimizer.py`, `src/nutrition/fat_rebalancer.py`, `src/nutrition/meal_plan_optimizer.py`, `skills/meal-planning/scripts/generate_day_plan.py`
**Dependencies**: scipy>=1.9 (milp disponible) — version actuelle 1.15.2 ✅

---

## CONTEXT REFERENCES

### Fichiers à lire OBLIGATOIREMENT avant d'implémenter

- `src/nutrition/portion_optimizer.py` (289 lignes) — LP v1 complet. Fonctions : `_extract_recipe_macros()`, `optimize_day_portions()`, `apply_scale_factor()`. Constants : `WEIGHT_PROTEIN=2.0`, `WEIGHT_FAT=2.0`, `WEIGHT_CALORIES=1.0`, `WEIGHT_CARBS=0.5`, `WEIGHT_MEAL_BALANCE=1.5`
- `src/nutrition/fat_rebalancer.py` (231 lignes) — Heuristique de réduction fat. `HIGH_FAT_INGREDIENTS` (24 entrées), `rebalance_high_fat_day()`. **Orphelée** — jamais appelée dans le code actif, sera supprimée.
- `src/nutrition/meal_plan_optimizer.py` (87 lignes) — Exporte `MIN_SCALE_FACTOR=0.50`, `MAX_SCALE_FACTOR=3.00`, `generate_adjustment_summary()`, re-exporte `round_quantity_smart`, `FAT_SURPLUS_THRESHOLD`. `generate_adjustment_summary()` est **inutilisée**.
- `src/nutrition/quantity_rounding.py` (81 lignes) — `round_quantity_smart()` : arrondit pièces→entier, g/ml→entier, épices<10g→1 décimale. **Réutilisé tel quel**.
- `src/nutrition/openfoodfacts_client.py` (lignes 36-190) — `_INGREDIENT_CATEGORIES` (96 entrées), `_PIECE_WEIGHTS` (27 entrées, les items discrets), `_ML_TO_G_DENSITY` (12 entrées), `_unit_to_multiplier()`, `normalize_ingredient_name()`, `_get_ingredient_category()` (longest-first substring matching).
- `skills/meal-planning/scripts/generate_day_plan.py` (lignes 521-627) — `scale_portions()` : appelle `optimize_day_portions()` puis `apply_scale_factor()`. C'est le **seul caller actif** des deux fonctions.
- `src/nutrition/portion_scaler.py` — Importe `MIN_SCALE_FACTOR`, `MAX_SCALE_FACTOR` depuis `meal_plan_optimizer`. Utilise dans `calculate_scale_factor()`.
- `tests/test_portion_optimizer.py` (674 lignes) — 30+ tests : `TestExtractRecipeMacros`, `TestOptimizeDayPortions`, `TestApplyScaleFactor`. Patterns : fixtures macro `CHICKEN/RICE/BROCCOLI`, `_make_recipe()`, `pytest.approx()`.
- `tests/test_portion_scaler.py` (271 lignes) — 4 classes de tests, importe `MIN_SCALE_FACTOR`.

### Fichiers créés

- `src/nutrition/ingredient_roles.py` — Table INGREDIENT_ROLES + fonction de tagging
- `src/nutrition/portion_optimizer_v2.py` — MILP per-ingredient optimizer
- `tests/test_ingredient_roles.py` — Tests du tagging
- `tests/test_portion_optimizer_v2.py` — Tests du MILP

### Fichiers modifiés

- `src/nutrition/portion_optimizer.py` — Remplacé par v2 (ancien code supprimé ou gardé comme fallback)
- `src/nutrition/meal_plan_optimizer.py` — Mise à jour des imports/exports
- `skills/meal-planning/scripts/generate_day_plan.py` — Appelle le nouvel optimizer
- `tests/test_portion_optimizer.py` — Adapté pour le nouveau module

### Fichiers supprimés

- `src/nutrition/fat_rebalancer.py` — Remplacé par le MILP. Orphelé (jamais appelé dans le code actif).

### Documentation pertinente

- scipy.optimize.milp API : `milp(c, constraints, integrality, bounds, options)`
  - `constraints` : `LinearConstraint(A, lb, ub)` — `lb <= A @ x <= ub`
  - `integrality` : 0=continu, 1=entier
  - `bounds` : `Bounds(lb, ub)` ou list de tuples
  - Conversion depuis linprog : `A_eq @ x = b_eq` → `LinearConstraint(A_eq, b_eq, b_eq)`

### Patterns à suivre

**Naming** : `UPPER_SNAKE_CASE` pour constantes, `_prefix` pour helpers privés
**Logging** : `logger = logging.getLogger(__name__)`, `logger.info()`, `logger.warning()`
**Imports** : stdlib → third-party → `src.nutrition.*` → constants → fonctions
**Type hints** : Stricts sur tous les args et retours
**Docstrings** : PEP 257 + Google Style (Args, Returns, Raises, References)
**Tests** : Classes par fonction, `pytest.approx()`, `pytest.raises(match=...)`, `_make_recipe()` fixture

---

## DESIGN DÉTAILLÉ

### Formulation MILP

**Variables** : 1 par ingrédient scalable + variables de déviation macro

Pour une journée de 3 recettes avec respectivement 5, 4, 3 ingrédients :
- Ingrédients scalables (non-fixed) : ~9 (les fixed n'ont pas de variable)
- Variables de déviation : 8 (cal+, cal-, prot+, prot-, fat+, fat-, carbs+, carbs-)
- Variables de déviation per-meal : 2 × 3 (optionnel)
- Total : ~23 variables

```
Variables:
  x_0..x_k     = scale factors par ingrédient scalable (continu ou entier)
  d_cal+, d_cal-  = déviation calories
  d_prot+, d_prot- = déviation protéines
  d_fat+, d_fat-   = déviation fat
  d_carbs+, d_carbs- = déviation carbs
  (optionnel) dm_r+, dm_r- = déviation calories par recette

Objectif: Minimiser
  W_cal  * (d_cal+ + d_cal-)
+ W_prot * (d_prot+ + d_prot-)
+ W_fat  * (d_fat+ + d_fat-)
+ W_carbs * (d_carbs+ + d_carbs-)
+ W_meal * sum(dm_r+ + dm_r-)

Contraintes d'égalité (macros journaliers):
  Pour chaque macro m ∈ {cal, prot, fat, carbs}:
    sum(x_i * nutrition_per_100g_i[m] * base_multiplier_i) - d_m+ + d_m- = target_m
    (les ingrédients fixed contribuent comme constantes, soustraites du target)

Contraintes d'égalité (macros per-meal, optionnel):
  Pour chaque recette r:
    sum(x_i * cal_i * mult_i, pour i dans recette r) - dm_r+ + dm_r- = meal_target_r
    (ajusté pour les ingrédients fixed de cette recette)

Contraintes de divergence (cohérence culinaire):
  UNIQUEMENT pour les paires (protein↔starch, protein↔vegetable, starch↔vegetable).
  fat_source est EXEMPT — libre de ses propres bornes.
  Pour chaque paire (g1, g2) dans DIVERGENCE_PAIRS, dans la même recette :
    sum(x_i ∈ g1) * |g2| ≤ MAX_DIVERGENCE * sum(x_j ∈ g2) * |g1|
    sum(x_j ∈ g2) * |g1| ≤ MAX_DIVERGENCE * sum(x_i ∈ g1) * |g2|

Bornes:
  x_i ∈ [role_min, role_max] selon le rôle de l'ingrédient
  d_*, dm_* ∈ [0, +∞)

Intégrité:
  x_i est INTEGER si l'ingrédient utilise une unité discrète (pièces, oeufs, tranches)
  x_i est CONTINU sinon
```

### Rôles et bornes

| Rôle | Min | Max | Exemples |
|------|-----|-----|----------|
| `protein` | 0.5 | 2.0 | poulet, saumon, tofu, œuf, bœuf |
| `starch` | 0.3 | 2.5 | riz, pâtes, pain, quinoa, pomme de terre |
| `vegetable` | 0.7 | 1.5 | brocoli, tomate, courgette, épinard |
| `fat_source` | 0.2 | 1.5 | huile, beurre, crème, fromage, avocat |
| `unknown` | 0.75 | 1.25 | ingrédients non reconnus (±25% symétrique) |

**Fixed** : épices, sauces, garnitures → pas de variable LP, contribuent comme constantes.

### Contrainte de divergence

`MAX_GROUP_DIVERGENCE = 2.0`

La divergence s'applique **uniquement entre les paires structurelles** :
- protein ↔ starch
- protein ↔ vegetable
- starch ↔ vegetable

**`fat_source` est EXEMPT** de la contrainte de divergence. Raison : les sources de fat (huile, beurre, fromage) sont des "ajustements" indépendants du cœur de la recette. Le solveur doit pouvoir réduire l'huile à ×0.2 tout en gardant le poulet à ×1.5, ce qui est culinairement logique (moins d'huile = recette plus légère, pas dénaturée). Forcer la divergence protein↔fat_source empêcherait exactement l'optimisation qu'on cherche.

`DIVERGENCE_PAIRS: list[tuple[str, str]] = [("protein", "starch"), ("protein", "vegetable"), ("starch", "vegetable")]`

Pour chaque recette, si le scaling moyen du groupe `protein` est 1.5×, le scaling moyen du groupe `starch` ne peut pas être en dessous de 0.75× (1.5/2.0) ni au-dessus de 3.0× (1.5×2.0, mais cappé par les bornes du rôle).

**Linéarisation** : Pour chaque paire (g1, g2) dans `DIVERGENCE_PAIRS`, dans la même recette :
```
sum(x_i ∈ g1) * |g2| ≤ MAX_DIVERGENCE * sum(x_j ∈ g2) * |g1|
sum(x_j ∈ g2) * |g1| ≤ MAX_DIVERGENCE * sum(x_i ∈ g1) * |g2|
```
Ce sont des contraintes linéaires (inequality), compatibles avec le MILP.

Cela réduit considérablement le risque d'infeasibility — le cas problématique "1 protein + 3 fat_source" ne génère plus aucune contrainte de divergence.

### Items discrets

Les ingrédients dont l'unité est dans `DISCRETE_UNITS` ont un traitement spécial : la **variable LP représente la quantité finale en pièces** (pas un scale factor). C'est la seule approche compatible avec `integrality=1` de scipy milp.

**Pourquoi** : scipy milp impose que la variable elle-même soit entière. Si la variable était un scale factor (ex: 0.5, 1.0, 1.5), on ne pourrait pas exprimer "le résultat doit être un nombre entier d'œufs". En faisant de la variable la quantité finale, l'entier représente directement le nombre de pièces.

**Calcul des bornes pour items discrets** :
```python
base_qty = 2  # pièces (ex: 2 œufs dans la recette originale)
role_min, role_max = 0.5, 2.0
int_lb = max(1, math.floor(base_qty * role_min))   # floor(1.0) = 1
int_ub = math.ceil(base_qty * role_max)              # ceil(4.0) = 4
# Variable x_i ∈ {1, 2, 3, 4}  (entier)
# Contribution macro = x_i * weight_per_piece * nutrition_per_100g / 100
# (où weight_per_piece vient de _PIECE_WEIGHTS, ex: 60g pour un œuf)
```

**Pour les items continus** (poulet en grammes), la variable reste un scale factor classique :
```python
base_qty = 150  # grammes
role_min, role_max = 0.5, 2.0
# Variable x_i ∈ [0.5, 2.0]  (continu)
# Contribution macro = x_i * base_multiplier * nutrition_per_100g
# (où base_multiplier = _unit_to_multiplier(150, "g", "poulet") = 1.5)
```

Les deux types de variables coexistent dans le même MILP avec des `integrality` différentes (1 vs 0).

### Fallback

Si le MILP échoue (infeasible), fallback vers le comportement v1 : scale factor uniforme basé sur les calories.

---

## CALLERS ET IMPACTS

### Callers directs à modifier

| Fonction | Fichier | Ligne | Changement |
|----------|---------|-------|------------|
| `scale_portions()` | `generate_day_plan.py` | 586 | Appelle `optimize_day_portions_v2()` au lieu de `optimize_day_portions()` |
| `scale_portions()` | `generate_day_plan.py` | 613 | Appelle `apply_scale_factors_v2()` (pluriel — retourne des scale factors par ingrédient, pas un seul par recette) |

### Imports à mettre à jour

| Fichier | Import actuel | Nouvel import |
|---------|--------------|---------------|
| `generate_day_plan.py` | `from src.nutrition.portion_optimizer import optimize_day_portions, apply_scale_factor` | `from src.nutrition.portion_optimizer_v2 import optimize_day_portions_v2, apply_ingredient_scale_factors` |
| `meal_plan_optimizer.py` | Re-export `_rebalance_high_fat_day`, `FAT_SURPLUS_THRESHOLD` | Supprimer ces re-exports |
| `portion_scaler.py` | `MIN_SCALE_FACTOR, MAX_SCALE_FACTOR` | Inchangé (ces constantes restent dans `meal_plan_optimizer.py`) |

### Fichiers à supprimer

| Fichier | Raison |
|---------|--------|
| `src/nutrition/fat_rebalancer.py` | Orphelé (jamais appelé), remplacé par MILP |

### Fichiers inchangés

| Fichier | Pourquoi |
|---------|----------|
| `src/nutrition/quantity_rounding.py` | Réutilisé tel quel par `apply_ingredient_scale_factors()` |
| `src/nutrition/openfoodfacts_client.py` | Consommé, pas modifié |
| `src/nutrition/portion_scaler.py` | Utilise `MIN/MAX_SCALE_FACTOR` — pas affecté par le changement d'optimizer |

---

## INGREDIENT_ROLES — Table exhaustive

La table couvre 95%+ des ingrédients des 547 recettes (1088 ingrédients uniques identifiés). Le matching est par **substring** (longest-first, comme `_get_ingredient_category()`).

### Protein (~40 entrées)

```python
# Volaille
"poulet": "protein", "dinde": "protein", "canard": "protein",
"blanc de poulet": "protein", "cuisse de poulet": "protein",
"escalope de dinde": "protein", "filet de dinde": "protein",
# Viande rouge
"boeuf": "protein", "bœuf": "protein", "veau": "protein",
"agneau": "protein", "porc": "protein", "steak": "protein",
"filet mignon": "protein",
# Poisson & fruits de mer
"saumon": "protein", "cabillaud": "protein", "thon": "protein",
"daurade": "protein", "crevette": "protein", "gambas": "protein",
"moule": "protein", "calamar": "protein", "truite": "protein",
"sardine": "protein", "maquereau": "protein", "colin": "protein",
"pavé de saumon": "protein", "filet de cabillaud": "protein",
# Protéines végétales
"tofu": "protein", "tempeh": "protein", "seitan": "protein",
"protéine": "protein",  # protéine de pois, whey, etc.
# Œufs (aussi discrets)
"oeuf": "protein", "œuf": "protein", "oeufs": "protein", "œufs": "protein",
# Légumineuses (protéine + carbs, taggé protein car c'est leur rôle principal dans nos recettes)
"lentille": "protein", "pois chiche": "protein", "haricot rouge": "protein",
"haricot noir": "protein", "haricot blanc": "protein", "edamame": "protein",
"fève": "protein",
```

### Starch (~25 entrées)

```python
# Céréales & grains
"riz": "starch", "pâtes": "starch", "pasta": "starch",
"spaghetti": "starch", "penne": "starch", "fusilli": "starch",
"tagliatelle": "starch", "nouille": "starch", "vermicelle": "starch",
"couscous": "starch", "quinoa": "starch", "boulgour": "starch",
"semoule": "starch", "polenta": "starch", "orge": "starch",
"avoine": "starch", "flocon": "starch",  # flocons d'avoine
"muesli": "starch", "granola": "starch",
# Pain & féculents
"pain": "starch", "tortilla": "starch", "galette": "starch",
"pomme de terre": "starch", "patate douce": "starch",
"patate": "starch", "igname": "starch",
"farine": "starch", "maïs": "starch",
"wrap": "starch", "naan": "starch", "pita": "starch",
```

### Vegetable (~35 entrées)

```python
# Légumes courants
"tomate": "vegetable", "courgette": "vegetable", "aubergine": "vegetable",
"poivron": "vegetable", "brocoli": "vegetable", "chou-fleur": "vegetable",
"épinard": "vegetable", "salade": "vegetable", "laitue": "vegetable",
"roquette": "vegetable", "mâche": "vegetable",
"concombre": "vegetable", "céleri": "vegetable", "carotte": "vegetable",
"oignon": "vegetable", "échalote": "vegetable", "poireau": "vegetable",
"fenouil": "vegetable", "navet": "vegetable", "radis": "vegetable",
"betterave": "vegetable", "asperge": "vegetable",
"haricot vert": "vegetable", "petit pois": "vegetable",
"champignon": "vegetable", "chou": "vegetable",
"pak choi": "vegetable", "bok choy": "vegetable",
"artichaut": "vegetable", "endive": "vegetable",
"courge": "vegetable", "butternut": "vegetable", "potiron": "vegetable",
"potimarron": "vegetable",
# Fruits utilisés comme légumes dans les recettes salées
"olive": "vegetable", "cornichon": "vegetable",
"poivron rouge": "vegetable", "poivron vert": "vegetable",
```

### Fat Source (~25 entrées)

```python
# Huiles
"huile": "fat_source", "huile d'olive": "fat_source",
"huile de coco": "fat_source", "huile de sésame": "fat_source",
"huile de colza": "fat_source",
# Beurre & crème
"beurre": "fat_source", "margarine": "fat_source",
"crème": "fat_source", "crème fraîche": "fat_source",
"crème liquide": "fat_source", "lait de coco": "fat_source",
# Fromage (high-fat dairy)
"fromage": "fat_source", "parmesan": "fat_source",
"emmental": "fat_source", "gruyère": "fat_source",
"mozzarella": "fat_source", "feta": "fat_source",
"cheddar": "fat_source", "chèvre": "fat_source",
"ricotta": "fat_source", "mascarpone": "fat_source",
# Oléagineux
"avocat": "fat_source", "noix": "fat_source",
"amande": "fat_source", "noisette": "fat_source",
"cacahuète": "fat_source", "pistache": "fat_source",
"noix de cajou": "fat_source",
"beurre de cacahuète": "fat_source", "tahini": "fat_source",
"graine de tournesol": "fat_source", "graine de lin": "fat_source",
"graine de chia": "fat_source", "graine de courge": "fat_source",
# Viandes grasses
"bacon": "fat_source", "lardons": "fat_source",
"saucisse": "fat_source", "chorizo": "fat_source",
```

### Fixed (~30 entrées — épices, sauces, garnitures)

```python
# Épices & aromates
"sel": "fixed", "poivre": "fixed", "cumin": "fixed",
"paprika": "fixed", "curcuma": "fixed", "curry": "fixed",
"cannelle": "fixed", "muscade": "fixed", "piment": "fixed",
"herbes de provence": "fixed", "origan": "fixed", "thym": "fixed",
"romarin": "fixed", "basilic": "fixed", "persil": "fixed",
"coriandre": "fixed", "menthe": "fixed", "ciboulette": "fixed",
"aneth": "fixed", "estragon": "fixed", "laurier": "fixed",
"ail": "fixed", "gingembre": "fixed",
# Sauces & condiments
"sauce soja": "fixed", "vinaigre": "fixed", "moutarde": "fixed",
"sauce": "fixed", "ketchup": "fixed", "mayonnaise": "fixed",
"miso": "fixed", "nuoc mam": "fixed", "sauce poisson": "fixed",
"sauce teriyaki": "fixed", "sauce worcestershire": "fixed",
"concentré de tomate": "fixed", "pâte de curry": "fixed",
# Sucrants & assaisonnement liquide
"miel": "fixed", "sirop d'érable": "fixed", "sucre": "fixed",
"jus de citron": "fixed", "citron": "fixed", "citron vert": "fixed",
# Garnitures
"sésame": "fixed", "graines de sésame": "fixed",
"chapelure": "fixed", "levure": "fixed",
# Liquides de cuisson
"eau": "fixed", "bouillon": "fixed",
"vin blanc": "fixed", "vin rouge": "fixed",
"lait": "fixed",  # le lait en petite quantité dans une recette = fixed
```

### Ordre de matching (longest-first)

Le matching doit être **longest-first** pour éviter les faux positifs :
- "haricot vert" → vegetable (pas protein à cause de "haricot")
- "haricot rouge" → protein
- "beurre de cacahuète" → fat_source (pas protein)
- "lait de coco" → fat_source (pas fixed à cause de "lait")
- "pomme de terre" → starch (pas vegetable/fruit)
- "crème fraîche" → fat_source
- "fromage blanc" → protein (exception — pas fat_source)
- "fromage frais" → protein (exception — pas fat_source)

**Exceptions spéciales** (substring matching requires careful ordering) :
```python
ROLE_EXCEPTIONS = {
    "fromage blanc": "protein",   # Override fromage → fat_source
    "fromage frais": "protein",   # Override fromage → fat_source
    "yaourt": "protein",          # Dairy but primarily protein source
    "yogourt": "protein",
    "skyr": "protein",
    "cottage": "protein",
    "blanc d'oeuf": "protein",    # Pure protein
}
```

---

## IMPLEMENTATION PLAN

### Phase 1 : Foundation (Tasks 1-2)
- Créer `ingredient_roles.py` avec la table de tagging et la fonction de lookup
- Tests unitaires du tagging

### Phase 2 : Core MILP (Tasks 3-4)
- Créer `portion_optimizer_v2.py` avec le solveur MILP
- Tests unitaires exhaustifs du MILP

### Phase 3 : Integration (Tasks 5-7)
- Mettre à jour `generate_day_plan.py` pour appeler le nouvel optimizer
- Nettoyer les imports dans `meal_plan_optimizer.py`
- Supprimer `fat_rebalancer.py`

### Phase 4 : Validation (Tasks 8-9)
- Mettre à jour les tests existants
- Validation end-to-end

---

## STEP-BY-STEP TASKS

### Task 1 : CREATE `src/nutrition/ingredient_roles.py`

- **IMPLEMENT** :
  - Dict `INGREDIENT_ROLES: dict[str, str]` — ~155 entrées (voir section INGREDIENT_ROLES ci-dessus)
  - Dict `ROLE_EXCEPTIONS: dict[str, str]` — ~7 exceptions (fromage blanc, yaourt, etc.)
  - Dict `ROLE_BOUNDS: dict[str, tuple[float, float]]` — bornes par rôle
    ```python
    ROLE_BOUNDS: dict[str, tuple[float, float]] = {
        "protein": (0.5, 2.0),
        "starch": (0.3, 2.5),
        "vegetable": (0.7, 1.5),
        "fat_source": (0.2, 1.5),
        "unknown": (0.75, 1.25),
        "fixed": (1.0, 1.0),
    }
    ```
  - Set `DISCRETE_UNITS: set[str]` — unités comptables
    ```python
    DISCRETE_UNITS: set[str] = {
        "pièces", "pièce", "piece", "pieces",
        "tranche", "tranches",
        "oeuf", "oeufs", "œuf", "œufs",
    }
    ```
  - Constante `MAX_GROUP_DIVERGENCE: float = 2.0`
  - Constante `DIVERGENCE_PAIRS: list[tuple[str, str]] = [("protein", "starch"), ("protein", "vegetable"), ("starch", "vegetable")]` — fat_source est EXEMPT
  - Fonction `get_ingredient_role(name: str) -> str` — longest-first substring matching :
    1. Normalize le nom (`normalize_ingredient_name()`)
    2. Check `ROLE_EXCEPTIONS` d'abord (longest-first)
    3. Check `INGREDIENT_ROLES` (longest-first)
    4. Retourne `"unknown"` si aucun match
  - Fonction `is_discrete_unit(unit: str) -> bool` — check si l'unité est discrète
  - Fonction `get_role_bounds(role: str) -> tuple[float, float]` — retourne les bornes

- **PATTERN** : Suivre `_get_ingredient_category()` dans `openfoodfacts_client.py` (lignes 252-259) pour le matching longest-first
- **IMPORTS** : `from src.nutrition.openfoodfacts_client import normalize_ingredient_name`
- **GOTCHA** :
  - Le matching longest-first est CRITIQUE : "haricot vert" (vegetable) doit matcher avant "haricot" (protein)
  - Pré-trier les clés par longueur décroissante au module load (pas à chaque appel)
  - "lait de coco" doit être fat_source, pas "fixed" (à cause de "lait")
  - "fromage blanc" / "fromage frais" doivent être protein, pas fat_source
- **VALIDATE** : `python -c "from src.nutrition.ingredient_roles import get_ingredient_role; print(get_ingredient_role('blanc de poulet')); assert get_ingredient_role('haricot vert') == 'vegetable'; assert get_ingredient_role('haricot rouge') == 'protein'; assert get_ingredient_role('fromage blanc') == 'protein'; assert get_ingredient_role('fromage') == 'fat_source'"`

### Task 2 : CREATE `tests/test_ingredient_roles.py`

- **IMPLEMENT** : Tests exhaustifs du tagging
  - `TestGetIngredientRole` :
    - `test_protein_keywords()` — poulet, saumon, tofu, oeuf, lentille
    - `test_starch_keywords()` — riz, pâtes, quinoa, pomme de terre, pain
    - `test_vegetable_keywords()` — brocoli, tomate, courgette, épinard
    - `test_fat_source_keywords()` — huile, beurre, fromage, avocat, noix
    - `test_fixed_keywords()` — sel, poivre, sauce soja, ail, basilic
    - `test_unknown_fallback()` — ingrédient non reconnu → "unknown"
    - `test_longest_first_matching()` — "haricot vert" → vegetable, "haricot rouge" → protein
    - `test_exceptions_override()` — "fromage blanc" → protein, "yaourt" → protein
    - `test_lait_de_coco_is_fat()` — "lait de coco" → fat_source (pas fixed)
    - `test_accent_normalization()` — "épinard" et "epinard" → même résultat
    - `test_case_insensitive()` — "Poulet" → protein
  - `TestIsDiscreteUnit` :
    - `test_pieces()` — "pièces" → True
    - `test_oeufs()` — "oeufs" → True
    - `test_grams()` — "g" → False
    - `test_ml()` — "ml" → False
  - `TestRoleBounds` :
    - `test_all_roles_have_bounds()`
    - `test_unknown_bounds_symmetric()` — (0.75, 1.25)
    - `test_fixed_bounds_locked()` — (1.0, 1.0)
- **PATTERN** : Suivre `tests/test_portion_optimizer.py` (classes par fonction, `_make_recipe()`)
- **VALIDATE** : `python -m pytest tests/test_ingredient_roles.py -x -q`

### Task 3 : CREATE `src/nutrition/portion_optimizer_v2.py`

- **IMPLEMENT** :

  #### Constantes (réutiliser les mêmes poids que v1)
  ```python
  WEIGHT_PROTEIN = 2.0
  WEIGHT_FAT = 2.0
  WEIGHT_CALORIES = 1.0
  WEIGHT_CARBS = 0.5
  WEIGHT_MEAL_BALANCE = 1.5
  ```

  #### `_prepare_ingredients(recipes: list[dict]) -> list[dict]`
  Pour chaque ingrédient de chaque recette :
  - Extraire `nutrition_per_100g`, `quantity`, `unit`, `name`
  - Calculer `base_multiplier` via `_unit_to_multiplier()`
  - Tagger le rôle via `get_ingredient_role()`
  - Déterminer si discret via `is_discrete_unit()`
  - Calculer les bornes LP (role bounds × base_quantity pour discrets)
  - Retourner une liste plate d'`IngredientVar` (dataclass) avec :
    ```python
    @dataclass
    class IngredientVar:
        recipe_idx: int       # index de la recette dans la liste
        ing_idx: int          # index de l'ingrédient dans la recette
        name: str
        role: str
        base_qty: float       # quantité originale
        unit: str
        base_multiplier: float  # _unit_to_multiplier(base_qty, unit, name)
        nutrition_per_100g: dict  # {calories, protein_g, fat_g, carbs_g}
        is_discrete: bool
        lb: float             # borne basse du scale factor
        ub: float             # borne haute du scale factor
    ```

  #### `optimize_day_portions_v2(recipes, daily_targets, per_meal_targets=None) -> list[dict]`
  **Signature** : `(recipes: list[dict], daily_targets: dict, per_meal_targets: list[float] | None = None) -> list[dict[int, float]]`
  **Retourne** : Liste de dicts `{ing_idx: scale_factor}` — un dict par recette.

  1. Préparer les ingrédients via `_prepare_ingredients()`
  2. Séparer fixed (pas de variable) vs scalable
  3. Calculer la contribution fixe (soustraire des targets)
  4. Construire le MILP :
     - Variables : 1 par ingrédient scalable + 8 déviation macros + (optionnel) 2×n déviation per-meal
     - Objectif : minimiser weighted deviations
     - Contraintes d'égalité : macros journaliers (ajustés pour les fixed)
     - Contraintes d'inégalité : divergence inter-groupes par recette
     - Bornes : selon le rôle
     - Intégrité : 1 pour discrets, 0 pour continus
  5. Résoudre via `scipy.optimize.milp()`
  6. Fallback si infeasible : scale factors uniformes (comme v1)
  7. Log les résultats

  #### `apply_ingredient_scale_factors(recipe: dict, scale_factors: dict[int, float]) -> dict`
  **Signature** : Prend une recette et un dict `{ing_idx: scale_factor}`, retourne la recette scalée.

  Pour chaque ingrédient :
  - Si `ing_idx` dans `scale_factors` :
    - Item continu : `new_qty = base_qty * scale_factor` → arrondir via `round_quantity_smart()`
    - Item discret : `new_qty = scale_factor` (la variable MILP EST la quantité finale en pièces) → arrondir via `round_quantity_smart()` (qui arrondit les pièces à l'entier)
  - Sinon : laisser tel quel (c'est un fixed)
  - Recalculer `scaled_nutrition` depuis les quantités ajustées via `_unit_to_multiplier()` + `nutrition_per_100g`

  **CONTRAT DE SORTIE** (doit matcher exactement `apply_scale_factor()` de v1, lu dans `portion_optimizer.py:232-288`) :
  ```python
  {
      # Toutes les clés de la recette originale (shallow copy)
      "name": str, "instructions": str, "prep_time_minutes": int, ...
      # Clés mises à jour :
      "ingredients": list[dict],       # quantités ajustées par ingrédient
      "scaled_nutrition": {             # ← CLÉ CRITIQUE pour _build_meal_from_scaled_recipe()
          "calories": float,            #    (generate_day_plan.py:110)
          "protein_g": float,
          "carbs_g": float,
          "fat_g": float,
      },
      "ingredient_scale_factors": dict[int, float],  # nouveau — pour debug/logging
  }
  ```
  La fonction `_build_meal_from_scaled_recipe()` (generate_day_plan.py:108-123) lit UNIQUEMENT `name`, `ingredients`, `instructions`, `prep_time_minutes`, et `scaled_nutrition`. Tout le reste est ignoré. Tant que ces 5 clés sont présentes et au bon format, l'intégration fonctionne.

- **IMPORTS** :
  ```python
  import logging
  import math
  from dataclasses import dataclass
  from scipy.optimize import milp, LinearConstraint, Bounds
  from src.nutrition.ingredient_roles import (
      get_ingredient_role, is_discrete_unit, get_role_bounds,
      ROLE_BOUNDS, MAX_GROUP_DIVERGENCE,
  )
  from src.nutrition.openfoodfacts_client import _unit_to_multiplier
  from src.nutrition.quantity_rounding import round_quantity_smart
  ```

- **GOTCHA** :
  - `scipy.optimize.milp` prend `Bounds(lb, ub)` avec des arrays, pas des listes de tuples comme `linprog`
  - `LinearConstraint(A, lb, ub)` — pour égalité : lb=ub. Pour inégalité : lb=-inf, ub=value
  - La contrainte de divergence est **par paire de groupes dans la même recette** — pas globale
  - Les variables de déviation sont TOUJOURS continues (jamais entières)
  - Si tous les ingrédients sont fixed → retourner des scale factors 1.0 pour tous
  - Si une recette n'a qu'un ingrédient scalable → pas de contrainte de divergence
  - `per_meal_targets` : la contribution per-meal inclut les fixed + les scalables de cette recette
  - Le `base_multiplier` convertit la quantité en "combien de portions de 100g" — c'est ce qui multiplie `nutrition_per_100g`

- **VALIDATE** : `python -c "from src.nutrition.portion_optimizer_v2 import optimize_day_portions_v2; print('OK')"`

### Task 4 : CREATE `tests/test_portion_optimizer_v2.py`

- **IMPLEMENT** : Tests exhaustifs du MILP

  #### Fixtures
  ```python
  CHICKEN_PER_100G = {"calories": 165, "protein_g": 31, "fat_g": 3.6, "carbs_g": 0}
  RICE_PER_100G = {"calories": 130, "protein_g": 2.7, "fat_g": 0.3, "carbs_g": 28}
  BROCCOLI_PER_100G = {"calories": 34, "protein_g": 2.8, "fat_g": 0.4, "carbs_g": 7}
  OLIVE_OIL_PER_100G = {"calories": 884, "protein_g": 0, "fat_g": 100, "carbs_g": 0}
  EGG_PER_100G = {"calories": 155, "protein_g": 13, "fat_g": 11, "carbs_g": 1.1}
  ```

  #### `TestPrepareIngredients`
  - `test_tags_correctly()` — poulet→protein, riz→starch, brocoli→vegetable, huile→fat_source
  - `test_discrete_detection()` — œuf en pièces → is_discrete=True
  - `test_bounds_from_role()` — protein ingredient gets [0.5, 2.0]
  - `test_unknown_ingredient()` — ingrédient non reconnu → role=unknown, bounds [0.75, 1.25]
  - `test_fixed_not_in_variables()` — sel, poivre → not in scalable list

  #### `TestOptimizeDayPortionsV2`
  - `test_basic_single_recipe()` — 1 recette, vérifie que les macros sont proches des targets
  - `test_protein_scaling_up()` — target protéine élevé → poulet scalé up, huile scalée down
  - `test_fat_reduction()` — target fat bas → huile fortement réduite, poulet maintenu
  - `test_divergence_constraint()` — vérifie que les groupes ne divergent pas > 2×
  - `test_discrete_eggs_stay_integer()` — 2 œufs → résultat 1, 2, 3, ou 4 (pas 1.7)
  - `test_multi_recipe_day()` — 3 recettes optimisées simultanément
  - `test_per_meal_targets()` — avec per_meal_targets, les calories par repas sont respectées
  - `test_all_fixed_returns_ones()` — recette de sauces/épices seulement → all 1.0
  - `test_single_scalable_ingredient()` — 1 seul ingrédient non-fixed → optimisé normalement
  - `test_infeasible_fallback()` — targets impossibles → fallback uniforme
  - `test_empty_recipes_raises()` — `pytest.raises(ValueError)`
  - `test_zero_calories_target_raises()` — `pytest.raises(ValueError)`
  - `test_performance_under_10ms()` — timing assertion pour 20 variables

  #### `TestMixedVariableFormulation` (CRITIQUE — mitigation risque #1)
  - `test_mixed_recipe_macros_exact()` — Recette mixte : 2 œufs (discret) + 150g riz (continu) + 100g brocoli (continu) + 10ml huile (continu). Le MILP optimise, puis on recalcule manuellement les macros depuis les quantités finales et on vérifie que ça correspond EXACTEMENT aux macros que le MILP a ciblés. Ce test attrape toute erreur de coefficient dans la matrice LP.
  - `test_discrete_coefficient_consistency()` — Pour un item discret (2 œufs), vérifier que le coefficient dans la matrice LP (`weight_per_piece / 100 * nutrition_per_100g`) produit la même contribution macro que `_unit_to_multiplier()` appliqué à la quantité finale.
  - `test_divergence_with_mixed_types()` — Recette avec 2 œufs (discret, protein) + 80g riz (continu, starch). La divergence compare les "scale factors équivalents" : `qty_finale / base_qty` pour les discrets, `x_i` directement pour les continus. Vérifier que la contrainte est respectée.

  #### `TestApplyIngredientScaleFactors`
  - `test_basic_scaling()` — scale factors appliqués correctement
  - `test_fixed_unchanged()` — ingrédients sans scale factor restent identiques
  - `test_discrete_applies_as_quantity()` — pour un item discret, le scale_factor EST la quantité finale (pas un multiplicateur)
  - `test_nutrition_recalculated()` — scaled_nutrition correct après scaling
  - `test_output_format_matches_v1()` — vérifier que le dict retourné contient `name`, `ingredients`, `scaled_nutrition` avec les bonnes clés (contrat `_build_meal_from_scaled_recipe`)
  - `test_no_mutation()` — recette originale non modifiée

- **PATTERN** : Suivre `tests/test_portion_optimizer.py` pour les fixtures et assertions
- **VALIDATE** : `python -m pytest tests/test_portion_optimizer_v2.py -x -q`

### Task 5 : UPDATE `skills/meal-planning/scripts/generate_day_plan.py`

- **IMPLEMENT** : Modifier `scale_portions()` (lignes 521-627) pour appeler le nouvel optimizer

  **Changements** :
  1. Ligne d'import : remplacer
     ```python
     from src.nutrition.portion_optimizer import optimize_day_portions, apply_scale_factor
     ```
     par
     ```python
     from src.nutrition.portion_optimizer_v2 import optimize_day_portions_v2, apply_ingredient_scale_factors
     ```
  2. Appel LP (ligne ~586) : remplacer
     ```python
     factors = optimize_day_portions(lp_recipes, daily_targets, per_meal_targets=per_meal_targets)
     ```
     par
     ```python
     ingredient_factors = optimize_day_portions_v2(lp_recipes, daily_targets, per_meal_targets=per_meal_targets)
     ```
  3. Application (ligne ~613) : remplacer
     ```python
     scaled = apply_scale_factor(recipe, lp_scale_factors[i])
     ```
     par
     ```python
     scaled = apply_ingredient_scale_factors(recipe, ingredient_factors[lp_idx])
     ```
     Note : `ingredient_factors` est une liste de dicts (1 par recette), donc `ingredient_factors[lp_idx]` est le dict de scale factors pour la recette `i`.

  4. Supprimer le stockage de `lp_scale_factors[i]` comme float unique — maintenant c'est un dict.

- **IMPORTS** : Voir ci-dessus
- **GOTCHA** :
  - La séparation `lp_indices` / `fallback_indices` reste identique — seuls les LP recipes passent par le v2
  - Les fallback recipes (sans nutrition_per_100g) continuent d'utiliser `scale_recipe_to_targets()` (inchangé)
  - `_build_meal_from_scaled_recipe()` doit recevoir le même format de sortie : recette avec `scaled_nutrition` et `ingredients` mis à jour. Vérifier que `apply_ingredient_scale_factors()` retourne le même format que l'ancien `apply_scale_factor()`.
- **VALIDATE** : `python -m pytest tests/ -x -q -k "not test_scripts_no_llm"` (run all tests except LLM check which is slow)

### Task 6 : UPDATE `src/nutrition/meal_plan_optimizer.py`

- **IMPLEMENT** :
  1. Supprimer le re-export de `fat_rebalancer` :
     ```python
     # SUPPRIMER ces lignes :
     from src.nutrition.fat_rebalancer import (  # noqa: F401 — re-exported
         rebalance_high_fat_day as _rebalance_high_fat_day,
         FAT_SURPLUS_THRESHOLD,
     )
     ```
  2. Garder `MIN_SCALE_FACTOR`, `MAX_SCALE_FACTOR`, `generate_adjustment_summary()`, `round_quantity_smart` re-export
  3. Optionnel : supprimer `generate_adjustment_summary()` si confirmé inutilisé (vérifier avec grep)

- **GOTCHA** : `portion_scaler.py` importe `MIN_SCALE_FACTOR, MAX_SCALE_FACTOR` depuis ce fichier — ne pas les supprimer
- **VALIDATE** : `python -c "from src.nutrition.meal_plan_optimizer import MIN_SCALE_FACTOR, MAX_SCALE_FACTOR; print('OK')"`

### Task 7 : REMOVE `src/nutrition/fat_rebalancer.py`

- **IMPLEMENT** : Supprimer le fichier. Il est **orphelé** (jamais appelé dans le code actif).
  - Vérifier avec grep qu'aucun autre fichier ne l'importe directement (seul `meal_plan_optimizer.py` le faisait, et on a supprimé cette ligne dans Task 6)
- **GOTCHA** : Si un test importe `fat_rebalancer`, supprimer aussi le fichier de test correspondant.
- **VALIDATE** : `python -c "import importlib; import pkgutil; [importlib.import_module(f'src.nutrition.{m.name}') for m in pkgutil.iter_modules(['src/nutrition'])]" && echo "All modules import OK"`

### Task 8 : UPDATE `tests/test_portion_optimizer.py`

- **IMPLEMENT** : Adapter les tests existants
  - Les tests de `_extract_recipe_macros()` restent valides (la fonction peut être gardée comme utilitaire ou recréée dans v2)
  - Les tests de `optimize_day_portions()` sont remplacés par `test_portion_optimizer_v2.py`
  - Les tests de `apply_scale_factor()` sont remplacés par les tests de `apply_ingredient_scale_factors()`
  - **Option** : garder l'ancien fichier de test si on garde `portion_optimizer.py` comme fallback, ou le supprimer si on le remplace complètement

- **VALIDATE** : `python -m pytest tests/ -x -q`

### Task 9 : Lint + Full Test Suite

```bash
ruff format src/ tests/ scripts/ && ruff check src/ tests/ scripts/
python -m pytest tests/ -x -q
```

### Task 10 : Eval — Validation du comportement agent

Le LP optimizer est au cœur du skill `meal-planning`. Modifier l'optimiseur peut changer le comportement de l'agent (macros des plans, qualité des réponses). Les tests unitaires valident la logique en isolation, mais il faut vérifier que **l'agent produit toujours des plans corrects avec le nouvel optimizer**.

Utiliser `/run-eval` pour créer et exécuter un eval qui vérifie :
- L'agent génère un plan de repas avec des macros dans les tolérances
- Les scale factors par ingrédient apparaissent dans les logs (pas un scale factor unique par recette)
- Les items discrets (œufs) sont en quantités entières dans le plan
- Le fat est correctement réduit quand le target fat est bas
- Pas de régression sur la variété des recettes

**Commande** : `/run-eval`

---

## SEAM REVIEW CHECKLIST

Avant de déclarer le travail terminé, vérifier ces points :

1. **`_build_meal_from_scaled_recipe()`** (generate_day_plan.py:108-123) — lit `scaled_recipe.get("scaled_nutrition", {})` puis `nutrition.get("calories", 0.0)` etc. Il faut que `apply_ingredient_scale_factors()` retourne un dict avec `scaled_nutrition` contenant exactement `{calories, protein_g, carbs_g, fat_g}` en float. Vérifié : le contrat est documenté dans Task 3. Le test `test_output_format_matches_v1()` dans Task 4 garantit la compatibilité.

2. **`validate_day()`** dans `generate_day_plan.py` — utilise les totaux du jour. Les totaux sont recalculés depuis `scaled_nutrition` des meals. Si le format change, la validation échoue silencieusement.

3. **`portion_scaler.py`** — utilise `MIN_SCALE_FACTOR` / `MAX_SCALE_FACTOR`. Ces constantes restent dans `meal_plan_optimizer.py` → pas d'impact.

4. **Fallback recipes** (sans `nutrition_per_100g`) — continuent d'utiliser `scale_recipe_to_targets()` dans `generate_day_plan.py`. Ce chemin n'est PAS modifié.

5. **Import circulaire** — `ingredient_roles.py` importe de `openfoodfacts_client.py`. Vérifier qu'il n'y a pas de cycle.

6. **`tests/test_scripts_no_llm.py`** — vérifie que `src/nutrition/` n'importe pas de LLM. `ingredient_roles.py` et `portion_optimizer_v2.py` n'importent que scipy + src.nutrition → OK.

---

## TESTING STRATEGY

### Unit Tests
- **`test_ingredient_roles.py`** : 15+ tests couvrant tous les rôles, exceptions, matching longest-first, normalisation
- **`test_portion_optimizer_v2.py`** : 15+ tests couvrant le MILP, items discrets, divergence, fallback, edge cases, performance

### Integration
- Run `generate_day_plan.py` avec un profil réel et vérifier que les macros du plan sont dans les tolérances
- Comparer les résultats v1 vs v2 sur les mêmes recettes

### Edge Cases
- Recette 100% fixed (épices/sauces)
- Recette avec 1 seul ingrédient scalable
- Tous les ingrédients discrets (petit-déjeuner : 2 œufs + 2 tranches de pain)
- Target fat très bas → huile réduite à 0.2×
- Target protéine très haut → poulet à 2.0×, riz à 2.5×
- MILP infeasible → fallback uniforme

---

## VALIDATION COMMANDS

### Level 1 : Syntax & Style
```bash
ruff format src/nutrition/ingredient_roles.py src/nutrition/portion_optimizer_v2.py tests/test_ingredient_roles.py tests/test_portion_optimizer_v2.py
ruff check src/ tests/
```

### Level 2 : Unit Tests
```bash
python -m pytest tests/test_ingredient_roles.py -x -q
python -m pytest tests/test_portion_optimizer_v2.py -x -q
```

### Level 3 : Full Test Suite
```bash
python -m pytest tests/ -x -q
```

### Level 4 : Eval agent (OBLIGATOIRE — le skill meal-planning est modifié)
```bash
# Utiliser /run-eval pour créer et exécuter un eval
# Vérifie le comportement end-to-end de l'agent avec le nouvel optimizer
```
Voir Task 10 pour les critères de l'eval.

### Level 5 : Integration manuelle
```bash
# Générer un plan et vérifier les logs
PYTHONPATH=. python -c "
import asyncio
from skills.meal_planning.scripts.generate_day_plan import execute
# Vérifier que les logs montrent des scale factors par ingrédient
"
```

---

## ACCEPTANCE CRITERIA

- [ ] `ingredient_roles.py` créé avec ~155 entrées, matching longest-first
- [ ] `get_ingredient_role()` couvre 95%+ des ingrédients des 547 recettes
- [ ] `portion_optimizer_v2.py` créé avec MILP via `scipy.optimize.milp`
- [ ] Items discrets (œufs, tranches) sont des variables INTEGER
- [ ] Contrainte de divergence inter-groupes (max 2.0×) sur paires protein↔starch↔vegetable uniquement (fat_source exempt)
- [ ] Bornes par rôle : protein [0.5,2.0], starch [0.3,2.5], vegetable [0.7,1.5], fat_source [0.2,1.5], unknown [0.75,1.25]
- [ ] `generate_day_plan.py` appelle le nouvel optimizer
- [ ] `fat_rebalancer.py` supprimé
- [ ] `meal_plan_optimizer.py` nettoyé (plus de re-export fat_rebalancer)
- [ ] 30+ tests unitaires (ingredient_roles + portion_optimizer_v2)
- [ ] Fallback si MILP infeasible
- [ ] Performance <10ms pour 20 variables
- [ ] Tous les tests existants passent
- [ ] `ruff format` + `ruff check` passent
- [ ] Seam review complété
- [ ] Eval agent passé (`/run-eval`) — plans corrects avec le nouvel optimizer

## COMPLETION CHECKLIST

- [ ] Tasks 1-10 complétées en ordre
- [ ] Chaque validation de task passée immédiatement
- [ ] Level 1-3 validations passées
- [ ] Level 4 : eval agent exécuté et validé
- [ ] Full test suite verte
- [ ] Seam review : 6 points vérifiés
- [ ] Pas de régression sur les plans de repas existants

---

## NOTES

### Décisions de design

1. **Pourquoi MILP et pas LP ?** Les items discrets (œufs) nécessitent des variables entières. Un LP pur + post-arrondi casserait l'optimalité. Le MILP résout le problème en une seule passe.

2. **Pourquoi pas 1 variable par ingrédient dans le LP v1 ?** Le v1 ne connaissait pas les rôles culinaires. Sans contraintes de cohérence, un LP par ingrédient pourrait produire "poulet 400g, riz 10g" — techniquement optimal en macros, culinairement absurde.

3. **Pourquoi fixed et pas unknown pour les épices ?** Les épices en petite quantité (<10g) n'impactent presque pas les macros. Les scaler n'apporte rien mais ajoute des variables au solveur. Fixed = 0 variable = solveur plus rapide + plus stable.

4. **Pourquoi la divergence est par recette et pas globale ?** On veut que DANS une recette, le poulet et le riz bougent ensemble. Mais entre recettes différentes, les scaling sont indépendants (un bowl peut être ×1.5 et une salade ×0.8).

5. **Pourquoi garder `portion_optimizer.py` comme fallback ?** Le MILP peut théoriquement échouer (infeasible). Avoir le v1 comme fallback garantit qu'on produit toujours un plan. En pratique, on peut le supprimer dans une version future si le MILP est stable.

### Risques

- **Tagging coverage** : Si des ingrédients importants ne sont pas dans la table, ils tombent en `unknown` avec des bornes serrées [0.75, 1.25]. C'est safe mais sous-optimal. Mitigation : table exhaustive (155 entrées) + audit post-déploiement.

- **Divergence constraint feasibility** : Risque fortement réduit car `fat_source` est exempt de la divergence. Les seules paires contraintes sont protein↔starch, protein↔vegetable, starch↔vegetable — des groupes qui coexistent naturellement dans les recettes. Le cas "1 protein + 3 fat_source" ne génère aucune contrainte de divergence. Si malgré tout le MILP est infeasible (targets extrêmes), le fallback uniforme prend le relais.

- **MILP performance** : scipy MILP avec des entiers peut être plus lent. Mitigation : <20 variables → <10ms. Si > 50 variables, timeout option dans `milp()`.
