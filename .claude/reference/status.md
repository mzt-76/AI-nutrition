# Current Status

**Phase:** Production — Deployed on Render (frontend + backend)
**Full roadmap:** See `PRD.md` section 12

**What's done:**
- Backend complete: FastAPI + Pydantic AI agent + 6 skills + 19 scripts + JWT auth + RLS
- React frontend: chat + streaming + Supabase Auth + generative UI (7 components)
- Multi-user isolation verified, 718 unit tests passing, 21 eval datasets
- OpenFoodFacts: 264K products (nettoyés Atwater), 1000+ cached ingredient mappings, online API fallback
- Database: 17 tables (incl. rag_pipeline_state), all RLS-enabled
- Generative UI committed (7 components, tests, evals)
- PRD v3.1 + README updated (EN + FR)

**Mobile MVP — Implementation Steps:**

### Step 1: Navigation mobile + responsive ✅
### Step 2: Tables DB + endpoints backend ✅
### Step 3: Onglet Suivi du Jour ✅
### Step 4: Onglet Mes Plans ✅
### Step 5: Integration + polish + deploy ✅
### Step 5b: Pre-deploy audit + PWA readiness ✅

### Step 6: Deployment infrastructure ✅
- [x] Créer projet Supabase production (`bxmihxyishfvmvswxfby`)
- [x] Schéma prod : `sql/0-all-tables.sql` exécuté (toutes les tables + RPC + indexes + RLS)
- [x] Seed données référence : `scripts/copy_reference_tables.sh` (dev → CSV → prod via `psql \copy`)
  - recipes: 712 rows, openfoodfacts_products: 264,495 rows, ingredient_mapping: 1,217 rows
- [x] `.env prod` configuré (DATABASE_URL, Supabase keys, VITE_SUPABASE_ANON_KEY prod)
- [x] Docker infrastructure complète :
  - `Dockerfile` (backend, port 8001), `frontend/Dockerfile` (multi-stage build + nginx), `src/RAG_Pipeline/Dockerfile`
  - `.dockerignore` (root, frontend/, src/RAG_Pipeline/)
  - `frontend/nginx.conf` pour servir le React SPA
  - `docker-compose.yml` : 3 services (backend:8001, rag-pipeline, frontend:8080)
  - `docker-compose.caddy.yml` : déploiement cloud avec Caddy reverse proxy + auto SSL
  - `Caddyfile` : hostnames env-driven routant vers backend/frontend
  - `deploy.py` : script de déploiement (modes local vs cloud)
  - `.env.example` complet avec documentation
  - `src/RAG_Pipeline/docker_entrypoint.py` (modes continuous/single run)
  - `src/RAG_Pipeline/common/state_manager.py` (persistance d'état DB-backed)
- [x] Migration DB pour table `rag_pipeline_state` (créée en prod)
- [x] RAG Pipeline aligné sur version cours v6 :
  - `file_watcher.py` : state_manager integration, `save_state()`, `check_for_changes()` amélioré
  - `drive_watcher.py` : idem + `ServiceAccountCredentials` pour déploiement cloud
  - `db_handler.py` + `text_processor.py` : détection prod/dev pour chargement `.env`
  - `state_manager.py` : docstrings complets (version cours)
- [x] Tester le déploiement Docker complet (`docker compose up`) — 3 containers running
- [x] RAG pipeline Google Drive fonctionnel (service account auth + scan fichiers)
- [x] Créer le guide Docker (`.claude/reference/docker-guide.md`)
- [x] CI/CD pipeline (GitHub Actions : 11 workflows — lint, tests, coverage, Docker builds, security, license, bundle size, deploy template)
- [x] CI fixes: pinned ruff==0.1.15, pydantic-ai[anthropic]==1.39.0, anthropic==0.75.0, ESM tailwind import, mypy continue-on-error
- [x] Render deployment:
  - `render.yaml` Blueprint (2 services: static frontend + Docker backend)
  - Frontend: `https://ai-nutrition-frontend-78p7.onrender.com` (static site, Vite build via CDN)
  - Backend: `https://ai-nutrition-backend-16c2.onrender.com` (Docker, FastAPI)
  - `.env.prod` configured (CORS, Supabase prod keys, all API keys)
  - Supabase Auth: Site URL + Redirect URLs configured for prod
  - Google OAuth: consent screen configured, `supabase.co` authorized domain, published to production
- [x] Production DB cleanup: test users/data removed, meuzeretl@gmail.com set as admin
- [x] RLS policies verified between dev and prod (consistent)
- [x] README rewritten (EN + FR) with accurate project numbers (718 tests, 712 recipes, 17 tables, etc.)
- [ ] Smoke test end-to-end
- [x] Langfuse observability (SDK v3 + admin panel link)
- [x] TWA → APK generation + distribution (assetlinks.json + Bubblewrap build)
- [x] TWA fix: assetlinks.json package_name mismatch corrigé (com.ainutrition.app → com.onrender.ai_nutrition_frontend_78p7.twa)

---

## Deferred Issues (from pre-deploy review 2026-03-07)

- [x] **M4. Sync Supabase client dans endpoints async** — ✅ Migré vers `SupabaseAsyncClient`. 81 `.execute()` calls await-ifiés, 16 source files + 14 test files. `get_async_supabase_client()` dans `src/clients.py`, sync client préservé pour `scripts/`.
- [ ] **L5. Ruff E402 — 10 imports pas en haut de fichier** — intentionnel (après `sys.path` setup). Ajouter `# noqa: E402` ou configurer ruff pour ignorer ces fichiers.
- [ ] **L6. Mypy — 140 erreurs pre-existantes** — surtout implicit Optional et types Pydantic AI v2. Nécessite un pass dédié mypy cleanup.

## Perf / UX improvements — streaming UX (issue #10)

Diagnostiqués en analysant le flow `/api/agent`. Le fix critique (proxy buffering) a
été appliqué — ces améliorations restent ouvertes pour fluidifier davantage.

- [ ] **Fix 2 — Découpler `title_task` du chunk `complete: true`** — `src/api.py` dans
  `_stream_agent_response` (~ligne 1482). Actuellement on `await title_task` avant
  d'émettre le chunk final, ce qui laisse le spinner actif pendant 1–3s après la fin
  du streaming. Solution : émettre `complete: true` immédiatement et gérer la mise à
  jour du titre en arrière-plan via `asyncio.create_task` (même pattern que
  `store_request`). `MessageHandling.tsx` n'utilise que `session_id` depuis ce
  chunk, donc safe.

- [ ] **Fix 3 — Vérification JWT locale (PyJWT)** — `src/api.py` fonction
  `verify_token` (~ligne 235). Aujourd'hui chaque requête fait un round-trip HTTP
  vers l'API Supabase Auth (~50–200ms sur Render Starter). Remplacer par une
  vérification locale via `PyJWT` + `SUPABASE_JWT_SECRET` (Dashboard → Settings → API
  → JWT Secret). Garder l'appel HTTP en fallback si le secret est absent.

- [ ] **Fix 4 — `store_message` (user) fire-and-forget** — `src/api.py:460-469`.
  Actuellement on `await store_message(...)` avant de démarrer le `StreamingResponse`,
  ce qui ajoute ~50–100ms au TTFB. Transformer en `asyncio.create_task(...)` +
  `add_done_callback(_log_task_exception)`, identique au pattern `store_request`
  existant.

- [ ] **Fix 5 — Optimiser le rendu markdown pendant le streaming** —
  `frontend/src/components/chat/MessageItem.tsx:109-174`. Le `useMemo` pour
  `ReactMarkdown` dépend de `message.content`, qui change à chaque chunk → parsing
  AST complet à chaque update. Sur longues réponses ça lag. Solution : ajouter une
  prop `isStreaming`, afficher `<span className="whitespace-pre-wrap">` pendant le
  streaming, `ReactMarkdown` uniquement sur les messages finalisés.

## Quick Fixes TODO

- [ ] **Supabase `timeout`/`verify` DeprecationWarning** — `src/clients.py` : le constructeur `AsyncPostgrestClient` reçoit `timeout` et `verify` en params directs, mais les nouvelles versions de `supabase-py` attendent qu'ils soient configurés dans le `httpx.AsyncClient` sous-jacent. Pas bloquant, juste des warnings dans les logs. Fix : passer ces params via `httpx_client` au lieu du constructeur.
- [x] **Tailwind ESLint `require()` error** — Converti en ESM import dans `tailwind.config.ts`.

## Deferred Issues (from pre-deploy audit 2026-03-12)

- [ ] **Architecture: Service_role key → user-scoped tokens** — Le backend utilise `SUPABASE_SERVICE_KEY` pour toutes les opérations DB, ce qui bypass les 60+ RLS policies. RLS ne protège que le frontend (anon_key). Refactor nécessaire : créer un client Supabase par requête avec le JWT de l'utilisateur pour les endpoints user-facing, garder le service_key uniquement pour les opérations admin/système (skills, RAG pipeline). Prérequis : (1) mettre à jour les RLS DELETE policies (`USING (false)` → `USING (auth.uid() = user_id)` pour meal_plans, conversations, messages), (2) ajouter une policy INSERT authenticated sur recipes, (3) adapter les skill scripts pour recevoir le JWT. Rapport complet : `.claude/audits/audit-2026-03-12-0700.md`
- [ ] **requirements.txt: garder `>=` pour l'instant** — L'audit recommandait `==` pour la reproductibilité Docker. Décision : on garde `>=` pour la flexibilité des mises à jour. À reconsidérer si un build Docker casse à cause d'une upgrade silencieuse.

## Improvement Ideas

- [ ] **Macro redistribution quand une recette favorite est pinned** — Quand une recette favorite est forcée dans un slot (Niveau 2), `calculate_meal_macros_distribution` devrait ajuster les cibles macro des slots restants pour compenser le profil fixe de la favorite. Actuellement le MILP optimise tous les slots contre la distribution uniforme originale, ce qui cause un drift carbs/fat quand la favorite a un profil macro atypique (ex: -24% carbs observé en test). Implémentation : après favorite lookup, soustraire les macros de la favorite des cibles journalières, redistribuer le reste sur les slots non-remplis.
- [ ] **Verrouiller les portions des recettes favorites dans le MILP** — Quand l'utilisateur ajoute sa propre recette et l'utilise dans un plan, le MILP modifie les quantités d'ingrédients (ex: huile d'olive réduite de 2 à 1 cuillère, poulet de 215g à 169g). L'utilisateur s'attend à garder sa recette telle quelle. Fix : ajouter un paramètre `locked_recipe_indices` à `optimize_day_portions_v2()` — les recettes verrouillées contribuent leurs macros fixes, seuls les autres repas sont optimisés pour compenser. Option B plus simple : bounds ultra-serrés (0.95–1.05) pour les favorites au lieu du verrouillage complet.

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

## DONE: Favorites management scripts (2026-03-18) ✅

Agent peut désormais lister/rechercher et supprimer les recettes favorites via le chat.
- `get_user_favorites` : liste tous les favoris avec filtre fuzzy par nom
- `remove_favorite_recipe` : supprime par favorite_id ou recipe_name (gestion ambiguïté)
- SKILL.md mis à jour (triggers, paramètres, exemples)
- 15 tests unitaires + 3 evals (100%)

## DONE: Automated bug investigation workflow (2026-03-24) ✅

Workflow complet de gestion des bugs via GitHub Actions + Claude Code :
- `investigate-bug.yml` : enquête auto quand label `user-feedback` ajouté → diagnostic + plan d'implémentation
- `fix-bug.yml` : assistant conversationnel sur l'issue + `/fix` pour créer une PR
- `proactive-monitoring.yml` : scan Langfuse + Supabase toutes les 48h (cron)
- `scripts/investigate_bugs.py` : data fetcher LLM-free (Langfuse traces + Supabase conversations)
- `.github/ISSUE_TEMPLATE/user-feedback.yml` : formulaire de bug report structuré
- 20 tests unitaires, 3 labels GitHub, 5 secrets configurés
- Doc : `docs/bug-investigation-workflow.md`

**TODO pour ce workflow :**
- [ ] **Review PR #3** (fix streaming tab-switch) — code auto-généré par Claude, à vérifier avant merge
- [ ] **Vérifier quota Max** — chaque commentaire sur une issue user-feedback = 1 run Claude (~5-10 min). Surveiller la consommation.
- [ ] **Renouveler le token OAuth** — `CLAUDE_CODE_OAUTH_TOKEN` expire, penser à `claude setup-token` + `gh secret set` quand ça casse

## NEXT: Feature — Recettes favorites + vue détail

### Étape 1 : Vue détail recette + bouton favori
- [x] **Backend**: scripts agent pour lister/supprimer les favoris (get_user_favorites, remove_favorite_recipe)
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

## NEXT v2: Generative UI — composants autonomes hors bulle de chat

Actuellement les composants UI (MacroGauges, DayPlanCard, etc.) sont rendus DANS la bulle de texte.
Idee : les rendre comme des blocs independants dans le flux de conversation, pleine largeur,
entre les bulles de texte. L'agent pourrait repondre avec uniquement des graphiques/cartes
quand c'est plus pertinent que du texte.

- Changement principalement frontend (ComponentRenderer sort du MessageBubble)
- Le backend emet deja des chunks `ui_component` separes — pas de changement necessaire
- Inspiration : apps IA modernes (ChatGPT canvas, Perplexity, etc.)
- Effort estime : ~demi-journee

---

## BACKLOG

- [ ] **Critères de sélection recettes** — vérifier que les filtres (macro ratio, variété, cuisine) sont pertinents et que le pool de 692 recettes offre assez de choix pour tous les profils (perte de poids, prise de masse, vegan, etc.)
- [ ] **Couverture ingredient_roles.py** — 155 mappings sur 1000+ ingrédients validés. Les "unknown" [0.75×–1.25×] sont conservateurs. Enrichir les rôles les plus fréquents pour améliorer l'optimisation MILP.
- [ ] **Import recettes live** — utiliser le pipeline v2e avec les API (Spoonacular, TheMealDB) une fois les clés configurées. Priorité : sources FR (Marmiton, 750g).
- [x] **CI/CD** — GitHub Actions : 11 workflows (lint, tests, coverage, Docker, security, license, bundle size)
- [ ] **Smoke test e2e** — test automatisé du flow complet via Docker
- [x] **TWA → APK** — génération + distribution
- [x] **Langfuse** — observability SDK v3 + admin panel deeplinks
- [x] **Documentation technique** — `docs/twa-digital-asset-links.md` + `docs/concepts-cles-a-maitriser.md` (TWA, MILP, Pydantic AI, Supabase RLS, NDJSON streaming, OpenFoodFacts, Docker/Render)
