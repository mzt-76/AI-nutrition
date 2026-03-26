# Assistant Nutrition IA

> Essayez-le : [ai-nutrition-frontend-78p7.onrender.com](https://ai-nutrition-frontend-78p7.onrender.com)

---

## Le projet

Ce projet est né d'une envie d'apprendre à construire un agent IA de bout en bout. L'idée : un assistant nutritionnel en français capable de calculer vos besoins caloriques, générer des plans repas personnalisés avec des vraies recettes, et suivre vos macros au quotidien.

C'est une première version, construite dans le cadre du cours [AI Agent Mastery](https://dynamous.ai/) de Cole Medin. L'application est fonctionnelle et déployée — vous pouvez la tester directement via le lien ci-dessus.

---

## Ce qu'on peut faire

### Chat — Parler nutrition avec l'IA

L'onglet principal. Vous posez vos questions en français, l'assistant répond avec des conseils fondés sur la science nutritionnelle. Il peut calculer vos besoins (calories, protéines, glucides, lipides), générer un plan repas pour la semaine, créer une liste de courses, ou simplement répondre à vos questions sur la nutrition.

Les réponses incluent des composants visuels interactifs directement dans le chat : résumés nutritionnels, jauges de macros, cartes de recettes.

<p align="center">
  <img src="e2e-screenshots/01-after-login.png" width="70%" alt="Chat — page d'accueil" />
</p>
<p align="center">
  <img src="e2e-screenshots/10-mobile-chat.png" width="30%" alt="Chat — version mobile" />
</p>

### Suivi du Jour — Suivre ses macros

L'onglet Suivi permet de visualiser ce que vous avez mangé dans la journée par rapport à vos objectifs. Une jauge circulaire pour les calories, des barres de progression pour protéines/glucides/lipides.

Pour ajouter un aliment, tapez simplement "j'ai mangé..." — l'assistant cherche les macros dans une base de 264 000 produits français (OpenFoodFacts) et met à jour vos totaux.

<p align="center">
  <img src="e2e-screenshots/02-daily-tracking.png" width="70%" alt="Suivi du Jour — desktop" />
</p>
<p align="center">
  <img src="e2e-screenshots/11-mobile-tracking.png" width="30%" alt="Suivi du Jour — mobile" />
</p>

### Bibliothèque — Plans, recettes et courses

L'onglet Bibliothèque regroupe tout ce que l'assistant a généré pour vous :

- **Plans** — vos plans repas hebdomadaires, avec le détail jour par jour (recettes, ingrédients, macros par repas)
- **Recettes** — vos recettes favorites sauvegardées depuis le chat
- **Courses** — les listes de courses générées à partir de vos plans

<p align="center">
  <img src="e2e-screenshots/07-meal-plan-detail.png" width="70%" alt="Détail d'un plan repas" />
</p>
<p align="center">
  <img src="e2e-screenshots/05-bibliotheque-recettes.png" width="70%" alt="Recettes favorites" />
</p>

---

## Comment c'est construit

### Architecture

```
Frontend (React 18 + TypeScript + Vite)
  │  3 onglets : Chat · Suivi du Jour · Bibliothèque
  │  Auth Supabase · Generative UI · Streaming NDJSON
  │
  ↕  HTTPS / JWT
  │
Backend (FastAPI)
  │  Streaming NDJSON · Auth JWT · Rate limiting
  │
  ↕
  │
Agent Pydantic AI (6 outils, système de skills)
  │
  ├── nutrition-calculating/    Calcul besoins (Mifflin-St Jeor)
  ├── meal-planning/            Plans repas + optimisation MILP
  ├── food-tracking/            Suivi alimentaire quotidien
  ├── shopping-list/            Listes de courses
  ├── weekly-coaching/          Feedback hebdomadaire adaptatif
  ├── knowledge-searching/      RAG + recherche web
  └── body-analyzing/           Analyse photo (GPT-4 Vision)
  │
  ↕
  │
Données
  ├── Supabase (PostgreSQL + pgvector) — 17 tables, RLS
  ├── OpenFoodFacts — 264K produits français
  └── mem0 — mémoire inter-sessions
```

L'agent ne contient pas de logique métier. Il charge un fichier `SKILL.md` pour découvrir les scripts disponibles, puis appelle `run_skill_script()` qui injecte automatiquement les clients partagés. Ajouter une fonctionnalité = ajouter un dossier dans `skills/`.

### Stack technique

| Couche | Technologie |
|---|---|
| **Frontend** | React 18, TypeScript 5, Vite 5, shadcn/ui, Tailwind CSS, Recharts, Zod |
| **Backend** | FastAPI, Pydantic AI, Python 3.11+ |
| **LLMs** | Claude Haiku 4.5 (agent) + GPT-4o-mini (vision, embeddings) |
| **Base de données** | Supabase (PostgreSQL + pgvector), RLS sur 17 tables |
| **Auth** | Supabase Auth (email/password + Google OAuth) |
| **Données alimentaires** | OpenFoodFacts (264K produits, recherche locale) |
| **Optimisation** | SciPy MILP pour le portionnement des recettes |
| **Tests** | pytest (718 tests) + pydantic-evals (21 fichiers) |
| **CI/CD** | GitHub Actions + Render |

### Quelques chiffres

| | |
|---|---|
| 718 tests unitaires | 7 domaines de compétences |
| 712 recettes validées | 264 495 produits OpenFoodFacts |
| 7 composants Generative UI | 17 tables (toutes avec RLS) |

---

## Quick Start

### Prérequis

- Python 3.11+
- Node.js 18+
- Un projet Supabase (le plan gratuit suffit)
- Clés API : Anthropic, OpenAI (embeddings + vision), optionnellement Brave Search

### Installation

```bash
git clone https://github.com/mzt-76/AI-nutrition.git
cd AI-nutrition

# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..
```

### Configuration

```bash
cp .env.example .env
# Renseignez vos clés API et identifiants Supabase

cp frontend/.env.example frontend/.env
# Renseignez votre URL Supabase et clé anon
```

### Lancement

```bash
# Backend
uvicorn src.api:app --port 8001 --reload

# Frontend (autre terminal)
cd frontend && npm run dev
```

Le frontend tourne sur `http://localhost:8080`, le backend sur `http://localhost:8001`.

### Tests

```bash
pytest tests/ -v
ruff format src/ tests/ && ruff check src/ tests/ && mypy src/
```

---

## Remerciements

Un remerciement particulier à **Cole Medin** pour son investissement dans la communauté [Dynamous AI](https://dynamous.ai/) et la création de son cours **AI Agent Mastery**, sans lequel ce projet n'aurait pas vu le jour.

Développé en collaboration avec **Claude Code** (Anthropic) — de la conception de l'architecture au debugging, en passant par le design frontend avec le skill `frontend-design`.

Merci aux projets open source sur lesquels cette application s'appuie :
- [Pydantic AI](https://github.com/pydantic/pydantic-ai) — framework agent
- [OpenFoodFacts](https://world.openfoodfacts.org/) — base de données alimentaire ouverte
- [shadcn/ui](https://ui.shadcn.com/) — composants UI
- [Langfuse](https://langfuse.com/) — observabilité LLM
- Sciences nutritionnelles : ISSN, Mifflin et al. (1990), Helms et al. (2014)

---

Créé par **Meuz** — projet personnel construit pour apprendre et permettre à chacun de recevoir des conseils nutrionnels personalisés.
