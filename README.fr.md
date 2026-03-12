# AI Nutrition Assistant

Une application full-stack de coaching nutritionnel par IA — plans repas personnalisés, suivi quotidien des macros et feedback hebdomadaire adaptatif. Construite avec **Pydantic AI**, **React 18**, **FastAPI** et **Supabase**.

> Réalisé dans le cadre du cours AI Agent Mastery de Cole Medin et la communauté [Dynamous](https://dynamous.ai/).

---

## Fonctionnalités

- **Coach IA conversationnel** — posez n'importe quelle question sur la nutrition en français, obtenez des réponses fondées sur la science
- **Calcul des besoins nutritionnels** via Mifflin-St Jeor (MB, TDEE, macros) avec inférence automatique de l'objectif
- **Génération de plans repas hebdomadaires** avec 712 recettes, optimisation MILP des portions et filtrage allergènes/préférences
- **Création de listes de courses** à partir des plans repas avec agrégation et catégorisation des ingrédients
- **Suivi quotidien** — enregistrez vos repas par chat, visualisez vos macros en temps réel avec des jauges de progression
- **Adaptation hebdomadaire** basée sur les tendances de poids, la faim, l'énergie, le sommeil et le taux d'adhérence
- **Recherche de connaissances nutritionnelles** via RAG (Supabase pgvector) et recherche web (Brave API)
- **Analyse de composition corporelle** à partir de photos (GPT-4 Vision)
- **Mémorisation des préférences** entre sessions (mémoire long-terme mem0)
- **Generative UI** — 7 composants interactifs riches (résumés nutritionnels, jauges macros, cartes repas, plans journaliers) affichés directement dans le chat

---

## Architecture

```
Frontend (React 18 + TypeScript 5 + Vite 5)
  │  Onglets : Chat · Suivi du Jour · Mes Plans
  │  Supabase Auth · Generative UI · Streaming NDJSON
  │
  ↕  HTTPS / JWT
  │
Backend (FastAPI)
  │  Streaming NDJSON · Auth JWT · Rate limiting
  │  /api/agent · /api/conversations · /api/meal-plans
  │  /api/daily-log · /api/favorite-recipes · /api/shopping-lists
  │
  ↕
  │
Agent Pydantic AI (6 outils, divulgation progressive)
  │
  ├── nutrition-calculating/    MB, TDEE, macros (Mifflin-St Jeor + ISSN)
  ├── meal-planning/            Plans semaine/jour, optimiseur MILP, recettes
  ├── food-tracking/            Suivi alimentaire, résumés macros
  ├── shopping-list/            Agrégation d'ingrédients
  ├── weekly-coaching/          Ajustements adaptatifs + détection signaux d'alerte
  ├── knowledge-searching/      RAG (Supabase pgvector) + recherche web Brave
  └── body-analyzing/           Estimation composition corporelle GPT-4 Vision
  │
  ↕
  │
Couche Données
  ├── Supabase (PostgreSQL + pgvector) — 17 tables, RLS sur toutes
  ├── OpenFoodFacts (264K produits français pour macros précis)
  └── mem0 (mémoire inter-sessions)
```

**Pattern clé** : L'agent n'appelle jamais la logique métier directement. Il charge le `SKILL.md` d'une compétence pour découvrir les scripts disponibles, puis appelle `run_skill_script()` qui injecte automatiquement tous les clients partagés. Ajouter une compétence = ne toucher que les fichiers dans `skills/<nom>/`.

---

## Stack Technique

| Couche | Technologie |
|---|---|
| **Frontend** | React 18, TypeScript 5, Vite 5, shadcn/ui, Tailwind CSS, Recharts, Zod |
| **Backend** | FastAPI, Pydantic AI, Python 3.11+ |
| **LLMs** | Claude Haiku 4.5 (agent) + GPT-4o-mini (vision, embeddings) |
| **Base de données** | Supabase (PostgreSQL + pgvector), RLS sur les 17 tables |
| **Authentification** | Supabase Auth (email/mot de passe + Google OAuth), vérification JWT |
| **Données alimentaires** | OpenFoodFacts (264K produits, recherche full-text locale) |
| **Optimisation** | Solveur MILP SciPy pour le portionnement |
| **Mémoire** | mem0 (suivi des préférences inter-sessions) |
| **Recherche web** | Brave Search API |
| **Tests** | pytest (718 tests) + pydantic-evals (21 fichiers d'évals) |
| **CI/CD** | GitHub Actions + Render (site statique + Docker) |
| **Linting** | ruff + mypy + ESLint |

---

## Chiffres du Projet

| Métrique | Nombre |
|---|---|
| Tests unitaires | **718** |
| Fichiers d'évaluation | **21** |
| Domaines de compétences | **7** |
| Scripts de compétences | **15** |
| Composants Generative UI | **7** |
| Recettes en base | **712** (validées OFF) |
| Mappings d'ingrédients | **1 217** (croissance auto) |
| Produits OpenFoodFacts | **264 495** (français, avec données nutritionnelles) |
| Chunks RAG | **485** |
| Tables en base | **17** (toutes avec RLS) |

---

## Démarrage Rapide

### Prérequis

- Python 3.11+
- Node.js 18+ (pour le frontend)
- Un projet Supabase (le plan gratuit suffit)
- Clés API : Anthropic, OpenAI (embeddings + vision), optionnellement Brave Search

### 1. Cloner & Installer

```bash
git clone https://github.com/mzt-76/AI-nutrition.git
cd AI-nutrition

# Backend
python -m venv venv
source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt

# Frontend
cd frontend
npm install
cd ..
```

### 2. Configurer l'Environnement

```bash
cp .env.example .env
# Modifiez .env avec vos clés API et identifiants Supabase

cp frontend/.env.example frontend/.env
# Modifiez frontend/.env avec votre URL Supabase et clé anon
```

### 3. Lancer

```bash
# API Backend
uvicorn src.api:app --port 8001 --reload

# Frontend (terminal séparé)
cd frontend && npm run dev

# Ou CLI seul (pas besoin du frontend)
python -m src.cli
```

Le frontend tourne sur `http://localhost:8080`, le backend sur `http://localhost:8001`.

### 4. Lancer les Tests

```bash
pytest tests/ -v

# Linting
ruff format src/ tests/ && ruff check src/ tests/ && mypy src/
```

---

## Déploiement

Le projet se déploie sur **Render** avec 2 services :
- **Frontend** : Site statique (gratuit) — build Vite servi via CDN
- **Backend** : Service web Docker — FastAPI + Agent + Compétences

Voir `render.yaml` pour la configuration Blueprint.

---

## Structure du Projet

```
AI-nutrition/
├── src/                           # Backend
│   ├── agent.py                   # Agent Pydantic AI (6 outils, ne grossit jamais)
│   ├── api.py                     # FastAPI (streaming NDJSON, JWT, CRUD)
│   ├── tools.py                   # Outils profil (lecture + mise à jour)
│   ├── prompt.py                  # Prompt système (coach nutrition français)
│   ├── clients.py                 # Tous les clients API
│   ├── db_utils.py                # Opérations DB (conversations, messages)
│   ├── ui_components.py           # Extraction des marqueurs Generative UI
│   ├── skill_loader.py            # Découverte & divulgation progressive des compétences
│   ├── nutrition/                 # Logique métier (11.6K LOC)
│   │   ├── calculations.py        # MB, TDEE, macros (Mifflin-St Jeor)
│   │   ├── adjustments.py         # Tendances poids, ajustements hebdo
│   │   ├── recipe_db.py           # CRUD recettes avec filtrage allergènes
│   │   ├── portion_optimizer_v2.py # Optimiseur MILP par ingrédient
│   │   ├── openfoodfacts_client.py # Correspondance locale (264K produits)
│   │   └── ...
│   └── RAG_Pipeline/              # Sync documents (Google Drive + Local)
│
├── skills/                        # Domaines de compétences autonomes
│   ├── nutrition-calculating/     # SKILL.md + scripts/ + references/
│   ├── meal-planning/             # Plan semaine, plan jour, recettes, favoris
│   ├── food-tracking/             # Suivi alimentaire, résumés
│   ├── shopping-list/             # Agrégation d'ingrédients
│   ├── weekly-coaching/           # Feedback adaptatif + protocole signaux d'alerte
│   ├── knowledge-searching/       # RAG + recherche web
│   └── body-analyzing/            # Analyse GPT-4 Vision
│
├── frontend/                      # React 18 + TypeScript 5 + Vite 5
│   └── src/
│       ├── components/generative-ui/ # 7 composants UI riches
│       ├── components/ui/         # Primitives shadcn/ui
│       ├── hooks/                 # useDailyTracking, useAuth, etc.
│       └── pages/                 # Chat, DailyTracking, MyPlans, MealPlanView
│
├── tests/                         # 718 tests unitaires
├── evals/                         # 21 fichiers d'évaluation (scoring LLM)
├── sql/                           # Schéma DB + migrations
├── render.yaml                    # Render Blueprint (2 services)
├── Dockerfile                     # Image Docker backend
└── CLAUDE.md                      # Règles de développement & standards
```

---

## Contraintes de Sécurité (Hardcodées)

```python
MIN_CALORIES_WOMEN = 1200
MIN_CALORIES_MEN = 1500
ALLERGEN_ZERO_TOLERANCE = True    # Vérifie tous les ingrédients contre les allergènes utilisateur
DISLIKED_FOODS_FILTERED = True    # La DB recettes exclut les aliments non aimés à la requête
```

Ces contraintes sont appliquées dans le code, pas dans les prompts. L'agent ne peut pas les contourner.

---

## Remerciements

- Cours AI Agent Mastery de Cole Medin et la communauté [Dynamous](https://dynamous.ai/)
- Framework [Pydantic AI](https://github.com/pydantic/pydantic-ai)
- Base de données alimentaire ouverte [OpenFoodFacts](https://world.openfoodfacts.org/)
- Science nutritionnelle : ISSN, Mifflin et al. (1990), Helms et al. (2014)

---

## Licence

Ce projet a été construit pour un usage personnel et l'apprentissage. N'hésitez pas à explorer le code, réutiliser les patterns et l'adapter pour vos propres projets.
