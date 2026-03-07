# Current Status

**Phase:** Mobile MVP — Frontend refactoring + deployment
**Full roadmap:** See `PRD.md` section 12

**What's done:**
- Backend complete: FastAPI + Pydantic AI agent + 6 skills + 17 scripts + JWT auth + RLS
- React frontend: chat + streaming + Supabase Auth + generative UI (7 components)
- Multi-user isolation verified, 366 unit tests passing, 13 eval datasets
- OpenFoodFacts: 275K products, 546 cached ingredient mappings
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

### Step 6: Deployment infrastructure
- [ ] Préparer la base de données production (Supabase séparé, 14 migrations SQL, seed OpenFoodFacts + recettes)
- [ ] Créer la config de déploiement (Dockerfile/Procfile selon plateforme)
- [ ] Configurer les variables d'environnement production (CORS_ORIGINS, API keys, Supabase)
- [ ] CI/CD pipeline (GitHub Actions : pytest, ruff, npm lint, npm build)
- [ ] Deploy backend (Railway/Fly.io) + frontend (Vercel)
- [ ] Smoke test end-to-end
- [ ] TWA → APK generation + distribution

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
