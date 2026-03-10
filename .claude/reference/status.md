# Current Status

**Phase:** Mobile MVP — Frontend refactoring + deployment
**Full roadmap:** See `PRD.md` section 12

**What's done:**
- Backend complete: FastAPI + Pydantic AI agent + 6 skills + 17 scripts + JWT auth + RLS
- React frontend: chat + streaming + Supabase Auth + generative UI (7 components)
- Multi-user isolation verified, 714+ unit tests passing, 13 eval datasets
- OpenFoodFacts: 264K products (nettoyés Atwater), 1000+ cached ingredient mappings, online API fallback
- Database: 16 tables, all RLS-enabled
- Generative UI committed (7 components, tests, evals)
- PRD v3.0 + README updated

**Mobile MVP — Implementation Steps:**

### Step 1: Navigation mobile + responsive ✅
### Step 2: Tables DB + endpoints backend ✅
### Step 3: Onglet Suivi du Jour ✅
### Step 4: Onglet Mes Plans ✅
### Step 5: Integration + polish + deploy ✅
### Step 5b: Pre-deploy audit + PWA readiness ✅

### Step 6: Deployment infrastructure
- [ ] Préparer la base de données production (Supabase séparé, 14 migrations SQL, seed OpenFoodFacts + recettes)
- [ ] Créer la config de déploiement (Dockerfile/Procfile selon plateforme)
- [ ] Configurer les variables d'environnement production (CORS_ORIGINS, API keys, Supabase)
- [ ] CI/CD pipeline (GitHub Actions : pytest, ruff, npm lint, npm build)
- [ ] Deploy backend (Railway/Fly.io) + frontend (Vercel)
- [ ] Smoke test end-to-end
- [ ] TWA → APK generation + distribution

---

## Deferred Issues (from pre-deploy review 2026-03-07)

- [x] **M4. Sync Supabase client dans endpoints async** — ✅ Migré vers `SupabaseAsyncClient`. 81 `.execute()` calls await-ifiés, 16 source files + 14 test files. `get_async_supabase_client()` dans `src/clients.py`, sync client préservé pour `scripts/`.
- [ ] **L5. Ruff E402 — 10 imports pas en haut de fichier** — intentionnel (après `sys.path` setup). Ajouter `# noqa: E402` ou configurer ruff pour ignorer ces fichiers.
- [ ] **L6. Mypy — 140 erreurs pre-existantes** — surtout implicit Optional et types Pydantic AI v2. Nécessite un pass dédié mypy cleanup.

## Improvement Ideas

- [ ] **Macro redistribution quand une recette favorite est pinned** — Quand une recette favorite est forcée dans un slot (Niveau 2), `calculate_meal_macros_distribution` devrait ajuster les cibles macro des slots restants pour compenser le profil fixe de la favorite. Actuellement le MILP optimise tous les slots contre la distribution uniforme originale, ce qui cause un drift carbs/fat quand la favorite a un profil macro atypique (ex: -24% carbs observé en test). Implémentation : après favorite lookup, soustraire les macros de la favorite des cibles journalières, redistribuer le reste sur les slots non-remplis.

Rapport complet : `.claude/code-reviews/pre-deploy-review-20260307.md`

---

## DONE: v2f — MILP per-ingredient optimizer (2026-03-10) ✅

Remplace le LP v1 (1 scale factor par recette) par un MILP per-ingredient via `scipy.optimize.milp`.

- `ingredient_roles.py` : 155 mappings ingrédient→rôle (protein, starch, vegetable, fat_source, fixed)
- `portion_optimizer_v2.py` : variables par ingrédient, contraintes de divergence inter-groupes, items discrets (œufs) en entiers
- `fat_rebalancer.py` supprimé (remplacé par contraintes MILP)
- `generate_day_plan.py` switchée sur v2
- 80 tests unitaires + 3/3 evals passés
- Testé manuellement : macros encore plus précises qu'avec v1

## DONE: v2e — Recipe import pipeline infrastructure (2026-03-10) ✅

Pipeline multi-source pour l'import de recettes avec validation OFF.

- 8 adaptateurs (Spoonacular, Edamam, TheMealDB, Marmiton, 750g, CuisineAZ, BBC Good Food, AllRecipes)
- CLI orchestrateur `scripts/import_recipes.py` (--source, --limit, --dry-run)
- 515 traductions EN→FR (`scripts/data/ingredient_translations.json`)
- 50 tests unitaires
- Infrastructure prête — import réel à faire avec clés API configurées

## DONE: v2b — Inter-meal macro compensation (2026-03-09) ✅
## DONE: v2d — Liquid/powder OFF code fixes (2026-03-09) ✅
## DONE: Meal-planning audit & data quality (2026-03-09) ✅
## DONE: Recipe DB coverage & pool unification (2026-03-09) ✅
## DONE: Fat trop bas fix (2026-03-08) ✅

---

## DONE: v2c — Extract tunable constants + v1 cleanup (2026-03-10) ✅

27 constantes centralisées dans `src/nutrition/constants.py` (scoring, macros, calories, MILP, LLM).
v1 LP optimizer (`portion_optimizer.py`) supprimé, `_extract_recipe_macros` migré dans v2.
697 tests passing, 0 regressions.

## DONE: Recipe DB gap-filling (2026-03-10) ✅

65 nouvelles recettes insérées ciblant les gaps identifiés :
- 20 collations high-protein low-fat (avg 23g prot, 4g fat)
- 15 petits-déjeuners high-protein low-fat (avg 27.5g prot, 5.5g fat)
- 30 déjeuner/dîner végétarien+vegan + cuisines diverses (avg 27g prot, 10g fat)

**DB : 627 → 692 recettes OFF-validées**, 15+ cuisines, 3 diet types équilibrés.
Skill réutilisable : `/seed-recipes` (`.claude/skills/seed-recipes/`)

---

## NEXT: Feature — Recettes favorites + vue détail

### Étape 1 : Vue détail recette + bouton favori
- [ ] **Backend**: `POST /api/recipes` (upsert par nom) — insère une recette depuis plan_data
- [ ] **Backend**: `GET /api/recipes/{id}` — fetch recette individuelle
- [ ] **Frontend**: Composant `RecipeDetailDrawer` (modale bottom-sheet mobile)
  - Nom, meal_type, temps de préparation
  - Ingrédients avec quantités + unités
  - Instructions étape par étape
  - Macros détaillés (calories, P/G/L)
  - Bouton favori (coeur) → toggle favori
- [ ] **Frontend**: Recettes cliquables dans `MealPlanView` → ouvre RecipeDetailDrawer
- [ ] **Frontend**: Favoris cliquables dans `MyPlans` → ouvre RecipeDetailDrawer
- [ ] **Frontend**: Type `FavoriteWithRecipe` exporté proprement (remplacer cast `as unknown`)
- [ ] Tests unitaires backend + build frontend

### Étape 2 : Édition des favoris
- [ ] Depuis le détail d'un favori, modifier quantités/ingrédients/notes
- [ ] `PATCH /api/recipes/{id}` endpoint
- [ ] Recalcul des macros à la modification (OpenFoodFacts)

---

## BACKLOG

- [ ] **Critères de sélection recettes** — vérifier que les filtres (macro ratio, variété, cuisine) sont pertinents et que le pool de 692 recettes offre assez de choix pour tous les profils (perte de poids, prise de masse, vegan, etc.)
- [ ] **Couverture ingredient_roles.py** — 155 mappings sur 1000+ ingrédients validés. Les "unknown" [0.75×–1.25×] sont conservateurs. Enrichir les rôles les plus fréquents pour améliorer l'optimisation MILP.
- [ ] **Import recettes live** — utiliser le pipeline v2e avec les API (Spoonacular, TheMealDB) une fois les clés configurées. Priorité : sources FR (Marmiton, 750g).
- [ ] **Deployment** — Step 6 du status : DB production, CI/CD, deploy backend+frontend
