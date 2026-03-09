# Current Status

**Phase:** Mobile MVP — Frontend refactoring + deployment
**Full roadmap:** See `PRD.md` section 12

**What's done:**
- Backend complete: FastAPI + Pydantic AI agent + 6 skills + 17 scripts + JWT auth + RLS
- React frontend: chat + streaming + Supabase Auth + generative UI (7 components)
- Multi-user isolation verified, 366 unit tests passing, 13 eval datasets
- OpenFoodFacts: 264K products (nettoyés Atwater), 933 cached ingredient mappings, online API fallback
- Database: 16 tables, all RLS-enabled
- Generative UI committed (7 components, tests, evals)
- PRD v3.0 + README updated

**Mobile MVP — Implementation Steps:**

### Step 1: Navigation mobile + responsive ✅
- [x] Bottom tab bar (3 tabs: Chat, Suivi du Jour, Mes Plans)
- [x] Mobile-first layout (full-width, no desktop sidebar by default)
- [x] Sidebar conversations → drawer (hamburger menu)
- [x] Profile icon in header → SettingsModal
- [x] Chat tab works immediately in new layout
- [x] Suivi du Jour + Mes Plans show placeholder
- [x] Build passes, desktop layout untouched

### Step 2: Tables DB + endpoints backend ✅
- [x] Create `daily_food_log` table + RLS (with user delete policy)
- [x] Create `favorite_recipes` table + RLS (with user delete policy for unfavoriting)
- [x] Create `shopping_lists` table + RLS (deny delete)
- [x] New API endpoints: daily-log CRUD, favorites CRUD, shopping-lists, meal-plans list
- [x] Pydantic request models (DailyLogCreate, DailyLogUpdate, FavoriteCreate, ShoppingListUpdate)
- [x] Frontend typed fetch functions in `api.ts` (with `apiFetch` helper)
- [x] TypeScript types updated (`database.types.ts`: DailyFoodLog, FavoriteRecipe, ShoppingList)
- [x] All endpoints tested end-to-end (auth, CRUD, 403 on wrong user, 401 unauth)

### Step 3: Onglet Suivi du Jour ✅
- [x] Custom hook `useDailyTracking` (date nav, profile targets, daily log, plan matching, CRUD)
- [x] DateSelector — navigation jour par jour, label "Aujourd'hui" / "Revenir à aujourd'hui"
- [x] CalorieGauge — SVG radial gauge avec gradient + glow (remplacé Recharts)
- [x] TrackingMacros — 3 barres horizontales (protéines/glucides/lipides) consumed vs target
- [x] MealSection — entrées groupées par meal_type avec icônes + suppression
- [x] PlanValidation — check/uncheck repas du plan → auto-log avec macros
- [x] TrackingInput — barre de saisie inline (texte + micro) → agent parse et log
- [x] Ordre repas: petit-déj → déjeuner → collation → dîner
- [x] Code review: 7/7 issues corrigées (keys, aria-labels, dead code, normalisation meal_type, race condition polling)
- [x] `DialogTitle` accessibility fix dans `command.tsx`
- [x] Fix streaming NDJSON dans TrackingInput (callback no-op pour path streaming)
- [x] Agent food logging: `log_food_entries` skill script + SKILL.md routing + `run_skill_script` type fix
- [x] 5 unit tests + 3 eval scenarios (4 cases, all 100%)

### Step 4: Onglet Mes Plans ✅
- [x] MyPlans page rewritten: 3-tab layout (Plans / Favoris / Courses)
- [x] PlanCard — glass-morphism card, week label, calorie/protein badges, click → /plans/:id
- [x] FavoriteCard — recipe name, meal_type badge, macros row, heart unfavorite (optimistic UI)
- [x] ShoppingListCard — expandable, items grouped by French category, checkbox toggle persisted
- [x] Empty states with guidance messages per tab
- [x] Data fetching via useEffect+useState (same pattern as DailyTracking)
- [x] TypeScript build passes, mobile-friendly layout

### Step 5: Integration + polish + deploy ✅
- [x] Agent food logging via chat (log_food_entries skill script)
- [x] Code review + security/efficiency fixes
- [x] Editable food name in daily tracking UI
- [x] Pre-deploy cleanup (console.log removal, requirements.txt sync, CRLF fix, linting)
- [x] 490 tests passing, frontend build OK

### Step 5b: Pre-deploy audit + PWA readiness ✅
- [x] Audit complet (sécurité, linting, tests, qualité code) — 0 issues critiques
- [x] ESLint: 6 erreurs → 0 (empty interfaces, unused vars, regex escapes, missing deps)
- [x] Favicon remplacé par logo Salad vert (SVG + PNG 192/512)
- [x] Renommage "Nutritionniste IA" → "Assistant Nutrition IA" (5 fichiers)
- [x] Sidebar mobile : liens Suivi/Bibliothèque masqués (déjà dans BottomTabs)
- [x] PWA manifest.json (nom, icônes, orientation, couleurs, langue FR)
- [x] Meta tags mobile : theme-color, apple-mobile-web-app-capable, apple-touch-icon, Open Graph
- [x] Service Worker via vite-plugin-pwa (cache app shell, autoUpdate, API en NetworkOnly)
- [x] Page 404 refaite (thème dark glass-morphism, logo, texte FR)
- [x] Mot de passe oublié : lien dans AuthForm + PasswordRecoveryModal (intercepte PASSWORD_RECOVERY)
- [x] PRD v3.1 : ajout section 14 — RAG personnelle par utilisateur (feature Phase 2)

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

Issues identified but intentionally deferred — not blockers, require dedicated refactors:

- [ ] **M4. Sync Supabase client dans endpoints async** — `src/api.py` utilise le client sync partout, bloque l'event loop. Migrer vers client async ou `asyncio.to_thread()`. Impact: performance sous charge.
- [ ] **L5. Ruff E402 — 10 imports pas en haut de fichier** — intentionnel (après `sys.path` setup). Ajouter `# noqa: E402` ou configurer ruff pour ignorer ces fichiers.
- [ ] **L6. Mypy — 140 erreurs pre-existantes** — surtout implicit Optional et types Pydantic AI v2. Nécessite un pass dédié mypy cleanup.

Rapport complet : `.claude/code-reviews/pre-deploy-review-20260307.md`

---

## Fix: Fat trop bas dans les meal plans ✅ (2026-03-08)

Le meal planner produisait des plans avec fat à -30/-55% du target (50g au lieu de 82g).

**3 corrections appliquées :**
1. **Filtre macro ratio relatif** (`recipe_db.py`): tolérance passée d'absolue à relative. Avec target fat=25%, accepte désormais [18.7%–31.1%] au lieu de [0%–50%]. Appliqué aux 3 macros.
2. **62 recettes balanced seedées** (`scripts/data/balanced_recipes.json`): toutes avec ~25% fat via sources lipides réelles (avocat, huile olive, beurre, fromage, saumon, noix, oeufs). 2 collation + 20 petit-dej + 20 déjeuner + 20 dîner. 60/62 OFF-validated. DB: 362 recettes total.
3. **Conversion "pièces" → grammes** (`openfoodfacts_client.py`): `_PIECE_WEIGHTS` dict pour 20 ingrédients courants. Avant: 3 oeufs = 100g. Après: 3×60g = 180g. +11 tests unitaires.

---

## DONE: Meal-planning audit & data quality (2026-03-09)

- [x] **Atwater sanity check** — `_passes_atwater_check()` dans `openfoodfacts_client.py`. Vérifie `|cal - (P×4+G×4+L×9)| < 30%` à l'insertion en cache ET à la lecture. Empêche les données OFF corrompues de polluer les plans.
- [x] **API OFF en ligne** — fallback `search_food_online()` quand la DB locale (264K produits) ne trouve pas l'ingrédient. Résultat inséré en local pour les appels futurs. Flux : cache → DB locale → API OFF → no-match.
- [x] **Nettoyage DB** — 10 500 produits OFF corrompus supprimés (264K restants), 78 mappings cache supprimés (922 restants), 174 recettes re-validées.
- [x] **Collations auditées** — 11 collations < 10g protéines supprimées, remplacées par 11 nouvelles (10-22g protéines, omnivore/végétarien/vegan). 51 collations total.
- [x] **Sécurité** — `sanitize_user_text()`, XML delimiters dans prompts LLM, UUID validation, `asyncio.Semaphore(5)` rate-limiting OFF.
- [x] **Modularité** — `find_worst_meal()`, `validate_recipe_allergens()`, constantes `MACRO_TOLERANCE_*` extraites vers `validators.py`.
- [x] **Simplification** — `_BatchState` dataclass, magic numbers nommés, `max(0,...)` guard LP targets négatifs, warnings surfacés.
- [x] **24 nouveaux tests** — Atwater, sanitize, allergens, find_worst_meal.

## DONE: Recipe DB coverage & pool unification (2026-03-09)

- [x] **Pool dejeuner/diner unifié** — `search_recipes()` utilise `.in_("meal_type", ["dejeuner", "diner"])` au lieu de `.eq()`. Pas de migration DB. Batch cooking et food tracking intacts.
- [x] **150 nouvelles recettes** — 50 petit-dejeuner + 50 main meals + 50 collations, toutes OFF-validées.
- [x] **25 recettes vegan/végétarien ajoutées** — 15 vegan diner + 10 végétarien diner pour équilibrer les pools.
- [x] **26 recettes non-validées supprimées** — macros corrompues ou incohérentes.
- [x] **Cuisine types normalisés** — tous en français (british→britannique, chinese→chinoise, etc.).
- [x] **Quasi-doublons nettoyés** — 9 recettes similaires (>85% similarité) supprimées.
- [x] **DB finale** : 547 recettes, 546 OFF-validées. Couverture équilibrée :
  - collation: 32 omnivore / 33 végétarien / 29 vegan (94 total)
  - dejeuner: 111 / 28 / 29 (168 total)
  - diner: 88 / 30 / 30 (148 total)
  - petit-dejeuner: 65 / 42 / 30 (137 total)
  - Pool main meals combiné: 199 omnivore / 58 végétarien / 59 vegan (316 total)

## TODO v2: LP optimizer hybride par groupes d'ingrédients (risque moyen)

**Problème** : le LP actuel applique UN scale factor par recette entière. Si une recette a un mauvais ratio macro, le LP ne peut que la réduire/augmenter globalement — il ne peut pas ajuster les proportions internes.

**Solution** : catégoriser les ingrédients par rôle et scaler par groupe :

```
Recette "Bowl poulet teriyaki"
  Protéine  : poulet 150g      → scalable [0.5×, 2.0×]
  Féculent  : riz 80g          → scalable [0.3×, 2.0×]
  Légumes   : brocoli 100g     → fixe ou léger scaling
  Sauce     : sauce teriyaki   → proportionnel au féculent
  Garniture : sésame 5g        → fixe
```

Le LP optimise 2-3 groupes par recette au lieu d'1 facteur unique, donnant la flexibilité macro sans casser la cohérence culinaire.

**Prérequis** :
- Tagger chaque ingrédient avec son rôle (`protein`, `starch`, `vegetable`, `sauce`, `garnish`)
- ~430 recettes × ~5 ingrédients = ~2150 tags → automatisable avec un LLM en batch
- Ajouter les contraintes de proportion au LP (sauce proportionnelle au féculent, garniture fixe)
- Modifier `portion_optimizer.py` : passer de n variables (1/recette) à ~3n variables (groupes/recette)
- Contraintes culinaires : quantités min/max par ingrédient (1 œuf = 60g, pas 37g)

**Complexité** : moyenne-haute. Le LP reste trivial (<10ms) mais le tagging et les contraintes culinaires demandent du travail de design.

## TODO v2b: Compensation inter-repas (budget macro glissant)

**Problème** : la sélection de recettes applique le MÊME target macro ratio à chaque repas indépendamment. Si le dîner a 40% fat, le petit-déjeuner devrait compenser à 15% fat — mais le système ne le sait pas car chaque slot est traité en isolation.

**Solution** : sélection séquentielle avec budget macro glissant :

```
Budget jour : 2500 kcal, 170g P, 80g F, 300g C

1. Sélectionner petit-déjeuner → "Omelette champignons" (500 kcal, 35g P, 25g F, 40g C)
2. Budget restant : 2000 kcal, 135g P, 55g F, 260g C
   → Nouveau target ratio : P=27%, F=25%, C=52% (fat a baissé car l'omelette était grasse)
3. Sélectionner déjeuner avec ces nouveaux ratios → recette plus lean
4. Budget restant recalculé → sélectionner dîner + collation
```

**Avantages** :
- Permet de mixer recettes grasses et lean dans la même journée
- Pas besoin de filtrer/exclure des recettes — le pool reste large
- Compatible avec le LP actuel (le LP reçoit des targets ajustés)
- Implémentation légère : modifier `generate_day_plan.py` pour passer les targets cumulés

**Prérequis** :
- Modifier `_select_recipe_for_slot()` pour recevoir le budget restant au lieu du budget total
- Ordre de sélection : fixer un ordre (petit-déj → déjeuner → dîner → collation) ou optimiser l'ordre
- Recalculer `target_macro_ratios` après chaque sélection dans la boucle de `select_recipes()`
- Le LP `scale_portions()` reçoit déjà les targets jour — pas de changement nécessaire

**Complexité** : basse-moyenne. Pas de nouveau modèle, juste une boucle séquentielle au lieu de calls indépendants.

## TODO v2c: Extraction des paramètres tunables (refactor)

**Problème** : ~13 constantes sont hardcodées en inline dans le code (magic numbers). Pas de visibilité centralisée, impossible de les exposer à l'utilisateur ou de les ajuster sans modifier le code.

**Objectif** : extraire TOUTES les variables tunables en constantes nommées, centralisées, pour pouvoir à terme les exposer en config utilisateur.

### Paramètres identifiés par fichier :

**`src/nutrition/recipe_db.py`** (6 inline) :
- Scoring weights : macro_fit=0.40, freshness=0.30, cuisine=0.20, usage=0.10 (l.472-476)
- Protein emphasis multiplier : 2× dans score_macro_fit (l.412)
- Fetch limit : multiplier=3, buffer=10 (l.148)

**`src/nutrition/calculations.py`** (2 inline) :
- FAT_PCT_OF_TOTAL : 0.20-0.25 par goal_type (l.324-327)
- Fat floor : 0.6g/kg (l.335)

**`skills/meal-planning/scripts/generate_day_plan.py`** (2 inline) :
- Default max_prep_time : 60 (l.203), 45 (l.330)

**`skills/meal-planning/scripts/generate_custom_recipe.py`** (2 inline) :
- LLM temperature : 0.7 (l.171)
- LLM max_tokens : 2000 (l.170)

### Déjà nommés (OK) :
- `MACRO_TOLERANCE_*` (validators.py) : protein=0.05, fat=0.10, calories=0.10, carbs=0.20
- `MACRO_RATIO_TOLERANCE_STRICT/WIDE` (generate_day_plan.py) : 0.20 / 0.50
- `MIN/MAX_SCALE_FACTOR` (meal_plan_optimizer.py) : 0.50 / 3.00
- `WEIGHT_*` (portion_optimizer.py) : protein=2.0, fat=2.0, calories=1.0, carbs=0.5, meal_balance=1.5
- `FRESHNESS_CAP_DAYS` (recipe_db.py) : 30
- `SNACK_STRUCTURE_CALORIE_THRESHOLD` (generate_week_plan.py) : 2500
- `CALORIE_RANGE_MIN_DIVISOR/MAX_MULTIPLIER` (generate_day_plan.py) : 3 / 2

**Phase future** : regrouper toutes ces constantes dans un fichier `src/nutrition/config.py` ou les stocker en DB (table `user_preferences`) pour les rendre modifiables par utilisateur.

---

## Feature: Recettes favorites + vue détail ← CURRENT

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
