# Product Requirements Document: Paddy

## Executive Summary

**Paddy** is an AI agent that enables Obsidian users to interact with their vaults using natural language through a self-hosted, Dockerized FastAPI backend. Paddy uses Pydantic AI for tool orchestration and integrates with Obsidian via the Copilot plugin, exposing an OpenAI-compatible API endpoint.

**MVP Goal:** Enable users to query, read, and manage their Obsidian vaults through conversational natural language, powered by their choice of LLM provider.

---

## Mission

Build a production-ready AI agent that makes Obsidian vault management intuitive and efficient through natural language interaction, while maintaining simplicity, transparency, and user control.

### Core Principles

1. **Self-hosted & Simple** - Easy to set up and run locally
2. **Provider-agnostic** - Works with any LLM provider (Anthropic, OpenAI, Google, local models)
3. **Transparent** - Clear reasoning, visible tool calls, actionable errors
4. **Workflow-oriented** - Tools match how users think, not just CRUD operations
5. **Type-safe** - Leverages Pydantic AI for reliable, maintainable agent development

---

## Target Users

**General Obsidian vault users** who want to:
- Interact with their notes using natural language
- Automate repetitive vault management tasks
- Discover connections and relationships in their knowledge base
- Save time on note organization and retrieval
- Maintain control over their data and LLM provider choice

**Technical Comfort Level:** Comfortable with basic command-line tools (installing dependencies, setting environment variables, running local services)

---

## MVP Scope

### In Scope

**Core Functionality:**
- ✅ Natural language querying of vault content (semantic search)
- ✅ Reading notes with contextual information (related notes, backlinks)
- ✅ Creating, updating, appending notes via natural language
- ✅ Folder management and organization
- ✅ Bulk operations (tagging, moving, updating multiple notes)
- ✅ OpenAI-compatible API endpoint for Obsidian Copilot integration

**Technical:**
- ✅ FastAPI backend with OpenAI-compatible `/v1/chat/completions` endpoint
- ✅ Pydantic AI agent with 3 consolidated tools
- ✅ Vertical Slice Architecture (VSA) with feature-based organization
- ✅ Provider-agnostic LLM support (Anthropic, OpenAI, Google, local models)
- ✅ Docker volume mounting for vault access (read-write bidirectional sync)
- ✅ Simple API key authentication
- ✅ UV for dependency management

**Integration:**
- ✅ Obsidian Copilot plugin as frontend
- ✅ CORS configuration for Obsidian app protocol

**Deployment:**
- ✅ Docker containerization for isolated deployment
- ✅ Docker Compose for orchestration
- ✅ Volume mounting for vault access

### Out of Scope (Future Considerations)

- ❌ Cloud hosting or SaaS deployment
- ❌ User authentication beyond API keys
- ❌ Multi-user support
- ❌ Database for conversation persistence (future enhancement)
- ❌ Advanced features: embeddings, semantic indexing, RAG (post-MVP)
- ❌ Support for other note-taking apps (Notion, Logseq, etc.)
- ❌ Obsidian plugin development (using existing Copilot plugin)
- ❌ Mobile support
- ❌ Real-time collaboration

---

## User Stories

### Primary User Stories

1. **As a vault user, I want to find notes using natural language**, so that I can locate information faster than manual search.
   - Example: "Find my notes about Python from last month"

2. **As a vault user, I want to read notes with their context**, so that I understand relationships and connections.
   - Example: "Read my architecture decision note and show me related documents"

3. **As a vault user, I want to create notes using natural language**, so that I can quickly capture ideas without manual formatting.
   - Example: "Create a new project note for the ML initiative with sections for goals, timeline, and team"

4. **As a vault user, I want to organize my vault automatically**, so that I don't spend time on manual file management.
   - Example: "Move all meeting notes from last quarter to the archive folder"

5. **As a vault user, I want to bulk-update notes**, so that I can maintain consistency across my vault.
   - Example: "Tag all notes in the Projects folder with 'active' and add a status field"

### Technical User Stories

6. **As a user, I want to choose my LLM provider**, so that I have control over costs, privacy, and capabilities.

7. **As a user, I want clear error messages**, so that I understand what went wrong and how to fix it.

8. **As a user, I want fast responses**, so that the agent doesn't interrupt my workflow.

---

## Core Architecture & Patterns

### Architecture: Vertical Slice Architecture (VSA)

```
project-root/
├── pyproject.toml          # UV configuration
├── .env                    # Environment variables
├── main.py                 # FastAPI app entry point
├── core/                   # Core infrastructure
│   ├── agent.py            # Single Pydantic AI agent
│   ├── config.py           # Settings (pydantic-settings)
│   ├── dependencies.py     # Agent dependencies
│   └── lifespan.py         # FastAPI startup/shutdown
├── shared/                 # Shared utilities
│   ├── vault/
│   │   ├── manager.py      # VaultManager class
│   │   └── models.py       # Vault domain models
│   └── openai_adapter.py   # OpenAI format conversion
└── features/               # Vertical slices (tools + routes)
    ├── chat/
    │   ├── routes.py       # POST /v1/chat/completions
    │   └── models.py       # ChatRequest, ChatResponse
    ├── vault_query/
    │   ├── tools.py        # obsidian_query_vault
    │   └── models.py       # QueryResult, NoteInfo
    ├── vault_context/
    │   ├── tools.py        # obsidian_get_context
    │   └── models.py       # ContextResult, NoteContent
    └── vault_management/
        ├── tools.py        # obsidian_vault_manager
        └── models.py       # OperationResult
```

### Key Patterns

**1. Single Agent Pattern**
- One Pydantic AI agent instance at module level
- Tools register via `@agent.tool` decorators
- Imported as side effects in `main.py`

**2. Tool Registration Flow**
```python
# core/agent.py - Define agent
vault_agent = Agent('anthropic:claude-sonnet-4-0', deps_type=VaultDependencies)

# features/vault_query/tools.py - Register tools
from core.agent import vault_agent

@vault_agent.tool
async def obsidian_query_vault(...):
    pass

# main.py - Import to register (side effect)
import features.vault_query.tools  # noqa: F401
```

**3. OpenAI Compatibility Layer**
- FastAPI route accepts OpenAI chat completion format
- Adapter converts to/from Pydantic AI format
- Enables Obsidian Copilot integration

**4. Feature-Based Organization**
- Each feature is self-contained (tools + models + routes)
- Tools group operations by workflow, not CRUD
- Follows Anthropic's "fewer, smarter tools" principle

---

## Tools

The agent exposes **3 consolidated tools** following Anthropic's best practices. See [mvp-tool-designs.md](./mvp-tool-designs.md) for detailed specifications.

### Tool 1: `obsidian_query_vault`
**Purpose:** All discovery, search, and listing operations (read-only)

**Operations:**
- Semantic search across vault content
- List vault/folder structure
- Find related notes
- Search by metadata (tags, dates)
- Get recent changes

**Key Feature:** Token-efficient with `response_format` parameter (concise vs detailed)

---

### Tool 2: `obsidian_vault_manager`
**Purpose:** All modification operations (notes + folders + bulk)

**Operations:**
- Note CRUD: create, update, append, delete, move
- Folder management: create, delete, move
- Bulk operations: bulk tag, bulk move, bulk update metadata

**Key Feature:** Integrated bulk operations via `targets` parameter; safety mechanisms for destructive operations

---

### Tool 3: `obsidian_get_context`
**Purpose:** Workflow-oriented reading with contextual information

**Operations:**
- Read single note with metadata
- Read multiple notes
- Gather related notes
- Read note with backlinks
- Get daily note

**Key Feature:** Compiles relevant context (related notes, backlinks) for synthesis tasks

---

## Technology Stack

### Backend
- **FastAPI** (0.115.0+) - Web framework with OpenAI-compatible endpoints
- **Pydantic AI** (0.0.14+) - Agent framework with tool orchestration
- **Pydantic** (2.9.0+) - Data validation and settings management
- **Python** (3.11+) - Core language
- **UV** - Dependency and package management
- **Docker** - Containerization for isolated deployment
- **Uvicorn** - ASGI server

### Optional Dependencies
- **python-frontmatter** (1.1.0+) - YAML frontmatter parsing
- **python-dotenv** (1.0.0+) - Environment variable management

### LLM Providers (Provider-Agnostic)
Supports any provider via Pydantic AI:
- Anthropic Claude (sonnet, opus)
- OpenAI (gpt-4, gpt-4-turbo, gpt-3.5-turbo)
- Google Gemini (gemini-pro, gemini-flash)
- Local models via Ollama (llama3, mistral, etc.)

### Frontend Integration
- **Obsidian Copilot** - Chat interface in Obsidian
- OpenAI-compatible custom endpoint configuration

---

## Security & Configuration

### Authentication
**Simple API Key Authentication:**
- Single API key defined in `.env`
- Validated on all `/v1/chat/completions` requests
- Passed via `Authorization: Bearer <API_KEY>` header from Obsidian Copilot

### Docker Deployment & Vault Access

**Volume Mounting for Vault Security:**

Paddy uses Docker volume mounting to provide secure, sandboxed access to your Obsidian vault:

```bash
# User sets their vault path in .env
OBSIDIAN_VAULT_PATH=/Users/name/Documents/MyVault

# Docker mounts it as /vault inside the container
docker run -v ${OBSIDIAN_VAULT_PATH}:/vault:rw \
           -e OBSIDIAN_VAULT_PATH=/vault \
           -p 8000:8000 \
           paddy-agent
```

**How It Works:**

1. **Host Configuration**: User specifies their vault path in `.env` (e.g., `/Users/name/Documents/MyVault`)
2. **Volume Mount**: Docker mounts this directory as `/vault` inside the container with read-write (`:rw`) permissions
3. **Container Access**: Inside the container, Paddy accesses the vault at `/vault` (the mounted path)
4. **Bidirectional Sync**: Changes made by Paddy are immediately visible to Obsidian and vice versa
5. **Sandboxing**: Container is restricted to only the mounted vault directory - cannot access other host files

**Security Benefits:**

- ✅ **Isolation**: Container cannot access files outside the mounted vault directory
- ✅ **Live Sync**: Real-time bidirectional synchronization between Paddy and Obsidian
- ✅ **Permission Control**: Volume mount uses explicit `:rw` (read-write) permissions
- ✅ **No Network File Sharing**: Direct file system access, no network protocols required
- ✅ **Simple Configuration**: Single environment variable controls vault access

### Configuration Management

**Environment Variables (`.env`):**
```bash
# LLM Provider Configuration
LLM_PROVIDER=anthropic              # anthropic | openai | google | ollama
LLM_MODEL=claude-sonnet-4-0         # Model identifier
LLM_API_KEY=sk-...                  # Provider API key

# Vault Configuration
OBSIDIAN_VAULT_PATH=/Users/name/Documents/MyVault  # Absolute path to vault on host
# Inside container, this becomes /vault via volume mount

# API Configuration
API_KEY=your-secret-api-key         # For Obsidian Copilot authentication
API_HOST=0.0.0.0                    # Host to bind (default: 0.0.0.0)
API_PORT=8000                       # Port to bind (default: 8000)

# CORS Configuration (for Obsidian)
ALLOWED_ORIGINS=app://obsidian.md,capacitor://localhost
```

**Docker Compose Configuration:**
```yaml
services:
  paddy:
    build: .
    container_name: paddy-agent
    ports:
      - "8000:8000"
    volumes:
      - ${OBSIDIAN_VAULT_PATH}:/vault:rw
    environment:
      - LLM_PROVIDER=${LLM_PROVIDER}
      - LLM_MODEL=${LLM_MODEL}
      - LLM_API_KEY=${LLM_API_KEY}
      - OBSIDIAN_VAULT_PATH=/vault  # Container path
      - API_KEY=${API_KEY}
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - ALLOWED_ORIGINS=${ALLOWED_ORIGINS}
    env_file:
      - .env
```

**Configuration Class (Pydantic Settings):**
```python
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    llm_provider: str
    llm_model: str
    llm_api_key: str
    obsidian_vault_path: Path  # Will be /vault inside container
    api_key: str
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    allowed_origins: list[str]

    class Config:
        env_file = ".env"
```

### Security Scope

**In Scope:**
- ✅ API key authentication for Obsidian Copilot
- ✅ CORS configuration for Obsidian app protocol
- ✅ Environment-based secrets management
- ✅ Docker volume mounting for sandboxed vault access
- ✅ Container isolation (only vault directory accessible)
- ✅ Safe file system operations (path validation)

**Out of Scope (Keep Simple):**
- ❌ User authentication/authorization
- ❌ Rate limiting
- ❌ Request logging (beyond basic FastAPI logs)
- ❌ Encryption at rest
- ❌ Multi-tenancy

---

## API Specification

### Endpoint: `POST /v1/chat/completions`

**OpenAI-Compatible Format:**

**Request:**
```json
{
  "model": "paddy",
  "messages": [
    {"role": "user", "content": "Find my notes about machine learning"}
  ],
  "stream": false
}
```

**Response:**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "paddy",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "I found 5 notes about machine learning:\n1. ML Project Overview.md\n2. Neural Networks Basics.md\n..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 150,
    "total_tokens": 170
  }
}
```

**Authentication:**
```
Authorization: Bearer <API_KEY>
```

**CORS Headers:**
```
Access-Control-Allow-Origin: app://obsidian.md
Access-Control-Allow-Methods: POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
```

---

## Success Criteria

### MVP Success Definition: **The Product Works**

**Functional Requirements:**
- ✅ User can start Paddy with `docker compose up` or `docker run`
- ✅ Vault is accessible via volume mount with bidirectional sync
- ✅ Obsidian Copilot successfully connects to the API
- ✅ All 3 tools execute successfully for their intended operations
- ✅ Natural language queries return relevant results
- ✅ Notes can be created, read, updated via Paddy
- ✅ Bulk operations work on multiple notes
- ✅ Error messages are clear and actionable
- ✅ Provider can be switched via environment variable
- ✅ Changes made by Paddy appear immediately in Obsidian

**Quality Indicators:**
- No critical bugs in core workflows
- Agent selects appropriate tools for tasks
- File system operations don't corrupt vault
- API responses follow OpenAI format correctly

**User Experience:**
- Setup takes <15 minutes for technical users
- Agent responses are relevant to queries
- Users can accomplish basic vault tasks via natural language

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Goal:** Basic agent with one working tool

**Deliverables:**
- ✅ Project scaffolding with UV
- ✅ Dockerfile and docker-compose.yml
- ✅ Volume mounting for vault access
- ✅ FastAPI app with OpenAI endpoint
- ✅ Core agent setup (Pydantic AI)
- ✅ `obsidian_query_vault` tool (semantic search)
- ✅ Obsidian Copilot integration working
- ✅ Provider-agnostic configuration

**Validation:** User can search vault via natural language in Obsidian using Dockerized Paddy

---

### Phase 2: Reading & Basic Operations (Week 2-3)
**Goal:** Enable reading and simple modifications

**Deliverables:**
- ✅ `obsidian_get_context` tool (read notes)
- ✅ `obsidian_vault_manager` tool (create, append, update notes)
- ✅ VaultManager class for file operations
- ✅ Frontmatter parsing

**Validation:** User can read notes and create/modify notes via agent

---

### Phase 3: Advanced Operations (Week 3-4)
**Goal:** Complete tool functionality

**Deliverables:**
- ✅ Bulk operations in `vault_manager`
- ✅ Folder management operations
- ✅ Related notes discovery
- ✅ Backlinks support
- ✅ Error handling and validation

**Validation:** All tool operations work reliably; user can manage vault entirely through agent

---

### Phase 4: Polish & Documentation (Week 4+)
**Goal:** Production-ready MVP

**Deliverables:**
- ✅ Comprehensive README with setup instructions
- ✅ Example `.env.example` file
- ✅ Error message improvements
- ✅ Performance testing
- ✅ Edge case handling

**Validation:** New users can set up and use the product independently

---

## Future Considerations (Post-MVP)

**Potential Enhancements:**
- Conversation history persistence (SQLite/PostgreSQL)
- Streaming responses (SSE) for better UX
- Semantic embeddings for improved search
- RAG implementation for large vaults
- Task extraction and management
- Template-based note generation
- Plugin system for custom tools
- Web UI for configuration
- Multi-vault support
- Kubernetes deployment manifests

**Integration Opportunities:**
- Obsidian Local REST API plugin (for advanced features)
- Model Context Protocol (MCP) server
- Other Obsidian plugins (Smart Connections, Dataview)

**Advanced Features:**
- Graph relationship analysis
- Automatic note linking suggestions
- Scheduled operations (daily note generation, etc.)
- Voice input/output
- Custom prompt templates

---

## Risks & Mitigations

### Risk: LLM Costs
**Mitigation:** Provider-agnostic design allows users to choose cost-effective options (local models, smaller models)

### Risk: Vault Corruption
**Mitigation:**
- File operations use atomic writes
- Delete operations require confirmation
- Validation before destructive operations
- Users maintain backups (standard Obsidian practice)

### Risk: Poor Agent Performance
**Mitigation:**
- Follow Anthropic's tool design best practices
- Clear tool descriptions and examples
- Iterative testing and refinement
- Start with simple, proven patterns

### Risk: Complex Setup
**Mitigation:**
- Clear documentation
- `.env.example` with all required variables
- Minimal dependencies via UV
- Step-by-step setup guide

---

## Appendix

### Related Documents
- [MVP Tool Designs](./mvp-tool-designs.md) - Detailed tool specifications
- [Anthropic: Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents) - Tool design principles

### Key Dependencies
- FastAPI: https://fastapi.tiangolo.com/
- Pydantic AI: https://ai.pydantic.dev/
- Obsidian Copilot: https://www.obsidiancopilot.com/
- UV: https://docs.astral.sh/uv/

### Repository Structure
```
paddy/
├── README.md              # Setup and usage instructions
├── PRD.md                 # This document
├── mvp-tool-designs.md    # Tool specifications
├── Dockerfile             # Container definition
├── docker-compose.yml     # Docker orchestration
├── pyproject.toml         # UV configuration
├── .env.example           # Environment variable template
├── .gitignore
├── .dockerignore
├── main.py                # FastAPI entry point
├── core/                  # Core infrastructure
├── shared/                # Shared utilities
└── features/              # Feature slices (tools + routes)
```
