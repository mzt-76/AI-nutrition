# Product Requirements Document: AI Nutrition Assistant

**Version:** 3.2
**Date:** March 12, 2026
**Status:** Production — Deployed on Render
**Author:** AI-Nutrition Team

---

## 1. Executive Summary

AI Nutrition Assistant is a personalized, conversational nutrition coach powered by AI. It creates weekly meal plans, tracks daily nutritional intake, adapts recommendations based on real-world results, and provides science-backed nutritional guidance — all through natural conversation in French.

The product combines advanced AI agent capabilities (progressive disclosure skills, RAG, long-term memory, generative UI) with domain-specific nutritional science to deliver a coaching experience that rivals human nutritionists.

**Core Value Proposition:**
> "Un nutritionniste IA qui te connaît, s'adapte à toi, et génère des plans repas personnalisés avec recettes et listes de courses — en tenant compte de tes préférences et résultats réels."

**Current Goal:** Production deployment complete — responsive web app deployed on Render with daily tracking, meal plan consultation, and favorite recipes. Next: TWA (Android APK) for easy distribution to family & friends.

**Dual Purpose:**
1. **Portfolio showcase** — Full-stack app built from scratch to deployment (Python + React + Supabase + AI agent)
2. **Functional MVP** — Usable product for family/friends, with potential to scale commercially if validated

---

## 2. Mission & Principles

**Mission:** Democratize access to personalized, science-based nutritional coaching through an AI agent that learns, adapts, and guides — making professional-grade nutrition guidance accessible and affordable.

**Core Principles:**

1. **Science-First:** Mifflin-St Jeor for BMR, ISSN/AND/EFSA/WHO validated formulas. Citations in docstrings.
2. **Adaptive Learning:** Weekly adjustments based on weight trends, energy, hunger, adherence, and subjective feedback.
3. **User Safety:** Hard constraints — min 1200 kcal (women), 1500 kcal (men), zero tolerance allergen violations.
4. **Personalization Over Prescriptivism:** Respect preferences (dietary restrictions, favorites, cooking time, cuisines).
5. **Transparency:** Always explain the "why" behind recommendations using RAG-retrieved scientific backing.

---

## 3. Target Users

### Phase 1 — MVP (Current)
**Profile:** Creator + Family & close friends
- Non-technical smartphone users
- General nutrition awareness, not specialists
- Goals: personalized meal plans, weight management, muscle gain, better habits
- Pain points: generic diet plans, inconsistent results, lack of accountability
- **Distribution:** APK shared via messaging (WhatsApp/Telegram)

### Phase 2 — Validation (Future)
**Profile:** Extended circle, early adopters
- Mobile-first, French-speaking
- Varied nutrition knowledge
- Validation of product-market fit before commercial investment

### Phase 3 — Commercial (Future)
**Profile:** General public / paying customers
- Subscription model potential
- App Store / Play Store distribution (Capacitor migration if validated)

---

## 4. Architecture

### 4.1 Deployment Strategy

```
Phase 1: Web deploy ✅  →  Phase 2: TWA (APK)  →  Phase 3: Capacitor (if needed)
─────────────────────────────────────────────────────────────────────────────────
Backend: Render (Docker)         (same)              (same)
Frontend: Render (Static CDN)    (same)              (same)
Mobile: Browser access      →  Android APK      →  Native APK + iOS
                            (TWA wrapper)        (if commercial)
```

**Deployed URLs:**
- Frontend: `https://ai-nutrition-frontend-78p7.onrender.com`
- Backend: `https://ai-nutrition-backend-16c2.onrender.com`

**Rationale:**
- Backend is fully decoupled via REST API — frontend choice is independent
- Render Blueprint (`render.yaml`) for declarative 2-service deployment
- TWA wraps the deployed web app in an APK shell (Chrome invisible, no URL bar)
- Zero code change between web and TWA — same codebase
- Capacitor reserved for later if native features needed (push notifications, offline)

### 4.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (React 18 + TypeScript 5)        │
│  Mobile-first responsive PWA — 3 tabs + profile             │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Chat    │  │ Suivi du Jour│  │  Mes Plans   │          │
│  │ Assistant │  │ Daily Track  │  │ Plans/Recettes│          │
│  └──────────┘  └──────────────┘  └──────────────┘          │
│  Generative UI components · Supabase Auth · NDJSON stream   │
└─────────────────────────────────────────────────────────────┘
                              ↕ HTTPS / JWT
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                          │
│  src/api.py — streaming NDJSON, JWT auth, rate limiting     │
│  Endpoints: /api/agent, /api/conversations, /api/meal-plans │
│             /api/daily-log, /api/favorite-recipes            │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                AI AGENT (Pydantic AI)                         │
│  6 tools: load_skill, read_skill_file, list_skill_files,    │
│           run_skill_script, fetch_my_profile, update_profile │
│  Progressive disclosure · mem0 memories · Generative UI      │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│              SKILLS (Progressive Disclosure)                  │
│  nutrition-calculating · meal-planning · weekly-coaching     │
│  knowledge-searching · body-analyzing · skill-creator        │
│  Each: SKILL.md + scripts/ + references/                     │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                    DATA LAYER (Supabase)                      │
│  PostgreSQL + pgvector + RLS on all 17 tables               │
│  user_profiles · meal_plans · recipes · daily_food_log       │
│  conversations · messages · weekly_feedback                   │
│  openfoodfacts_products (275K) · ingredient_mapping          │
│  mem0 (long-term memory) · documents (RAG vectorstore)       │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Directory Structure

```
AI-nutrition/
├── src/                            # Backend
│   ├── agent.py                    # Pydantic AI agent (6 tools, progressive disclosure)
│   ├── api.py                      # FastAPI (streaming, JWT, conversations)
│   ├── tools.py                    # Profile tools (fetch/update)
│   ├── prompt.py                   # System prompt
│   ├── clients.py                  # LLM, DB, memory clients
│   ├── db_utils.py                 # DB operations (conversations, messages, rate limiting)
│   ├── ui_components.py            # Generative UI marker extraction
│   ├── skill_loader.py             # Skill discovery & progressive disclosure
│   ├── skill_tools.py              # Skill tool implementations
│   ├── nutrition/                  # Domain logic (pure functions)
│   │   ├── calculations.py         # BMR, TDEE, macros
│   │   ├── adjustments.py          # Weight trends, red flags
│   │   ├── feedback_extraction.py  # Feedback parsing
│   │   ├── validators.py           # Input validation
│   │   ├── recipe_db.py            # Recipe database operations
│   │   ├── meal_distribution.py    # Macro distribution
│   │   ├── constants.py            # 27 tunable pipeline parameters (centralized)
│   │   ├── ingredient_roles.py     # Ingredient → culinary role mapping (MILP)
│   │   ├── portion_optimizer_v2.py # MILP per-ingredient optimizer (scipy.milp)
│   │   ├── portion_scaler.py       # Portion scaling
│   │   ├── openfoodfacts_client.py # OpenFoodFacts API (264K products)
│   │   └── meal_plan_formatter.py  # Output formatting
│   └── RAG_Pipeline/               # Document sync (Google Drive / Local)
│
├── skills/                         # Skill-based progressive disclosure
│   ├── nutrition-calculating/      # BMR/TDEE/macro calculations
│   ├── meal-planning/              # Week plans, day plans, shopping lists, recipes
│   ├── weekly-coaching/            # Adaptive weekly adjustments
│   ├── knowledge-searching/        # RAG + web search
│   ├── body-analyzing/             # GPT-4 Vision body composition
│   └── skill-creator/              # Meta: create new skills
│
├── frontend/                       # React 18 + TypeScript 5 + Vite 5
│   └── src/
│       ├── components/
│       │   ├── chat/               # Chat UI (layout, input, messages, streaming)
│       │   ├── generative-ui/      # 7 UI components (cards, gauges, chips)
│       │   ├── sidebar/            # Conversation sidebar
│       │   └── ui/                 # shadcn/ui primitives
│       ├── pages/                  # Chat, Login, Admin, MealPlanView
│       └── types/                  # TypeScript types (database, generative-ui)
│
├── tests/                          # Deterministic unit tests (718 passing)
├── evals/                          # Real LLM evaluations (scored, on demand)
├── sql/                            # DB migration files
└── .claude/reference/              # Dev documentation
```

---

## 5. Mobile MVP — Feature Specification

### 5.1 Navigation Structure

```
┌─────────────────────────────────────────┐
│  [≡ menu]     AI Nutrition     [👤 profil] │  ← Header
├─────────────────────────────────────────┤
│                                         │
│           (Active tab content)          │
│                                         │
├──────────┬──────────────┬───────────────┤
│  💬 Chat │ 📊 Suivi    │ 📋 Mes Plans  │  ← Bottom tabs
└──────────┴──────────────┴───────────────┘
```

- **3 bottom tabs:** Chat, Suivi du Jour, Mes Plans
- **Profil:** icône dans le header (accessible depuis tous les onglets)
- **Sidebar conversations:** drawer (hamburger menu) — simplifié pour mobile
- **Navigation:** React Router, tab state preserved on switch

### 5.2 Tab 1 — Chat (Assistant IA)

**Status:** Exists, needs mobile responsive adaptation

**Features:**
- Conversation avec l'agent IA (streaming NDJSON)
- Saisie texte + microphone (speech-to-text existant)
- Generative UI components inline (NutritionSummaryCard, MacroGauges, MealCard, DayPlanCard, etc.)
- Historique des conversations (drawer latéral)
- QuickReplyChips pour suggestions rapides
- Bouton favori (❤️) sur les MealCard pour sauvegarder en recette favorite

**Mobile adaptations needed:**
- Layout full-width, no sidebar by default
- Input bar sticky en bas
- Messages scrollables
- Drawer pour l'historique (swipe ou hamburger)

### 5.3 Tab 2 — Suivi du Jour (Daily Tracking)

**Status:** New feature

**Purpose:** Visualiser et compléter le suivi nutritionnel quotidien — calories et macros consommés vs objectifs.

**UI Components:**
- **Date selector** en haut (aujourd'hui par défaut, navigation jour par jour)
- **Jauges circulaires** : 1 grande pour calories globales + 3 petites pour protéines/glucides/lipides
  - Affichage: consommé / objectif (ex: 1450 / 2800 kcal)
  - Couleur: vert (dans les clous), orange (écart modéré), rouge (écart important)
- **Liste des repas loggés** : chaque entrée montre l'aliment/repas + macros
- **Plan du jour** (si un meal plan existe pour cette date) :
  - Chaque repas prévu affiché avec un **bouton ✓ (tic vert)** pour valider
  - Valider = ajoute automatiquement les macros connues de la recette dans `daily_food_log`
- **Bouton "Ajouter un repas"** → ouvre le chat pré-rempli avec "J'ai mangé..." pour saisie libre

**Data Flow:**
```
Validation plan (✓)  ──→  Agent ajoute macros connues  ──→  daily_food_log
Saisie libre (chat)  ──→  Agent cherche OpenFoodFacts  ──→  daily_food_log
                                                              ↓
                                                     Jauges mises à jour
```

**Backend:**
- Nouvelle table `daily_food_log` (voir section 6)
- Nouveaux endpoints: `GET /api/daily-log?date=YYYY-MM-DD&user_id=...`, `POST /api/daily-log`
- L'agent utilise OpenFoodFacts (275K produits FR) pour résoudre les macros des aliments libres

### 5.4 Tab 3 — Mes Plans (Plans, Recettes, Courses)

**Status:** Partially exists (MealPlanView page), needs expansion

**Sub-sections (sous-onglets ou accordéon) :**

#### 5.4.1 Plans de la Semaine
- Liste des meal plans sauvegardés (fetch direct Supabase, pas via agent)
- Chaque plan: date de début, nb jours, calories/jour
- Clic → vue détaillée avec DayPlanCard par jour
- Endpoint existant: `GET /api/meal-plans/{plan_id}`
- Nouveau: `GET /api/meal-plans?user_id=...` (liste)

#### 5.4.2 Recettes Favorites
- Liste des recettes sauvegardées par l'utilisateur
- Deux chemins de sauvegarde:
  - **Bouton ❤️** sur MealCard dans le chat → sauvegarde instantanée
  - **Commande vocale/texte** : "Sauvegarde cette recette" → l'agent la marque
- Chaque recette: nom, temps de préparation, macros, ingrédients
- Nouveau: table `favorite_recipes` ou flag dans `recipes` (voir section 6)
- Endpoint: `GET /api/favorite-recipes?user_id=...`

#### 5.4.3 Listes de Courses
- Listes de courses générées par le skill meal-planning
- Liées au plan de la semaine correspondant
- Affichage par catégorie (fruits/légumes, protéines, féculents, etc.)
- Checkbox pour cocher les articles achetés (état local, optionnel en DB)
- Endpoint: `GET /api/shopping-lists?user_id=...`

### 5.5 Profil Utilisateur

**Status:** Exists in DB, needs dedicated UI

**Accès:** Icône dans le header du chat

**Contenu:**
- Infos biométriques (âge, genre, poids, taille, niveau d'activité)
- Objectifs actuels (macros cibles, type de régime)
- Préférences (allergies, aliments détestés, favoris, cuisines, temps de préparation)
- Bouton "Recalculer mes besoins" → ouvre le chat avec prompt pré-rempli
- Déconnexion

---

## 6. Database Changes

### 6.1 New Table: `daily_food_log`

```sql
CREATE TABLE daily_food_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    log_date DATE NOT NULL,
    meal_type TEXT NOT NULL,  -- 'petit_dejeuner', 'dejeuner', 'collation', 'diner'
    food_name TEXT NOT NULL,
    calories NUMERIC NOT NULL DEFAULT 0,
    protein_g NUMERIC NOT NULL DEFAULT 0,
    carbs_g NUMERIC NOT NULL DEFAULT 0,
    fat_g NUMERIC NOT NULL DEFAULT 0,
    source TEXT,  -- 'plan_validation', 'manual_chat', 'openfoodfacts'
    meal_plan_id UUID REFERENCES meal_plans(id),  -- if from plan validation
    recipe_id UUID REFERENCES recipes(id),         -- if from a known recipe
    created_at TIMESTAMPTZ DEFAULT now()
);

-- RLS
ALTER TABLE daily_food_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own food log"
    ON daily_food_log FOR ALL
    USING (auth.uid() = user_id);

-- Index for daily queries
CREATE INDEX idx_daily_food_log_user_date
    ON daily_food_log(user_id, log_date);
```

### 6.2 New Table: `favorite_recipes`

```sql
CREATE TABLE favorite_recipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    recipe_id UUID REFERENCES recipes(id),  -- null if custom (from chat)
    name TEXT NOT NULL,
    category TEXT,
    nutrition JSONB,  -- {calories, protein_g, carbs_g, fat_g}
    servings INT,
    ingredients JSONB,
    instructions JSONB,
    prep_time INT,
    tags TEXT[],
    source TEXT,  -- 'recipe_db', 'agent_generated', 'user_saved'
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, recipe_id)  -- prevent duplicates from recipe_db
);

-- RLS
ALTER TABLE favorite_recipes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own favorites"
    ON favorite_recipes FOR ALL
    USING (auth.uid() = user_id);
```

### 6.3 New Table: `shopping_lists`

```sql
CREATE TABLE shopping_lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    meal_plan_id UUID REFERENCES meal_plans(id),
    week_start DATE,
    items JSONB NOT NULL,  -- [{category, name, quantity, unit, checked}]
    created_at TIMESTAMPTZ DEFAULT now()
);

-- RLS
ALTER TABLE shopping_lists ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own shopping lists"
    ON shopping_lists FOR ALL
    USING (auth.uid() = user_id);
```

---

## 7. API Specification

### 7.1 Existing Endpoints (no change)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Service health check |
| `POST` | `/api/agent` | Streaming agent chat (NDJSON) |
| `GET` | `/api/conversations?user_id=` | List user conversations |
| `GET` | `/api/meal-plans/{plan_id}` | Fetch single meal plan |

### 7.2 New Endpoints

#### Daily Food Log

```
GET  /api/daily-log?user_id=<uuid>&date=<YYYY-MM-DD>
→ { date, totals: {calories, protein_g, carbs_g, fat_g}, entries: [...] }

POST /api/daily-log
← { user_id, log_date, meal_type, food_name, calories, protein_g, carbs_g, fat_g, source, meal_plan_id?, recipe_id? }
→ { id, ...created entry }

DELETE /api/daily-log/{entry_id}
→ { success: true }
```

#### Meal Plans (list)

```
GET  /api/meal-plans?user_id=<uuid>
→ [{ id, week_start, created_at, target_calories_daily, notes }]
```

#### Favorite Recipes

```
GET  /api/favorite-recipes?user_id=<uuid>
→ [{ id, name, category, nutrition, prep_time, tags, created_at }]

POST /api/favorite-recipes
← { user_id, recipe_id?, name, nutrition, ingredients, instructions, ... }
→ { id, ...created entry }

DELETE /api/favorite-recipes/{recipe_id}
→ { success: true }
```

#### Shopping Lists

```
GET  /api/shopping-lists?user_id=<uuid>
→ [{ id, meal_plan_id, week_start, items, created_at }]

GET  /api/shopping-lists/{list_id}
→ { id, items: [{category, name, quantity, unit, checked}], ... }
```

All new endpoints require JWT authentication (same pattern as existing endpoints).

---

## 8. Tech Stack

### Backend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Agent Framework | Pydantic AI 0.0.53 | Agent orchestration, tool routing |
| API | FastAPI | REST API, streaming NDJSON |
| LLM | OpenAI / Anthropic | Chat, vision, skill-level calls |
| Embeddings | OpenAI text-embedding-3-small | RAG vectorization |
| Database | Supabase (PostgreSQL + pgvector) | All data + vector search |
| Long-Term Memory | mem0 | Cross-session preference tracking |
| Web Search | Brave Search API | Recent nutritional information |
| Food Database | OpenFoodFacts | 264K French products for macro lookup |
| Optimizer | scipy.optimize.milp | Per-ingredient MILP portion optimization |

### Frontend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | React 18 + TypeScript 5 | UI components |
| Build | Vite 5 | Fast dev/build |
| UI Library | shadcn/ui + Radix | Component primitives |
| Styling | Tailwind CSS 3 | Utility-first CSS |
| Charts | Recharts | Circular gauges, data viz |
| State | React Query | Server state management |
| Routing | React Router 6 | Client-side navigation |
| Validation | Zod | Runtime type validation |
| Auth | Supabase Auth | Email/password + Google OAuth |

### Mobile Distribution

| Phase | Technology | Purpose |
|-------|-----------|---------|
| Phase 1 | Responsive web | Browser access |
| Phase 2 | TWA (Bubblewrap/PWABuilder) | Android APK from web |
| Phase 3 | Capacitor (if needed) | Native APK + push notifications |

### Dev & Testing

| Tool | Purpose |
|------|---------|
| pytest + pytest-asyncio | Unit tests (718 passing) |
| pydantic-evals | LLM behavior evaluation (21 datasets) |
| ruff | Linting + formatting |
| mypy | Type checking |
| ESLint | Frontend linting |

---

## 9. Skills System

6 skill domains, each independently testable and extendable:

| Skill | Scripts | Purpose |
|-------|---------|---------|
| `nutrition-calculating` | `calculate_nutritional_needs` | BMR, TDEE, macro targets |
| `meal-planning` | `generate_day_plan`, `generate_week_plan`, `generate_shopping_list`, `generate_custom_recipe`, `fetch_stored_meal_plan`, `select_recipes`, `validate_day`, `scale_portions`, `seed_recipe_db` | Full meal planning pipeline (see 9.1) |
| `weekly-coaching` | `calculate_weekly_adjustments`, `set_baseline` | Adaptive weekly feedback |
| `knowledge-searching` | `retrieve_relevant_documents`, `web_search` | RAG + Brave search |
| `body-analyzing` | `image_analysis` | GPT-4 Vision body composition |
| `skill-creator` | `init_skill`, `package_skill`, `quick_validate` | Meta: create new skills |

**Pattern:** Agent calls `load_skill(name)` → reads SKILL.md → calls `run_skill_script(name, script, params)`. Adding a new skill = only touch `skills/<name>/`.

### 9.1 Meal-Planning Pipeline (v2f)

```
1. select_recipes()     — sequential selection with v2b sliding macro budget
                          (each slot adjusts targets based on previously selected meals)
2. scale_portions()     — MILP per-ingredient optimizer (portion_optimizer_v2.py)
                          - Variables: one per scalable ingredient (not per recipe)
                          - Culinary roles: protein [0.5×–2.0×], starch [0.3×–2.5×],
                            vegetable [0.7×–1.5×], fat_source [0.2×–1.5×], fixed [1.0×]
                          - Discrete items (eggs, slices) → integer MILP variables
                          - Divergence constraints: protein↔starch, protein↔vegetable,
                            starch↔vegetable limited to 2× ratio
                          - Fallback: uniform calorie-based scaling if infeasible
3. validate_day()       — macro tolerance check per meal + day totals
4. repair loop          — swap worst meal if validation fails (max 3 retries)
```

**Recipe DB:** 712 OFF-validated recipes across 4 meal types × 3 diet types × 15+ cuisines. All tunable parameters in `src/nutrition/constants.py` (27 constants).

---

## 10. Generative UI

Agent emits `<!--UI:Component:{json}-->` markers in text → backend extracts → streams as `ui_component` NDJSON chunks → frontend renders React components.

**7 components:** NutritionSummaryCard, MacroGauges, MealCard, DayPlanCard, WeightTrendIndicator, AdjustmentCard, QuickReplyChips

All props validated with Zod before rendering. Zone-based layout (top, inline, bottom).

---

## 11. Security

### Implemented
- JWT authentication via Supabase Auth (verify_token in API)
- RLS enabled on ALL tables (13+) — per-user data isolation
- Input validation on all tool parameters
- Allergen zero tolerance in recipe generation
- Minimum calorie floors (1200W / 1500M)
- Rate limiting on agent endpoint
- CORS configuration
- API keys in environment variables

### Safety Constraints (Hardcoded)
```python
MIN_CALORIES_WOMEN = 1200
MIN_CALORIES_MEN = 1500
ALLERGEN_ZERO_TOLERANCE = True
DISLIKED_FOODS_FILTERED = True
```

---

## 12. Implementation Roadmap (1 week)

### Day 1-2: Frontend Mobile Refactoring
- [ ] Responsive mobile-first layout (bottom tabs, sticky input, full-width)
- [ ] 3-tab navigation: Chat, Suivi du Jour, Mes Plans
- [ ] Profile icon in header
- [ ] Sidebar → drawer for mobile
- [ ] Test on mobile viewport (Chrome DevTools)

### Day 3: Database + Backend
- [ ] Create `daily_food_log` table + RLS
- [ ] Create `favorite_recipes` table + RLS
- [ ] Create `shopping_lists` table + RLS
- [ ] New API endpoints: daily-log, favorite-recipes, shopping-lists, meal-plans list
- [ ] Agent integration: log food via chat → OpenFoodFacts → daily_food_log

### Day 4-5: Suivi du Jour + Mes Plans
- [ ] Circular gauges (calories + macros) with consumed vs target
- [ ] Daily meal log list
- [ ] Plan validation (✓ button) → auto-log macros
- [ ] "Ajouter un repas" → chat with pre-filled prompt
- [ ] Mes Plans: plan list, recipe favorites (❤️ button), shopping lists

### Day 6: Integration + Polish
- [ ] Favorite recipe save from chat (❤️ on MealCard + vocal command)
- [ ] End-to-end testing (chat → log → gauge update)
- [ ] UI polish, animations, loading states
- [ ] Mobile testing on real device

### Day 7: Deployment ✅
- [x] Backend deploy (Render — Docker web service)
- [x] Frontend deploy (Render — static site CDN)
- [x] Environment variables, DNS, CORS config
- [x] Supabase Auth prod (Site URL, Redirect URLs, Google OAuth published)
- [x] CI/CD pipeline green (GitHub Actions: ruff, ESLint, pytest, Docker builds)
- [x] Production DB cleaned (test data removed, admin set)
- [ ] TWA generation (PWABuilder or Bubblewrap) → APK
- [ ] Send APK to family/friends for testing

---

## 13. Success Metrics

### MVP (Phase 1)
- App deployed and accessible via URL + APK
- 3+ family members actively using it
- Daily food logging works end-to-end
- Meal plans consultable from "Mes Plans" tab
- Chat assistant responds correctly to nutrition queries

### Validation (Phase 2)
- User retention: >50% still using after 2 weeks
- Feature usage: daily tracking used >3x/week per active user
- User feedback: "useful" rating from >70% of testers
- Technical: <2s response time for non-AI endpoints, <10s for agent streaming start

---

## 14. Future Features — Post-MVP

### 14.1 RAG Personnelle par Utilisateur (Documents Drive)

**Problème :** Aujourd'hui la base de connaissances RAG est globale — seul l'admin alimente un Drive partagé, tous les utilisateurs y accèdent. Les utilisateurs ne peuvent pas personnaliser l'agent avec leurs propres documents (ordonnances, bilans sanguins, régimes spécifiques).

**Vision :** Chaque utilisateur connecte son Google Drive. Les documents déposés dans un dossier dédié sont automatiquement indexés et utilisés par **son** agent uniquement, en complément de la base de connaissances globale.

**Architecture cible :**
```
Base globale (admin)          →  Tous les agents (articles scientifiques, guides)
Drive personnel (utilisateur) →  Son agent uniquement (ordonnances, bilans, régimes)
                                       ↓
                              Résultats combinés : global + personnel
```

**Changements requis :**

1. **DB : ajouter `user_id` à `documents`** + mettre à jour RLS pour filtrer par utilisateur
2. **OAuth Google Drive par utilisateur** — chaque user autorise l'accès à son propre Drive (pas seulement l'admin)
3. **Modifier `match_documents` RPC** — combiner résultats globaux (`user_id IS NULL`) + personnels (`user_id = auth.uid()`)
4. **Drive watcher multi-utilisateur** — un watcher par utilisateur connecté, ou un watcher central qui route par `user_id`
5. **UI : onglet "Documents" dans Bibliothèque** — lien vers le Drive, statut de synchronisation, liste des documents indexés

**Priorité :** Phase 2 (post-déploiement MVP)

**Effort estimé :** Migration DB + OAuth multi-user + UI = feature complète

---

**Version:** 3.2 | **Updated:** 2026-03-12
