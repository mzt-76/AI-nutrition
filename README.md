# AI Nutrition Assistant - MVP Implementation

A conversational AI nutrition coach that creates personalized meal plans and adapts recommendations based on real-world results.

## Stack

- **Agent Framework:** Pydantic AI 0.0.53
- **LLM:** OpenAI (GPT-4o-mini, GPT-4o)
- **Database:** Supabase (PostgreSQL + pgvector)
- **Memory:** mem0
- **Interface:** Streamlit (MVP), React (Future)

## Quick Start

### 1. Setup Virtual Environment

```bash
# Navigate to project directory
cd 4_Pydantic_AI_Agent

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Edit `.env` with your credentials:

```bash
# LLM Configuration
LLM_CHOICE=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...

# Embedding Configuration
EMBEDDING_API_KEY=sk-...
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL_CHOICE=text-embedding-3-small

# Database
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# Web Search (optional)
BRAVE_API_KEY=BSA...
```

### 3. Run the Application

```bash
# Start Streamlit UI
streamlit run streamlit_ui.py

# Or test agent directly
python agent.py
```

## Project Structure

```
4_Pydantic_AI_Agent/
├── agent.py                 # Main agent setup
├── tools.py                 # Tool implementations
├── clients.py               # Client initialization
├── prompt.py                # System prompt
├── streamlit_ui.py          # Streamlit interface
├── requirements.txt         # Dependencies
├── .env                     # Environment variables
├── nutrition/               # Domain logic
│   ├── calculations.py      # BMR, TDEE, macros
│   ├── adjustments.py       # Weekly feedback (TODO)
│   └── validators.py        # Safety constraints (TODO)
├── RAG_Pipeline/            # Document processing
│   ├── common/
│   ├── Google_Drive/
│   └── Local_Files/
├── sql/                     # Database schema
└── tests/                   # Test suite
```

## Available Tools

### 1. calculate_nutritional_needs
Calculate BMR, TDEE, and macros with automatic goal inference.

**Example:**
```
User: "Calcule mes besoins: 35 ans, homme, 87kg, 178cm, activité modérée"
```

### 2. fetch_my_profile
Load user profile from Supabase.

**Example:**
```
User: "Charge mon profil"
```

### 3. retrieve_relevant_documents
Search nutritional knowledge base (RAG).

**Example:**
```
User: "Combien de protéines pour prendre du muscle?"
```

### 4. web_search
Search the web for recent information (Brave API).

**Example:**
```
User: "Nouvelles recommandations oméga-3 2024?"
```

### 5. image_analysis
Analyze body composition from images (GPT-4 Vision).

**Example:**
```
User: [uploads photo] "Estime mon body fat"
```

## Development Workflow

### Run Tests
```bash
pytest
pytest --cov=nutrition  # With coverage
```

### Lint & Format
```bash
ruff format .
ruff check .
mypy .
```

### RAG Pipeline (Separate Terminal)
```bash
cd RAG_Pipeline/Google_Drive
python main.py
```

## Safety Constraints

**Hardcoded (Never Bypass):**
- Minimum calories: 1200 (women), 1500 (men)
- Allergen zero tolerance
- Minimum protein: 50g/day
- Minimum carbs: 50g/day
- Minimum fat: 30g/day

## Current Status

✅ **Completed:**
- Core calculation engine (BMR, TDEE, adaptive protein ranges)
- All 5 tools implemented and functional
- RAG system working (688 documents, cross-language support)
- Profile management with incomplete profile detection
- Streamlit UI operational
- Comprehensive system prompt with mandatory RAG

⏳ **In Progress:**
- Weekly feedback tool (deferred for dedicated session)
- Safety validators
- Test suite creation

📋 **Next Steps:**
- Test web_search and image_analysis tools
- Implement safety validators in `nutrition/validators.py`
- Create comprehensive test suite
- Complete weekly feedback tool
- Document database schema

📄 **See [PROJECT_STATUS.md](./PROJECT_STATUS.md) for detailed progress tracking**

## Documentation

- **PRD:** `/PRD.md` - Product Requirements
- **CLAUDE.md:** `/CLAUDE.md` - Development Guidelines
- **Knowledge Base:** `/nutrition references/nutritional_knowledge_base.md`

## Support

For issues or questions, refer to the AI Agent Mastery course materials in `/ai-agent-mastery/4_Pydantic_AI_Agent/`
