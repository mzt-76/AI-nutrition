# Product Requirements Document: AI Nutrition Assistant

**Version:** 2.1
**Date:** February 24, 2026
**Status:** Active Development - FastAPI Backend API + Multi-User Support
**Author:** AI-Nutrition Team

---

## 1. Executive Summary

The AI Nutrition Assistant is an intelligent, conversational nutrition coach that creates personalized weekly meal plans, tracks user progress, and adapts recommendations based on real-world results. Unlike static meal planning apps or one-size-fits-all calculators, this agent learns individual preferences, remembers conversation history, and continuously optimizes nutritional strategies using scientifically-validated methods.

The product combines advanced AI agent capabilities (RAG, long-term memory, tool orchestration) with domain-specific nutritional science to deliver a coaching experience that rivals human nutritionists. Users interact through natural conversation, upload body composition photos for analysis, receive weekly adaptive feedback, and get complete meal plans with recipes and shopping lists.

**Core Value Proposition:**
> "A nutritionist AI that knows you, adapts to you, and generates weekly personalized meal plans with recipes and shopping lists - accounting for your preferences and real-world results."

**MVP Goal:** Production-ready Python agent (Pydantic AI) with skill-based progressive disclosure architecture, eval-validated tool scripts, and adaptive weekly coaching — accessible via Streamlit and CLI.

---

## 2. Mission

**Mission Statement:**
Democratize access to personalized, science-based nutritional coaching by creating an AI agent that combines nutritional expertise with adaptive learning, making professional-grade nutrition guidance accessible, affordable, and continuously improving.

**Core Principles:**

1. **Science-First:** All nutritional recommendations must be grounded in peer-reviewed research, validated formulas (Mifflin-St Jeor for BMR), and established guidelines (ISSN, AND, EFSA, WHO).

2. **Adaptive Learning:** The agent learns from each user's real-world results, adjusting recommendations based on weight changes, energy levels, hunger, adherence, and subjective feedback.

3. **User Safety:** Hard constraints on minimum calories (1200 for women, 1500 for men), zero tolerance for allergen violations, and clear disclaimers that this is guidance, not medical advice.

4. **Personalization Over Prescriptivism:** Respect individual preferences (dietary restrictions, favorite foods, cooking skills, time constraints) while achieving nutritional targets.

5. **Transparency:** Always explain the "why" behind recommendations using scientific backing retrieved from the knowledge base (RAG).

---

## 3. Target Users

### Primary User (Phase 1 - MVP)
**Profile:** Yourself (product creator)
- **Technical Level:** Basic Python knowledge, comfortable with APIs, learning AI development
- **Domain Expertise:** Strong nutritional knowledge, understands BMR/TDEE/macros
- **Goals:** Test and validate the agent's capabilities before extending to others
- **Pain Points:** Need to prove the concept works reliably before sharing with family/friends

### Phase 2 Users
**Profile:** Family & Friends
- **Technical Level:** Non-technical, smartphone users
- **Domain Expertise:** General nutrition awareness, not specialists
- **Goals:** Personalized meal plans, weight management, muscle gain, better nutrition habits
- **Pain Points:** Generic diet plans don't work, inconsistent results, lack of accountability

### Phase 3 Users (Future)
**Profile:** General Public / Potential Customers
- **Technical Level:** Varied, primarily mobile-first
- **Domain Expertise:** Minimal to moderate
- **Goals:** Sustainable lifestyle changes, specific physique goals, performance optimization
- **Pain Points:** Expensive nutritionists ($100-300/session), generic apps, lack of personalization

**Key User Needs:**
- ✅ Accurate calorie and macro calculations based on individual metrics
- ✅ Weekly meal plans that respect preferences and restrictions
- ✅ Adaptive feedback system that adjusts based on real results
- ✅ Conversation-based interaction (not forms and spreadsheets)
- ✅ Memory of past preferences and conversations
- ✅ Access to scientifically-validated nutritional knowledge

---

## 4. MVP Scope

### ✅ In Scope (Module 4 - Python Migration)

**Core Agent Functionality:**
- ✅ Conversational AI agent using Pydantic AI framework
- ✅ Session management with unique session IDs
- ✅ Long-term memory system (mem0 integration)
- ✅ RAG for nutritional knowledge base (Supabase vector store)
- ✅ RAG for conversation memories (Supabase vector store)
- ✅ System prompt with nutrition coaching personality (French, warm, scientific)

**Nutrition Tools:**
- ✅ `calculate_nutritional_needs` - BMR, TDEE, macro calculations with goal inference
- ✅ `calculate_weekly_adjustments` - Adaptive feedback analysis and recommendations
- ✅ Document query tool (RAG search in nutritional knowledge base)
- ✅ Memory query tool (RAG search in past conversations)
- ✅ Web search tool (Brave API for recent nutritional information)
- ✅ Image analysis tool (GPT-4 Vision for general images via Google Drive)

**Body Composition Analysis:**
- ✅ Image upload support (base64 encoding)
- ✅ Validation guardrails (ensure appropriate body photos)
- ✅ Body fat estimation using GPT-4o Vision with fitness coach framing
- ✅ Error handling for invalid images

**Data Infrastructure:**
- ✅ Supabase database integration (cloud)
- ✅ Tables: `my_profile`, `documents`, `memories`, `document_metadata`, `document_rows`
- ✅ Additional tables: `ingredients_reference`, `recipes`, `meal_plans`, `weekly_tracking`, `n8n_chat_histories`
- ✅ RAG pipeline for Google Drive document sync

**Interface:**
- ✅ Streamlit chat interface for testing
- ✅ Message history persistence (localStorage)
- ✅ Image upload capability
- ✅ Session management

---

## 5. User Stories

### Primary User Stories (MVP)

**US-1: Initial Profile Setup**
*As a new user, I want to have a natural conversation to set up my profile (age, weight, height, goals, allergies), so that I receive personalized nutritional recommendations without filling out forms.*

**Example:**
User: "Je fais 87kg, 1m78, 35 ans, je veux prendre du muscle"
Agent: *Uses `calculate_nutritional_needs` → Returns BMR: 1850, TDEE: 2868, Target: 3168 kcal (191g protein, 397g carbs, 88g fat)*

---

**US-2: Weekly Feedback & Adaptive Adjustments**
*As an active user, I want to submit my weekly check-in (weight changes, hunger, energy, adherence) via conversation, so that the agent adjusts my calorie/macro targets based on real-world results.*

**Example:**
User: "Cette semaine j'ai commencé à 87kg et fini à 86.4kg, j'ai suivi le plan à 85%, niveau d'énergie bon mais j'ai eu un peu faim"
Agent: *Uses `calculate_weekly_adjustments` → Returns +20g protein (hunger management), +150 kcal (energy support), detailed rationale*

---

**US-3: Nutritional Knowledge Queries**
*As a user curious about nutrition science, I want to ask questions like "Combien de protéines pour prendre du muscle?" and get scientifically-backed answers, so that I understand the reasoning behind recommendations.*

**Example:**
User: "C'est quoi le meilleur timing pour les glucides?"
Agent: *Queries RAG documents → Returns synthesis from ISSN position stands on nutrient timing, explains pre/post-workout carb strategies*

---

**US-4: Body Composition Analysis**
*As a user tracking my physique, I want to upload a body photo and receive an estimated body fat percentage with detailed visual feedback, so that I can track progress beyond just weight.*

**Example:**
User: *Uploads shirtless photo*
Agent: *Validates image → Analyzes with GPT-4o Vision → Returns: "Estimation: 18% body fat (range 16-20%), muscle definition visible in shoulders and abs, strengths: upper body development, suggestions: focus on lower body hypertrophy"*

---

**US-5: Preference Memory & Personalization**
*As a returning user, I want the agent to remember my dietary restrictions, favorite foods, and past conversations, so that I don't have to repeat myself and recommendations improve over time.*

**Example:**
User: "Je suis allergique aux arachides et je déteste le poisson"
*[2 weeks later]*
User: "Propose-moi une collation riche en protéines"
Agent: *Queries memories → Recalls allergies → Suggests: yogurt grec, fromage blanc, oeufs durs (avoids peanut butter and tuna)*

---

**US-6: Web Search for Recent Information**
*As a user asking about recent nutrition trends, I want the agent to search the web when its knowledge base is insufficient, so that I get up-to-date information beyond its training cutoff.*

**Example:**
User: "Quelles sont les nouvelles recommandations 2024 sur les oméga-3?"
Agent: *Knowledge base outdated → Uses web_search → Synthesizes recent research + existing knowledge base*

---

**US-7: Profile Retrieval & Context Loading**
*As a user starting a new conversation session, I want the agent to automatically load my profile and recent memories, so that the conversation feels continuous and personalized.*

**Example:**
User: "Salut"
Agent: *Automatically calls `fetch_my_profile` + `memories` RAG → "Salut! Tu es à ta 3ème semaine de prise de masse, dernière pesée 86.4kg. Comment s'est passée ta semaine?"*

---

**US-8: Conversational Calculations**
*As a user with changing metrics, I want to ask "Si je passe à 85kg, ça change mes macros?" and get instant recalculations, so that I can explore different scenarios.*

**Example:**
User: "Si je passe à un niveau d'activité très actif, mes besoins changent de combien?"
Agent: *Recalculates with new activity multiplier → "Ton TDEE passerait de 2868 à 3515 kcal (+647), donc cible à 3815 kcal (+647), avec 210g protéines (+19g)"*

---

## 6. Core Architecture & Patterns

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE LAYER                      │
│                  Streamlit Chat Interface                    │
│           (Session management, message history)              │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                   AI AGENT ORCHESTRATOR                      │
│                     (Pydantic AI)                            │
│  • System prompt (nutrition coach personality)               │
│  • Tool routing and execution                                │
│  • Conversation management                                   │
│  • Response generation                                       │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                      TOOLS LAYER                             │
├──────────────────────────┬──────────────────────────────────┤
│  Nutrition Calculations  │      Knowledge & Memory          │
│  • calculate_nutritional │  • documents (RAG)               │
│    _needs                │  • memories (RAG)                │
│  • calculate_weekly      │  • web_search (Brave)            │
│    _adjustments          │  • image_analysis (GPT-4V)       │
│  • fetch_my_profile      │                                  │
└──────────────────────────┴──────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                    DATA & STORAGE LAYER                      │
├─────────────────────────────────────────────────────────────┤
│  Supabase PostgreSQL + pgvector                             │
│  • my_profile (user biometrics, targets)                    │
│  • documents (RAG vectorstore - nutritional knowledge)       │
│  • memories (RAG vectorstore - conversation history)         │
│  • weekly_tracking (feedback history)                        │
│  • ingredients_reference, recipes, meal_plans                │
│  • document_metadata, document_rows (tabular data)           │
│                                                              │
│  mem0 Long-Term Memory                                       │
│  • Cross-session preference tracking                         │
│  • User behavior patterns                                    │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                   EXTERNAL SERVICES                          │
│  • OpenAI API (GPT-4, GPT-4o, embeddings)                   │
│  • Brave Search API (web search)                            │
│  • Google Drive API (document sync for RAG pipeline)         │
└─────────────────────────────────────────────────────────────┘
```

### Directory Structure (Current)

```
AI-nutrition/
├── src/                            # Main agent package
│   ├── agent.py                    # Pydantic AI agent (loads skill scripts via importlib)
│   ├── tools.py                    # Agent tool wrappers (@agent.tool decorators)
│   ├── prompt.py                   # System prompt template
│   ├── clients.py                  # LLM, DB, memory clients
│   ├── cli.py                      # CLI entry point
│   ├── streamlit_ui.py             # Streamlit interface
│   ├── skill_loader.py             # Skill discovery & progressive disclosure
│   ├── skill_tools.py              # Skill agent tools (load, read, list)
│   ├── nutrition/                  # Domain logic (pure functions)
│   │   ├── calculations.py         # BMR, TDEE, protein, macros
│   │   ├── adjustments.py          # Weight trends, red flags, adjustments
│   │   ├── feedback_extraction.py  # Feedback parsing & completeness
│   │   ├── validators.py           # Input validation
│   │   ├── meal_planning.py        # Meal plan generation
│   │   ├── meal_distribution.py    # Macro distribution across meals
│   │   ├── meal_plan_optimizer.py  # Optimization constraints
│   │   ├── meal_plan_formatter.py  # Output formatting
│   │   ├── openfoodfacts_client.py # Open Food Facts API
│   │   ├── fatsecret_client.py     # FatSecret API (legacy)
│   │   └── error_logger.py         # Error tracking
│   └── RAG_Pipeline/               # Document sync
│       ├── common/ (db_handler, text_processor)
│       ├── Google_Drive/ (drive_watcher)
│       └── Local_Files/ (file_watcher)
│
├── skills/                         # Skill-based progressive disclosure
│   ├── nutrition-calculating/      # BMR/TDEE/macro calculation
│   │   ├── SKILL.md                # Metadata + when to use
│   │   ├── scripts/calculate_nutritional_needs.py
│   │   └── references/formulas.md
│   ├── meal-planning/              # Weekly plans, shopping lists
│   │   ├── SKILL.md
│   │   ├── scripts/ (generate_weekly_meal_plan, shopping_list, fetch_stored)
│   │   └── references/ (presentation, allergens, shopping format)
│   ├── weekly-coaching/            # Adaptive weekly adjustments
│   │   ├── SKILL.md
│   │   ├── scripts/calculate_weekly_adjustments.py
│   │   └── references/red_flag_protocol.md
│   ├── knowledge-searching/        # RAG + web search
│   │   ├── SKILL.md
│   │   └── scripts/ (retrieve_relevant_documents, web_search)
│   ├── body-analyzing/             # GPT-4 Vision analysis
│   │   ├── SKILL.md
│   │   └── scripts/image_analysis.py
│   └── skill-creator/              # Meta: create new skills
│
├── evals/                          # Pydantic-evals structured evaluations
│   ├── test_skill_loading.py       # Skill discovery & loading (5 datasets)
│   └── test_skill_scripts.py       # Script execution (5 datasets, 28 cases)
│
├── tests/                          # Pytest unit/integration tests
├── sql/                            # DB schema migrations
├── prototype/                      # n8n reference & Lovable frontend
│   └── loveable_interface/         # React/TypeScript frontend
│
└── Configuration files
    ├── .env, requirements.txt, pytest.ini, CLAUDE.md, PRD.md
```

### Key Design Patterns

**1. Skill-Based Progressive Disclosure Architecture**
- Each domain (nutrition, meal-planning, coaching, etc.) is a **skill** with its own directory
- Skills contain: `SKILL.md` (metadata/when-to-use), `scripts/` (executable functions), `references/` (domain docs)
- Scripts are standalone `async execute(**kwargs)` functions loaded via `importlib`
- Agent tool wrappers live in `src/agent.py` (thin `_import_skill_script` adapters, one per script)
- `src/tools.py` contains ONLY `fetch_my_profile_tool` and `update_my_profile_tool` — zero skill logic
- `SkillLoader` discovers skills at startup and provides metadata for agent context
- Enables independent testing, eval coverage per script, and modular development

**2. RAG (Retrieval-Augmented Generation)**
- Knowledge base documents stored as embeddings in Supabase pgvector
- User queries converted to embeddings → semantic similarity search
- Retrieved context injected into LLM prompt
- Prevents hallucinations, grounds responses in scientific literature

**3. Adaptive Feedback Loop**
- Weekly check-ins collect real-world data (weight, hunger, energy)
- `calculate_weekly_adjustments` analyzes trends vs. targets
- Automatic recommendations for calorie/macro adjustments
- User approval required before applying changes (safety)

**4. Memory-Augmented Conversations**
- Short-term: n8n PostgreSQL chat history (session-based)
- Long-term: mem0 + Supabase memories vectorstore (cross-session)
- On first message: fetch profile + query memories for context
- New preferences/restrictions automatically stored

**5. Eval-Driven Development**
- All skill scripts validated with pydantic-evals structured evaluations
- Custom evaluators (IsValidJSON, CaloriesInRange, JSONErrorCode, etc.) verify outputs
- 28 eval cases across 5 datasets cover happy paths, edge cases, and error handling
- Mocked external dependencies (Supabase, OpenAI, HTTP) for deterministic testing
- Safety constraints validated in evals (min calories, allergen checks, weight validation)

---

## 7. Tools/Features

### Tool 1: `calculate_nutritional_needs`

**Purpose:** Calculate Basal Metabolic Rate (BMR), Total Daily Energy Expenditure (TDEE), and target macronutrient distribution based on user biometrics and goals.

**Operations:**
- ✅ BMR calculation using Mifflin-St Jeor equation (gender-specific)
- ✅ TDEE calculation with activity level multipliers (sedentary: 1.2, light: 1.375, moderate: 1.55, active: 1.725, very active: 1.9)
- ✅ Automatic goal inference from activities/context (e.g., "musculation + basket" → muscle_gain: 7, performance: 7)
- ✅ Protein targets: 1.6-2.2 g/kg for muscle gain, 2.3-3.1 g/kg for deficit, 1.4-2.0 g/kg maintenance
- ✅ Carb/fat distribution based on goal ratios
- ✅ Warnings for out-of-range parameters (age <18 or >100, weight <40kg, height <100cm)

**Parameters:**
```json
{
  "age": 35,
  "gender": "male",
  "weight_kg": 87,
  "height_cm": 178,
  "activity_level": "moderate",
  "goals": {
    "muscle_gain": 7,
    "performance": 7,
    "weight_loss": 0,
    "maintenance": 3
  },
  "activities": ["musculation", "basket"],
  "context": "Je veux prendre du muscle tout en restant performant au basket"
}
```

**Output:**
```json
{
  "bmr": 1850,
  "tdee": 2868,
  "target_calories": 3168,
  "target_protein_g": 191,
  "target_carbs_g": 397,
  "target_fat_g": 88,
  "protein_per_kg": 2.2,
  "goals_used": {
    "muscle_gain": 7,
    "performance": 7
  },
  "inference_rationale": [
    "Musculation détectée → muscle_gain: 7",
    "Sport collectif (basket) → performance: 7"
  ]
}
```

**Key Features:**
- Automatic goal detection from natural language (eliminates need for sliders/forms)
- Scientifically-validated formulas (ISSN position stands)
- Adjusts protein based on goal priority (higher protein for muscle gain/deficit)
- Transparent rationale returned to user

---

### Tool 2: `calculate_weekly_adjustments`

**Purpose:** Analyze weekly feedback data and recommend nutritional adjustments based on weight trends, subjective metrics (hunger, energy, sleep), and adherence rate.

**Operations:**
- ✅ Weight change analysis vs. goal-specific targets (weight loss: -0.3 to -0.7 kg/week, muscle gain: +0.2 to +0.5 kg/week)
- ✅ Adherence gating (<50% → focus on simplification, not adjustments)
- ✅ Hunger-based protein adjustments (+20g if hunger = high)
- ✅ Energy-based carb adjustments (+30g if energy = low)
- ✅ Craving-based fat adjustments (+10g if cravings = "gras")
- ✅ Sleep quality impact detection (poor sleep → metabolic slowdown warning)
- ✅ Free-text notes parsing for keywords (fatigue, bloating, motivation)
- ✅ Safety floors (minimum 1200 kcal, 50g protein, 50g carbs, 30g fat)

**Parameters:**
```json
{
  "weight_start": 87,
  "weight_end": 86.4,
  "current_calories": 3168,
  "current_protein_g": 191,
  "current_carbs_g": 397,
  "current_fat_g": 88,
  "adherence_rate": 85,
  "hunger_level": "medium",
  "energy_level": "high",
  "sleep_quality": "good",
  "cravings": ["sucré"],
  "user_goal": "muscle_gain",
  "weeks_on_plan": 2,
  "notes": "Bonne semaine, un peu fatigué vendredi"
}
```

**Output:**
```json
{
  "status": "stable",
  "adjustments": {
    "calories": 0,
    "protein_g": 0,
    "carbs_g": 0,
    "fat_g": 0
  },
  "new_targets": {
    "calories": 3168,
    "protein_g": 191,
    "carbs_g": 397,
    "fat_g": 88
  },
  "weight_analysis": {
    "start_kg": 87,
    "end_kg": 86.4,
    "change_kg": -0.6,
    "change_percent": -0.69,
    "trend": "perte"
  },
  "rationale": [
    "✅ Perte optimale (-0.6kg) - Parfait pour une prise sèche !"
  ],
  "alerts": ["✅ Aucune alerte"],
  "warnings": [],
  "tips": [
    "Intègre 1 fruit ou 1 carré de chocolat noir après le repas",
    "Les fringales sucrées peuvent indiquer un manque de glucides ou de sommeil"
  ],
  "recommendation": "💪 Prise de masse propre en cours ! Continue.",
  "next_steps": [],
  "summary": "Semaine 2: -0.60kg | Adhérence: 85% | Ajustement: +0 kcal"
}
```

**Key Features:**
- Goal-aware logic (different targets for weight loss vs. muscle gain)
- Multi-factor analysis (weight + subjective metrics + adherence)
- Actionable tips generated based on user state
- Conservative adjustments to prevent yo-yo effects
- Transparent rationale for every decision

---

### Tool 3: `fetch_my_profile`

**Purpose:** Retrieve user profile from Supabase `my_profile` table.

**Operations:**
- ✅ SQL query: `SELECT * FROM my_profile LIMIT 1;`
- ✅ Returns complete user profile including biometrics, goals, preferences, current targets

**Output:**
```json
{
  "id": "uuid",
  "name": "Moi",
  "age": 35,
  "gender": "male",
  "weight_kg": 87,
  "height_cm": 178,
  "activity_level": "moderate",
  "goals": {
    "muscle_gain": 7,
    "performance": 7,
    "weight_loss": 0,
    "maintenance": 3
  },
  "allergies": ["arachides"],
  "diet_type": "omnivore",
  "disliked_foods": ["poisson"],
  "favorite_foods": ["poulet", "riz", "banane"],
  "max_prep_time": 45,
  "preferred_cuisines": ["méditerranéenne", "asiatique"],
  "target_calories": 3168,
  "target_protein_g": 191,
  "target_carbs_g": 397,
  "target_fat_g": 88
}
```

---

### Tool 4: `documents` (RAG - Knowledge Base)

**Purpose:** Search the nutritional knowledge base using semantic similarity.

**Operations:**
- ✅ Query Supabase vectorstore using `match_documents` function
- ✅ Returns top-k most relevant document chunks with metadata
- ✅ Content includes: ISSN position stands, AND guidelines, macronutrient science, nutrient timing, etc.

**Example Query:** "Combien de protéines pour prendre du muscle?"

**Returns:** Chunks from `nutritional_knowledge_base.md` with protein synthesis data, ISSN recommendations (1.6-2.2 g/kg), plateau effects, leucine thresholds.

---

### Tool 5: `memories` (Long-Term Memory via mem0)

**Purpose:** Maintain context across sessions using mem0 for intelligent memory management.

**Implementation:** Uses **mem0** library instead of a separate vectorstore. mem0 provides:
- ✅ Automatic extraction of important information from conversations
- ✅ Memory consolidation and deduplication
- ✅ Cross-session context persistence
- ✅ Injected into system prompt via `add_memories()` function

**How it works:**
```python
# In agent.py - memories are loaded from mem0 and injected into system prompt
@agent.system_prompt
def add_memories(ctx: RunContext[AgentDeps]) -> str:
    if ctx.deps.memories:
        return f"\n\n## User Memories (Long-Term Context)\n{ctx.deps.memories}"
```

**Example Context Provided:** "Allergic to peanuts, dislikes fish, prefers Mediterranean and Asian cuisines, maximum prep time 45 minutes, goal is muscle gain."

---

### Tool 6: `web_search`

**Purpose:** Search the web using Brave Search API for recent information not in the knowledge base.

**Operations:**
- ✅ Brave Search API integration
- ✅ Result summarization and entity extraction
- ✅ Synthesis with existing knowledge base

**Use Cases:**
- Recent nutrition research (2024 studies)
- New ingredient information
- Trending dietary approaches
- Updated position stands

---

### Tool 7: `image_analysis`

**Purpose:** Analyze images using GPT-4 Vision (two modes: Google Drive URLs for agent, direct upload for body fat analysis).

**Operations:**
- ✅ Google Drive image download (for agent-called analysis)
- ✅ GPT-4o-mini Vision analysis
- ✅ Structured output based on query

**Note:** Body fat analysis bypasses the agent and uses a dedicated n8n flow (see Body Fat Analysis Flow below).

---

### Special Feature: Body Fat Analysis Flow

**Purpose:** Estimate body composition from user-uploaded photos with validation guardrails.

**Architecture:** Dedicated flow that bypasses the agent (not a tool, but a separate webhook path).

**Flow:**
```
[Webhook receives image]
  → [Code: Extract & convert base64 to binary]
  → [Switch: hasImage?]
  → [GPT-4o-mini: Validate image is appropriate body photo]
  → [Code: Parse validation JSON]
  → [Switch: isValid?]
      → YES: [GPT-4o: Analyze body fat with fitness coach prompt]
      → NO: [Error message with guidance]
  → [Respond to webhook]
```

**Validation Prompt:**
```
Analyse cette image et détermine si elle est appropriée pour une estimation de body fat.

VALIDE: personne humaine, torse visible, photo permettant évaluation composition corporelle
INVALIDE: animal, objet, vêtements amples, seulement visage, floue, contenu inapproprié

RÉPONDS UNIQUEMENT EN JSON:
{
  "is_valid": true/false,
  "reason": "explication courte"
}
```

**Analysis Prompt (Fitness Coach Framing):**
```
Tu es un coach fitness expérimenté qui aide les gens à comprendre leur progression physique.

Genre: {{ gender }}

Évalue:
1. Niveau de définition musculaire (très défini / défini / modéré / peu visible)
2. Estimation composition corporelle (fourchette basée sur repères visuels standards)
   - Homme: athlétique (10-14%), fitness (15-19%), moyen (20-24%), à travailler (25%+)
   - Femme: athlétique (18-22%), fitness (23-27%), moyenne (28-32%), à travailler (33%+)
3. Points forts observés (groupes musculaires développés)
4. Axes d'amélioration
5. Estimation globale (ex: "environ 18%", fourchette "entre 16% et 20%")

IMPORTANT:
- Évaluation visuelle approximative à but informatif uniquement
- Seules méthodes professionnelles (DEXA, impédancemétrie) donnent mesures précises
- Cette estimation sert à orienter l'entraînement, pas poser diagnostic

Réponds de manière encourageante et constructive, comme un coach bienveillant.
```

**Key Features:**
- Guardrail prevents inappropriate image submissions
- Fitness coach framing bypasses OpenAI content policy restrictions
- Encourages users to understand limitations (visual estimate only)
- Provides actionable feedback beyond just a number

---

## 8. Technology Stack

### Backend (Python)

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Agent Framework** | Pydantic AI | Latest | Agent orchestration, tool routing |
| **LLM Provider** | OpenAI API | GPT-4, GPT-4o, GPT-4o-mini | Conversational AI, image analysis |
| **Embeddings** | OpenAI | text-embedding-3-small | RAG vectorization |
| **Database** | Supabase (PostgreSQL + pgvector) | Latest | User data, RAG vectorstore |
| **Long-Term Memory** | mem0 | Latest | Cross-session preference tracking |
| **Web Search** | Brave Search API | Latest | Recent nutritional information |
| **File Monitoring** | Watchdog (Python) | Latest | RAG pipeline file watching |
| **Google Drive API** | Google Drive API v3 | Latest | Document sync for RAG |

**Core Dependencies (requirements.txt):**
```
pydantic-ai
openai
supabase
mem0ai
requests  # Brave API
google-auth
google-auth-oauthlib
google-api-python-client
watchdog  # File monitoring
streamlit  # UI
python-dotenv
```

### Frontend (Future Integration - Module 5)

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Framework** | React + TypeScript | Latest | UI components |
| **Build Tool** | Vite | Latest | Fast development |
| **UI Library** | shadcn/ui | Latest | Component library |
| **Styling** | Tailwind CSS | Latest | Utility-first CSS |
| **State Management** | React Query | Latest | Server state |
| **Routing** | React Router | Latest | Client-side routing |

**Current Status:** Lovable interface prototype connected to FastAPI backend via NDJSON streaming (`useChat.ts` → `POST /api/agent`). Tested end-to-end: tokens stream progressively, session management works. `user_id` hardcoded in `.env` until Supabase Auth is wired.

### Database Schema (Supabase)

**Tables:**
```sql
-- User profile
my_profile (
  id UUID PRIMARY KEY,
  name TEXT,
  age INT,
  gender TEXT,
  weight_kg NUMERIC,
  height_cm INT,
  activity_level TEXT,
  goals JSONB,
  allergies TEXT[],
  diet_type TEXT,
  disliked_foods TEXT[],
  favorite_foods TEXT[],
  max_prep_time INT,
  preferred_cuisines TEXT[],
  bmr NUMERIC,
  tdee NUMERIC,
  target_calories NUMERIC,
  target_protein_g NUMERIC,
  target_carbs_g NUMERIC,
  target_fat_g NUMERIC
)

-- RAG vectorstore (knowledge base)
documents (
  id BIGSERIAL PRIMARY KEY,
  content TEXT,
  metadata JSONB,
  embedding VECTOR(1536)
)

-- RAG vectorstore (conversation memories)
memories (
  id BIGSERIAL PRIMARY KEY,
  content TEXT,
  metadata JSONB,
  embedding VECTOR(1536)
)

-- Document metadata
document_metadata (
  id TEXT PRIMARY KEY,
  title TEXT,
  url TEXT,
  created_at TIMESTAMP,
  schema TEXT
)

-- Tabular document data
document_rows (
  id SERIAL PRIMARY KEY,
  dataset_id TEXT REFERENCES document_metadata(id),
  row_data JSONB
)

-- Ingredients reference
ingredients_reference (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  category TEXT,
  calories NUMERIC,
  protein_g NUMERIC,
  carbs_g NUMERIC,
  fat_g NUMERIC,
  fiber_g NUMERIC,
  allergens TEXT[],
  seasons TEXT[],
  diet_compatible TEXT[],
  price_tier TEXT
)

-- Recipes
recipes (
  id UUID PRIMARY KEY,
  created_at TIMESTAMP,
  name TEXT NOT NULL,
  category TEXT,
  nutrition JSONB,
  servings INT,
  ingredients JSONB,
  instructions JSONB,
  prep_time INT,
  cook_time INT,
  difficulty TEXT,
  tags TEXT[],
  rating INT,
  times_made INT,
  last_made DATE,
  notes TEXT
)

-- Meal plans
meal_plans (
  id UUID PRIMARY KEY,
  week_start DATE,
  created_at TIMESTAMP,
  plan_data JSONB,
  target_calories_daily NUMERIC,
  target_protein_g NUMERIC,
  target_carbs_g NUMERIC,
  target_fat_g NUMERIC,
  notes TEXT
)

-- Weekly tracking
weekly_tracking (
  id UUID PRIMARY KEY,
  week_start DATE UNIQUE,
  week_end DATE,
  created_at TIMESTAMP,
  weight_start NUMERIC,
  weight_end NUMERIC,
  weight_change NUMERIC,
  energy_level TEXT,
  hunger_level TEXT,
  sleep_quality TEXT,
  meals_followed INT,
  meals_skipped INT,
  adherence_rate NUMERIC,
  observations TEXT,
  cravings TEXT[],
  liked_recipes TEXT[],
  disliked_recipes TEXT[]
)

-- Chat history (n8n compatibility)
n8n_chat_histories (
  id SERIAL PRIMARY KEY,
  session_id VARCHAR NOT NULL,
  message JSONB NOT NULL
)
```

### External APIs

| Service | Purpose | Authentication | Rate Limits |
|---------|---------|----------------|-------------|
| OpenAI API | LLM, embeddings, vision | API Key | Varies by tier |
| Brave Search API | Web search | API Key | Free tier available |
| Google Drive API | Document sync | OAuth 2.0 | 10,000 requests/day |
| Supabase | Database + vectorstore | Service key | Free tier: 500MB DB, 2GB bandwidth |

---

## 9. Security & Configuration

### Environment Configuration

**Required Variables (.env):**
```bash
# LLM Configuration
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_CHOICE=gpt-4o-mini
VISION_LLM_CHOICE=gpt-4o

# Embedding Configuration
EMBEDDING_PROVIDER=openai
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=sk-...
EMBEDDING_MODEL_CHOICE=text-embedding-3-small

# Database Configuration
DATABASE_URL=postgresql://postgres:password@localhost:5432/mydb
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# Web Search
BRAVE_API_KEY=BSA...
SEARXNG_BASE_URL=  # Leave empty if using Brave

# Optional
DEBUG=false
LOG_LEVEL=INFO
```

### Authentication & Authorization

**MVP Scope:**
- ✅ Session-based identification (session IDs generated client-side)
- ✅ No multi-user authentication (single user: yourself)
- ✅ Supabase RLS (Row-Level Security) disabled for simplicity

**Post-MVP (Module 5):**
- ❌ User registration and login
- ❌ JWT-based authentication
- ❌ Supabase Auth integration
- ❌ Role-based access control (admin, user)
- ❌ Session management with refresh tokens

### Security Scope

**✅ In Scope (MVP):**
- API key protection (environment variables, .gitignore)
- Input validation on tool parameters (age, weight, height ranges)
- SQL injection prevention (parameterized queries via Supabase client)
- Allergen safety (zero tolerance for allergen violations in recipes)
- Minimum calorie floors (1200 women, 1500 men)
- Image content validation (body fat analysis guardrail)

**❌ Out of Scope (MVP):**
- Rate limiting (to be added in production)
- IP whitelisting
- DDoS protection
- End-to-end encryption for data at rest
- HIPAA/GDPR compliance (not medical device, informational only)
- Penetration testing
- Security audit

### Safety Constraints (Hardcoded)

```python
# Safety floors in calculate_weekly_adjustments
MIN_CALORIES = 1200  # Women
MIN_CALORIES_MEN = 1500
MIN_PROTEIN_G = 50
MIN_CARBS_G = 50
MIN_FAT_G = 30

# Age/weight/height validation in calculate_nutritional_needs
MIN_AGE = 18
MAX_AGE = 100
MIN_WEIGHT_KG = 40
MIN_HEIGHT_CM = 100

# Allergen check before recipe suggestions
ALLERGEN_ZERO_TOLERANCE = True
```

---

## 10. API Specification (Module 5)

### REST API (Python FastAPI Backend)

**Base URL:** `http://localhost:8001` (dev) — production URL TBD
**Entry point:** `src/api.py` — run with `python -m src api` or `uvicorn src.api:app --port 8001`

**Authentication:** Not yet wired — `user_id` comes from request body (trusted). `verify_token()` stub exists for future Supabase Auth JWT integration.

#### `GET /health`
Service health check.

**Response:**
```json
{"status": "healthy", "service": "ai-nutrition-api"}
```

#### `POST /api/agent`
Main streaming agent endpoint. Returns NDJSON chunks.

**Request:**
```json
{
  "query": "Propose-moi un plan pour cette semaine",
  "user_id": "5745fc58-9c75-48b1-bc79-12855a8c6021",
  "request_id": "unique-uuid-per-request",
  "session_id": "",
  "files": null
}
```
- `session_id`: empty string for new conversation (auto-generated), or existing session ID to continue
- `files`: optional list of `{file_name, content, mime_type}` for attachments

**Response (NDJSON stream):**
```
{"text": "Bonjour"}
{"text": "Bonjour! Comment"}
{"text": "Bonjour! Comment puis-je vous aider?"}
{"text": "Bonjour! Comment puis-je vous aider?", "session_id": "user~abc123", "conversation_title": "Greeting and Introduction", "complete": true}
```
- Each line is a JSON object with accumulated `text`
- Final chunk includes `session_id`, optional `conversation_title`, and `complete: true`
- On error: `{"text": "error message", "error": "...", "complete": true}`

#### `GET /api/conversations?user_id=<uuid>`
List conversations for a user (most recent first, limit 50).

**Response:**
```json
[
  {"session_id": "user~abc123", "title": "Nutrition Calculation", "created_at": "..."}
]
```

#### `POST /upload/body-image`
Upload body composition photo.

**Headers:**
```
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data
```

**Request:**
```
image: <binary file>
gender: male
```

**Response:**
```json
{
  "analysis": {
    "estimated_body_fat_percent": 18,
    "range_min": 16,
    "range_max": 20,
    "muscle_definition": "défini",
    "strengths": ["Développement haut du corps", "Définition abdominaux"],
    "improvements": ["Focus hypertrophie bas du corps"],
    "detailed_feedback": "..."
  },
  "imageId": "img_xyz789",
  "timestamp": "2024-12-14T18:35:00Z"
}
```

#### `GET /profile`
Retrieve user profile.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
  "id": "user_123",
  "name": "Moi",
  "age": 35,
  "gender": "male",
  "weight_kg": 87,
  "height_cm": 178,
  "activity_level": "moderate",
  "goals": {
    "muscle_gain": 7,
    "performance": 7,
    "weight_loss": 0,
    "maintenance": 3
  },
  "allergies": ["arachides"],
  "diet_type": "omnivore",
  "disliked_foods": ["poisson"],
  "favorite_foods": ["poulet", "riz", "banane"],
  "current_targets": {
    "calories": 3168,
    "protein_g": 191,
    "carbs_g": 397,
    "fat_g": 88
  }
}
```

#### `POST /weekly-checkin`
Submit weekly feedback.

**Headers:**
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request:**
```json
{
  "week_start": "2024-12-09",
  "week_end": "2024-12-15",
  "weight_start": 87.0,
  "weight_end": 86.4,
  "adherence_rate": 85,
  "hunger_level": "medium",
  "energy_level": "high",
  "sleep_quality": "good",
  "cravings": ["sucré"],
  "notes": "Bonne semaine, un peu fatigué vendredi"
}
```

**Response:**
```json
{
  "analysis": {
    "status": "stable",
    "weight_change_kg": -0.6,
    "trend": "perte optimale",
    "adjustments": {
      "calories": 0,
      "protein_g": 0,
      "carbs_g": 0,
      "fat_g": 0
    },
    "new_targets": {
      "calories": 3168,
      "protein_g": 191,
      "carbs_g": 397,
      "fat_g": 88
    },
    "rationale": [
      "✅ Perte optimale (-0.6kg) - Parfait pour une prise sèche !"
    ],
    "tips": [
      "Intègre 1 fruit ou 1 carré de chocolat noir après le repas"
    ],
    "recommendation": "💪 Prise de masse propre en cours ! Continue."
  }
}
```

---

## 11. Success Criteria

### MVP Success Definition
The Module 4 migration is successful when:
1. All tools from the n8n prototype are functional in Python
2. The agent can hold multi-turn conversations with memory
3. RAG retrieval works for both documents and memories
4. Nutritional calculations match n8n output (validated against test cases)
5. Streamlit UI allows natural conversation and image upload
6. No regressions from n8n functionality

### Functional Requirements

**✅ Core Agent:**
- ✅ Conversational flow with French personality (warm, scientific, uses "tu")
- ✅ System prompt correctly implements tool usage rules (RAG before calculations, allergen checks)
- ✅ Multi-turn conversation with context retention
- ✅ Session management (unique session IDs)

**✅ Nutrition Tools:**
- ✅ `calculate_nutritional_needs` returns accurate BMR/TDEE/macros (±5% tolerance vs. manual calculation)
- ✅ `calculate_weekly_adjustments` provides logical recommendations (tested against 10+ scenarios)
- ✅ `fetch_my_profile` retrieves complete profile from Supabase
- ✅ Safety constraints enforced (minimum calories, allergen checks)

**✅ RAG System:**
- ✅ Document queries return relevant chunks from nutritional knowledge base
- ✅ Memory queries return past conversation context
- ✅ RAG pipeline syncs Google Drive documents automatically (checks every 60 seconds)
- ✅ New/updated/deleted files trigger re-indexing

**✅ Memory System:**
- ✅ Long-term memory (mem0) stores user preferences across sessions
- ✅ On first message: automatic profile + memory loading
- ✅ Important information extracted and stored (allergies, preferences, goals)

**✅ Body Fat Analysis:**
- ✅ Image upload via base64 encoding
- ✅ Validation guardrail rejects inappropriate images (>95% accuracy on test set)
- ✅ GPT-4o Vision analysis provides encouraging, actionable feedback
- ✅ Error messages guide users on appropriate photo types

**✅ Web Search:**
- ✅ Brave API integration functional
- ✅ Results synthesized with knowledge base (not just raw search results)

**✅ Interface:**
- ✅ Streamlit chat interface with message history
- ✅ Image upload button
- ✅ Session persistence across refreshes (localStorage)
- ✅ Typing indicator during agent processing

### Quality Indicators

**Performance:**
- Response time <10 seconds for text queries (excluding web search)
- Response time <20 seconds for image analysis
- RAG retrieval returns results in <2 seconds

**Accuracy:**
- Nutritional calculations match validated formulas (100% accuracy)
- RAG retrieval relevance >80% (subjective evaluation on 20 test queries)
- Zero allergen violations in recipe suggestions

**User Experience:**
- Agent provides scientific rationale for recommendations (100% of nutrition questions)
- Conversations feel natural and personalized (subjective, user feedback)
- Error messages are clear and actionable

---

## 12. Implementation Phases

### Phase 1: Foundation Setup (Week 1)
**Goal:** Establish Python environment, database connections, and basic agent structure.

**Deliverables:**
- ✅ Python virtual environment created
- ✅ Dependencies installed (requirements.txt)
- ✅ .env configuration with API keys
- ✅ Supabase connection tested
- ✅ Basic Pydantic AI agent running (no tools)
- ✅ Streamlit UI scaffold

**Validation:**
- Agent responds to "Hello" with system prompt personality
- Database connection successful (manual query test)
- Streamlit loads without errors

---

### Phase 2: Core Nutrition Tools (Week 2)
**Goal:** Migrate nutrition calculation tools from n8n JavaScript to Python.

**Deliverables:**
- ✅ `calculate_nutritional_needs` tool implemented
- ✅ `calculate_weekly_adjustments` tool implemented
- ✅ `fetch_my_profile` tool implemented
- ✅ Unit tests for each tool (10+ test cases)
- ✅ Agent successfully calls tools based on user queries

**Validation:**
- Test case: "Je fais 87kg, 178cm, 35 ans, objectif prise de masse" → Returns BMR 1850, TDEE 2868, target 3168 kcal
- Test case: Weekly check-in with -0.6kg, 85% adherence → Returns "perte optimale, continue ainsi"
- All tools return same results as n8n prototype (validated against saved test data)

---

### Phase 3: RAG System Integration (Week 3)
**Goal:** Connect to existing Supabase vectorstore and implement RAG pipeline.

**Deliverables:**
- ✅ `documents` RAG tool (query nutritional knowledge base)
- ✅ `memories` RAG tool (query past conversations)
- ✅ Google Drive RAG pipeline running (automatic sync)
- ✅ Document chunking and embedding logic
- ✅ Test with 10+ nutrition questions

**Validation:**
- Query "Combien de protéines pour prendre du muscle?" → Returns chunks from ISSN position stands
- Query "What are this user's allergies?" → Returns "arachides" from memories
- Upload new document to Google Drive → Appears in vectorstore within 60 seconds

---

### Phase 4: Memory & Contextual Intelligence (Week 3-4)
**Goal:** Implement long-term memory (mem0) and conversation context management.

**Deliverables:**
- ✅ mem0 integration with PostgreSQL backend
- ✅ Automatic memory storage on important information
- ✅ First-message context loading (profile + memories)
- ✅ Session management with unique IDs
- ✅ Test multi-session conversations

**Validation:**
- Session 1: User says "Je suis allergique aux arachides"
- Session 2 (new session ID, next day): User asks "Propose une collation protéinée" → Agent avoids peanut butter
- Profile auto-loads on first message (verified in logs)

---

### Phase 5: Additional Capabilities (Week 4)
**Goal:** Add web search, image analysis, and body fat analysis flow.

**Deliverables:**
- ✅ `web_search` tool (Brave API)
- ✅ `image_analysis` tool (GPT-4 Vision for Google Drive images)
- ✅ Body fat analysis flow (validation + estimation)
- ✅ Image upload in Streamlit UI
- ✅ Error handling for failed API calls

**Validation:**
- Web search query "Nouvelles recommandations oméga-3 2024" → Returns recent search results + synthesis
- Image upload (appropriate body photo) → Returns body fat estimate with encouragement
- Image upload (cat photo) → Returns validation error with guidance

---

### Phase 6: Testing & Refinement (Week 5)
**Goal:** End-to-end testing, bug fixes, and system prompt optimization.

**Deliverables:**
- ✅ 20+ end-to-end conversation tests
- ✅ System prompt refinements based on response quality
- ✅ Bug fixes (error handling, edge cases)
- ✅ Documentation (README, usage guide)
- ✅ Code cleanup and comments

**Validation:**
- All user stories validated with real conversations
- No critical bugs in 20+ test sessions
- Agent personality consistent with n8n prototype
- Ready for personal use (Phase 1 user: yourself)

---

## 13. Future Considerations

### Post-MVP Enhancements (Module 5+)

**Frontend Integration:**
- ~~Connect Python backend to Lovable React interface~~ **DONE** (NDJSON streaming)
- Real-time chat with WebSockets (Socket.io)
- User authentication (Supabase Auth)
- Profile management UI (edit goals, allergies, preferences)
- Weekly check-in form (structured input)
- Progress visualization (weight charts, adherence trends)
- Load conversation history from DB (currently localStorage only)

**Meal Planning & Recipes:**
- 7-day meal plan generation tool (Python)
- Recipe creation with nutritional optimization
- Shopping list generation from meal plans
- Recipe rating and feedback system
- Meal timing optimization (pre/post workout)
- **Batch cooking vs varied meals** — Agent should ask user if they want identical meals across days (batch cooking for convenience) or different recipes each day. Currently the planner selects the same recipes for every day by default, which is not ideal for users who want variety.

**Advanced Analytics:**
- Body composition tracking over time (photo comparison)
- Metabolic tendency detection (after 4+ weeks)
- Progress reports (weekly, monthly summaries)
- Goal achievement predictions
- A/B testing different nutritional strategies

**Automation:**
- Automatic profile updates (weight, body fat, targets)
- Weekly check-in reminders (email, push notifications)
- Habit tracking integration (meal logging, workout logging)
- Slack/WhatsApp bot for check-ins

**Data Enhancements:**
- Micronutrient tracking (vitamins, minerals)
- Hydration tracking
- Supplement recommendations
- Integration with food databases (USDA, Open Food Facts)
- Barcode scanning for meal logging

### Integration Opportunities

**Fitness Trackers:**
- Garmin, Fitbit, Apple Health integration
- Automatic activity level adjustments
- Workout-based meal timing

**Food Delivery:**
- Integration with meal delivery services
- Pre-configured meal plans from restaurants
- Macro-optimized meal suggestions

**Health Platforms:**
- Export data to MyFitnessPal, Cronometer
- Import data from CGMs (continuous glucose monitors)
- Integration with health coaching platforms

**E-commerce:**
- Affiliate links for recommended supplements
- Grocery delivery integration (automatic shopping list ordering)

---

## 14. Risks & Mitigations

### Risk 1: API Cost Overruns
**Risk:** OpenAI API costs escalate during development/testing (especially GPT-4 Vision for body fat analysis).

**Likelihood:** Medium
**Impact:** Medium

**Mitigation:**
- Use GPT-4o-mini for validation guardrail (cheaper than GPT-4o)
- Implement request caching for repeated queries
- Monitor API usage with alerts (set budget limits in OpenAI dashboard)
- Use gpt-4o-mini for general conversations, GPT-4o only for critical tasks
- Consider local models (Ollama) for non-critical features in future

---

### Risk 2: RAG Retrieval Quality
**Risk:** RAG system returns irrelevant chunks or misses important information, leading to poor recommendations.

**Likelihood:** Medium
**Impact:** High

**Mitigation:**
- Curate high-quality knowledge base (peer-reviewed sources only)
- Implement hybrid search (semantic + keyword)
- Add re-ranking step (retrieve top 20, re-rank to top 5)
- User feedback mechanism ("Was this answer helpful?")
- Manual review of common queries to tune chunk size and retrieval parameters
- A/B test different embedding models (OpenAI vs. Cohere)

---

### Risk 3: Body Fat Analysis Accuracy
**Risk:** Visual body fat estimates are unreliable, leading to user distrust or harmful behavior (e.g., extreme dieting based on overestimated body fat).

**Likelihood:** High (inherent limitation of visual estimation)
**Impact:** Medium

**Mitigation:**
- Clear disclaimers in every response ("This is a visual estimate, not a clinical measurement")
- Provide wide ranges (e.g., 16-20%) instead of precise numbers
- Emphasize that DEXA, hydrostatic weighing, or bioimpedance are gold standards
- Frame as "progress tracking tool" not "diagnostic tool"
- Recommend professional assessment if user has specific health concerns
- Never store body fat estimates as ground truth (store as "user-reported estimate")

---

### Risk 4: Allergen Violation in Recipes
**Risk:** Agent suggests recipe containing user's allergen, leading to allergic reaction.

**Likelihood:** Low (with proper implementation)
**Impact:** Critical

**Mitigation:**
- **Zero-tolerance policy:** Hardcoded allergen checks before ANY recipe suggestion
- Cross-reference all ingredients against user profile allergies
- Double-check with LLM prompt: "Does this recipe contain any of these allergens: [list]?"
- Flag uncertain cases (e.g., "may contain traces") and ask user
- User confirmation required before finalizing meal plans
- Incident logging for any allergen near-misses (manual review)

---

### Risk 5: Scope Creep During Migration
**Risk:** Attempt to add new features during Module 4 migration, delaying completion.

**Likelihood:** High (natural temptation to improve while building)
**Impact:** Medium

**Mitigation:**
- **Strict MVP scope:** Only migrate existing n8n features, no new features
- Feature wishlist document for post-MVP ideas (PRD Section 13)
- Weekly progress reviews to stay on track
- Accept "good enough" for MVP (can refine later)
- Time-box each phase (if running over, defer non-critical items)

---

## 15. Appendix

### Related Documents

**Course Materials:**
- `ai-agent-mastery/3_n8n_Agents/README.md` - n8n prototype reference
- `ai-agent-mastery/4_Pydantic_AI_Agent/README.md` - Pydantic AI setup guide
- `ai-agent-mastery/4_Pydantic_AI_Agent/PLANNING.md` - Implementation planning

**Project Documentation:**
- `prototype/fiche_de_synthese_V2.1.md` - Comprehensive project synthesis (French)
- `nutrition references/nutritional_knowledge_base.md` - Scientific knowledge base
- `nutrition references/AI nutrion agent best practices` - Nutritional agent design principles

**Prototypes:**
- `prototype/AI Agent nutrition prototype weeklyfeedback(1).json` - n8n workflow (reference implementation)
- `prototype/loveable_interface/` - React/TypeScript frontend (future integration)

### Key Dependencies

| Dependency | Link | Version | Critical? |
|------------|------|---------|-----------|
| Pydantic AI | [GitHub](https://github.com/pydantic/pydantic-ai) | Latest | ✅ Yes |
| OpenAI Python SDK | [GitHub](https://github.com/openai/openai-python) | >=1.0.0 | ✅ Yes |
| Supabase Python | [Docs](https://supabase.com/docs/reference/python) | Latest | ✅ Yes |
| mem0 | [GitHub](https://github.com/mem0ai/mem0) | Latest | ✅ Yes |
| Streamlit | [Docs](https://docs.streamlit.io/) | >=1.28.0 | ✅ Yes |
| Google Drive API | [Docs](https://developers.google.com/drive/api/v3/about-sdk) | v3 | ⚠️ Optional (RAG) |

### Repository Structure

```
AI-nutrition/
├── PRD.md                          # This document
├── CLAUDE.md                       # Development guide (instructions for AI)
├── README.md                       # Project overview
├── requirements.txt                # Python dependencies
├── pytest.ini                      # Test configuration
│
├── src/                            # Main agent package
│   ├── agent.py, tools.py          # Core agent + tool wrappers
│   ├── skill_loader.py             # Skill discovery system
│   └── nutrition/                  # Domain logic (calculations, adjustments)
│
├── skills/                         # 6 skill domains with scripts + references
│   ├── nutrition-calculating/
│   ├── meal-planning/
│   ├── weekly-coaching/
│   ├── knowledge-searching/
│   ├── body-analyzing/
│   └── skill-creator/
│
├── evals/                          # Pydantic-evals structured evaluations
├── tests/                          # Pytest unit/integration tests
├── sql/                            # Database schema
│
├── prototype/                      # n8n reference + Lovable frontend
│   └── loveable_interface/
│
└── ai-agent-mastery/               # Course materials (reference)
```

### Contact & Support

**Primary User:** Yourself (product creator)
**Development Environment:** WSL2 Ubuntu on Windows
**IDE:** Claude Code CLI
**Support:** AI Agent Mastery course community

---

---

## Next Steps (February 2026)

1. ~~**Weekplan total refactoring**~~ **DONE** — Recipe DB + day-by-day generation + LLM fallback
2. ~~**Context optimization**~~ **DONE** — Progressive disclosure lean (~1400 tokens prompt, ~200 tokens metadata)
3. ~~**OpenFoodFacts integration**~~ **DONE** — 275K products imported, 543 cached ingredient mappings
4. ~~**Frontend integration**~~ **DONE** — React prototype connected to FastAPI backend via NDJSON streaming
5. **Batch cooking / recipe variety** — Agent should ask user preference before generating meal plans (same recipes = batch cooking convenience vs different recipes = variety). Currently repeats the same recipes across days.
6. **Profile target caching** — Auto-calculate BMR/TDEE/targets on first profile fetch, cache in `user_profiles` row
7. **User authentication** — Wire `verify_token()` with Supabase Auth JWT, replace hardcoded `VITE_USER_ID`
8. **Full multi-user DB migration** — Add `user_id` FK + RLS to `meal_plans`, `weekly_feedback`, `user_learning_profile`
9. **Load conversation history from DB** — Add `GET /api/conversations/{session_id}/messages` endpoint, replace localStorage

---

**Document Version:** 2.1
**Last Updated:** February 24, 2026
**Next Review:** After batch cooking feature + auth implementation
**Status:** Active - Frontend Integration Complete, Batch Cooking & Auth Next
