# Feature: v2d — OFF Liquid/Powder Ingredient Mismatch Fix

## Problème

Plusieurs recettes référencent des codes OFF de produits **secs/concentrés/poudre** mais utilisent l'ingrédient comme un **liquide** (mesuré en `ml`). Ça gonfle les macros — surtout les protéines — et pollue la sélection de recettes : les recettes avec des protéines artificiellement hautes passent toujours le filtre macro, empêchant les nouvelles recettes correctes d'être sélectionnées.

**Cause racine** : Le matching OFF a choisi le produit le plus populaire pour "bouillon de légumes" — la forme cube/poudre (200 kcal/100g, 13g protéines). Mais les recettes décrivent le liquide reconstitué.

### 6 codes problématiques, ~79 recettes affectées

| Code | Produit OFF | kcal/100g | Recettes | Stratégie | Ce que l'utilisateur voit |
|---|---|---|---|---|---|
| `26064529` | Bouillon de légumes (poudre) | 200 | 16 | **Option B** | "Cube de bouillon (7g) + Eau (339ml)" |
| `3760149750262` | Bouillon de poulet (poudre) | 154 | 6 | **Option B** | "Cube de bouillon (5g) + Eau (250ml)" |
| `4513883605201` | Dashi (poudre) | 312 | 1 | **Option B** | "Dashi en poudre (5g) + Eau (500ml)" |
| `2002657025588` | Sauce soja (concentrée) | 225 | 54 | **Option A** | "Sauce soja (15ml)" — inchangé |
| `3547130022382` | Vinaigre de vin rouge (mislabel) | 118 | 1 | **Option A** | "Vinaigre de vin rouge (30ml)" — inchangé |
| `8014347005149` | Vinaigre blanc (mislabel) | 86 | 1 | **Option A** | "Vinaigre blanc (15ml)" — inchangé |

### Ingrédients investigués et validés (PAS des erreurs)

| Ingrédient | kcal/100g | Pourquoi c'est correct |
|---|---|---|
| Huile d'olive | 821 | Huile = légitimement dense. L'utilisateur verse de l'huile. |
| Lait de coco | 206 | Lait gras. 206 kcal c'est normal pour du lait de coco entier. |
| Mirin | 218 | Vin de riz sucré. Liquide légitimement dense. |
| Sauce teriyaki | 133 | Sauce sucrée, densité correcte. |
| Sauce césar | 351 | Dressing gras, densité correcte. |
| Crème légère | 140 | Crème, c'est gras par nature. |
| Sirop d'érable | 220 | Sirop sucré, densité correcte. |
| Miel | 320 | Sucre pur, densité correcte. |
| Vinaigre balsamique | 263 | Variabilité naturelle (50-350 kcal selon vieillissement). Code actuel = probablement un vinaigre vieilli/crème, mais 5 recettes seulement et impact faible (petites quantités). À surveiller, pas bloquant. |
| Sauce poisson / Nuoc mam | 54-70 | Borderline mais plausible pour du nuoc mam (riche en sel/acides aminés). |
| Kéfir | 53 | Plausible pour un kéfir fermenté. |

### Audit exhaustif : 63 paires (code, ingrédient) en `ml` vérifiées

Un scan complet de toute la DB a confirmé que seuls les 6 codes ci-dessus sont des vrais problèmes. Tous les autres `⚠️ >50 kcal` sont des liquides légitimement denses (huiles, crèmes, sirops, laits gras).

---

## Solution : 2 stratégies selon la perspective utilisateur

### Option B — Concentrés dilués (bouillon, dashi)

**Du point de vue du cuisinier** : on fait bouillir de l'eau + on ajoute un cube. La recette doit refléter ce geste.

```
AVANT (ce que l'utilisateur voyait — faux) :
  "Bouillon de légumes — 339ml"
  → Le code OFF pointe vers de la poudre à 200 kcal/100g
  → Le système calcule 339g × 2.0 = 678 kcal ← FAUX

APRÈS (ce que l'utilisateur voit — vrai) :
  "Cube de bouillon de légumes — 5g"     → code poudre (correct!) → ~10 kcal
  "Eau — 339ml"                          → 0 kcal
  → Total : ~10 kcal ← CORRECT
```

- Le code OFF poudre reste **valide** — c'est la quantité qui change (5g au lieu de 339ml)
- L'eau ne contribue rien nutritionnellement
- **Ratio standard** : 10g de cube pour 500ml d'eau → `max(5, round(ml × 10 / 500))` g

### Option A — Vrais liquides (sauce soja, vinaigre)

**Du point de vue du cuisinier** : on verse de la sauce soja depuis la bouteille. C'est un liquide. Le problème c'est juste le mauvais code OFF.

```
AVANT (faux) :
  "Sauce soja — 15ml" → code concentré → 225 kcal/100g → 34 kcal ← FAUX (trop haut)

APRÈS (vrai) :
  "Sauce soja — 15ml" → code liquide  →  34 kcal/100g →  5 kcal ← CORRECT
```

- L'ingrédient tel que l'utilisateur le voit ne change PAS (même nom, même quantité)
- Seul le code OFF interne est corrigé → les macros deviennent justes

---

## Codes de remplacement vérifiés

### Option A — Swap de code OFF

| Ingrédient | Mauvais code | Bon code | Produit OFF vérifié | kcal/100g |
|---|---|---|---|---|
| Sauce soja | `2002657025588` (225 kcal) | `3171920000238` | Sauce soja (Kikkoman) | 34 |
| Vinaigre de vin rouge | `3547130022382` (118 kcal) | `3165356050066` | Vinaigre de vin rouge | 4 |
| Vinaigre blanc | `8014347005149` (86 kcal) | `3347439950511` | Vinaigre de vin blanc | 1 |

### Option B — Split concentré + eau

Les codes poudre existants sont conservés — seule la quantité et la structure de l'ingrédient changent.

| Code poudre | Nom du cube dans la recette | Ratio |
|---|---|---|
| `26064529` | Cube de bouillon de légumes | 10g / 500ml |
| `3760149750262` | Cube de bouillon de poulet | 10g / 500ml |
| `4513883605201` | Dashi en poudre | 10g / 500ml |

---

## Fichiers impactés

| Fichier | Modification | Raison |
|---|---|---|
| `scripts/fix_liquid_off_codes.py` | **Nouveau** | Script de correction (idempotent, LLM-free) |
| `src/nutrition/openfoodfacts_client.py` | Ajout catégorie `liquide_aqueux` + densités ml→g | Guard pour empêcher les futurs mismatches |
| `tests/test_openfoodfacts_client.py` | 10 nouveaux tests | Valider le guard avant d'exécuter le fix |

**À lire avant d'implémenter :**
- `src/nutrition/openfoodfacts_client.py` — `_CALORIE_CEILINGS`, `_INGREDIENT_CATEGORIES`, `_calorie_density_plausible()`, `_ML_TO_G_DENSITY`
- `scripts/validate_all_recipes.py` — pipeline de revalidation
- `tests/test_openfoodfacts_client.py` — `TestCalorieDensityGuard`

---

## TÂCHES

### Task 1 ✅ : Créer `scripts/fix_liquid_off_codes.py`

Script LLM-free (rule 10). Deux modes de correction :

- **Option A** : swap `off_code` dans l'ingrédient existant, purge `nutrition_per_100g` et `confidence`
- **Option B** : remplace 1 ingrédient (bouillon 339ml) par 2 ingrédients (cube 5g + eau 339ml)
- Nettoie le cache `ingredient_mapping` pour les 6 codes
- Met `off_validated = False` sur chaque recette modifiée

**Sécurité** : Script idempotent. Re-run safe (code déjà swappé → pas dans le dict → ignoré).

### Task 2 ✅ : Ajouter catégorie `liquide_aqueux` au density guard

- Ceiling = 50 kcal/100g
- 17 entrées dans `_INGREDIENT_CATEGORIES` : bouillons, sauce soja, vinaigres spécifiques, fumets, fonds, dashi, nuoc mam
- **Pas** de clé générique "vinaigre" → évite le faux positif sur "vinaigre balsamique" (qui matche par substring)
- Clés spécifiques : vinaigre blanc, vinaigre de vin, vinaigre de vin rouge, vinaigre de riz, vinaigre de cidre

**Exclues volontairement** : mirin (~218), teriyaki (~133), vinaigre balsamique (~88-263), huiles, crème, miel, sirop. Ce sont des liquides légitimement denses.

### Task 3 ✅ : Mettre à jour `_ML_TO_G_DENSITY`

6 entrées ajoutées : bouillon (1.0), sauce soja (1.08), vinaigre (1.01), dashi (1.0), sauce poisson (1.09), nuoc mam (1.09). Impact faible (tous ~1.0) mais documente l'intention.

### Task 4 ✅ : Tests unitaires pour `liquide_aqueux`

10 tests dans `TestCalorieDensityGuard` :
- Bouillon plausible (2-5 kcal) et implausible (154-200 kcal)
- Sauce soja plausible (34 kcal) et implausible (225 kcal)
- Dashi implausible (312 kcal)
- Vinaigre plausible (1-4 kcal) et implausible (86-118 kcal)
- Dense liquids NOT in category (mirin 218, teriyaki 133, balsamique 88 → tous passent)
- Category lookup (vérifie le mapping + les exclusions)

**Résultat** : 49 passed, 1 skipped (cache test skip).

### Task 5 : Exécuter le fix script + revalidation

```bash
PYTHONPATH=. python scripts/fix_liquid_off_codes.py
PYTHONPATH=. python scripts/validate_all_recipes.py
```

Le fix corrige les ingrédients, la revalidation recalcule les macros de chaque recette.

### Task 6 : Vérifier qu'aucun mauvais code ne subsiste

```bash
PYTHONPATH=. python -c "
from src.clients import get_supabase_client
sb = get_supabase_client()
bad_codes = ['26064529','2002657025588','4513883605201','3760149750262','3547130022382','8014347005149']
resp = sb.table('recipes').select('id,name,ingredients').execute()
found = 0
for r in resp.data:
    for ing in r.get('ingredients',[]):
        if ing.get('off_code') in bad_codes and ing.get('unit') == 'ml':
            print(f'STILL BAD: {r[\"name\"]} — {ing[\"name\"]} ({ing.get(\"quantity\")}{ing.get(\"unit\")}) → {ing[\"off_code\"]}')
            found += 1
print(f'Check complete: {found} remaining issues')
"
```

Note : le check ne flag que les codes poudre utilisés en `ml`. Les codes poudre en `g` (cube après split) sont **corrects**.

### Task 7 : Lint + tests complets

```bash
ruff format src/ tests/ scripts/ && ruff check src/ tests/ scripts/
python -m pytest tests/ -x -q
```

---

## Décisions de design

### Pourquoi 2 stratégies et pas 1 ?

Parce que l'utilisateur vit 2 réalités différentes en cuisine :

1. **Bouillon** → L'utilisateur met un **cube** dans l'eau. Lui afficher "Bouillon liquide (339ml)" avec un code produit de bouillon prêt-à-l'emploi est trompeur (et ces produits prêts sont rares en DB OFF). Option B reflète le vrai geste.

2. **Sauce soja** → L'utilisateur **verse** de la sauce soja. C'est un vrai liquide en bouteille. Le nom et la quantité sont corrects — seul le code OFF interne était mauvais. Option A ne touche que la donnée invisible pour l'utilisateur.

### Pourquoi le code poudre reste pour Option B ?

Le code OFF `26064529` est correct pour du bouillon en poudre. C'est la **quantité** qui change : 5g (poudre) au lieu de 339ml (calculé comme liquide). L'Atwater check passe car les macros de la poudre sont cohérentes pour de la poudre.

### Pourquoi pas de clé générique "vinaigre" ?

Le lookup `_get_ingredient_category` fait du substring matching (longest first). Une clé "vinaigre" matcherait "vinaigre balsamique" → faux positif (le balsamique est à 88-263 kcal, au-dessus du ceiling 50). On utilise des clés spécifiques : "vinaigre blanc", "vinaigre de vin", "vinaigre de riz", "vinaigre de cidre".

### Minimum 5g pour le cube

Empêche les valeurs aberrantes si la quantité originale est très petite (ex: "50ml de bouillon" → `round(50 × 10/500)` = 1g → clampé à 5g = un demi-cube, ce qui est réaliste).

---

## Sécurité & robustesse

- **Idempotence** : Le script peut être relancé sans effet négatif. Code déjà swappé → pas dans le dict → ignoré. Ingrédient déjà splitté → pas de code poudre en `ml` → ignoré.
- **Pas de perte de données** : `off_validated = False` force la revalidation. Les anciennes macros sont recalculées, pas supprimées silencieusement.
- **Cache purgé** : Les entrées `ingredient_mapping` des 6 mauvais codes sont supprimées avant le fix. Ça empêche le cache de servir les vieilles données.
- **Tests avant exécution** : Le density guard est testé (Tasks 2-4) AVANT d'exécuter le fix (Task 5). On ne touche pas à la DB de production sans tests verts.
- **Vérification post-fix** : Task 6 scanne toute la DB pour confirmer qu'aucun code poudre en `ml` ne subsiste.
- **Guard pour le futur** : La catégorie `liquide_aqueux` avec ceiling 50 kcal bloque automatiquement les futures associations poudre→liquide lors du matching OFF.

---

## Acceptance Criteria

- [x] Script `fix_liquid_off_codes.py` créé (idempotent, LLM-free)
- [x] Catégorie `liquide_aqueux` ajoutée au density guard (ceiling = 50 kcal)
- [x] `_ML_TO_G_DENSITY` étendu avec 6 entrées
- [x] 10 tests unitaires ajoutés et verts
- [ ] 3 codes liquides (sauce soja, vinaigres) swappés vers les bons codes OFF
- [ ] 3 codes concentrés (bouillons, dashi) splittés en cube + eau
- [ ] `ingredient_mapping` cache nettoyé pour les 6 codes
- [ ] ~79 recettes revalidées avec macros corrigés
- [ ] Aucune recette ne référence un code poudre en unité `ml` après le fix
- [ ] Tous les tests passent
- [ ] `ruff format` + `ruff check` passent
