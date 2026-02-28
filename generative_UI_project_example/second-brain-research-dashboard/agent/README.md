# Second Brain Agent

Pydantic AI agent for transforming Markdown research documents into generative UI dashboards using the AG-UI protocol.

## Overview

This agent powers the Second Brain Dashboard by:
1. Analyzing Markdown content (structure, type, media)
2. Selecting optimal layout (magazine, dashboard, tutorial, etc.)
3. Generating A2UI component definitions
4. Streaming results via AG-UI protocol

## Quick Start

### Prerequisites

- Python 3.10 or higher
- `uv` (recommended) or `pip`
- OpenRouter API key

### Setup

1. **Install dependencies:**

   ```bash
   # Option 1: Using uv (recommended)
   chmod +x setup.sh
   ./setup.sh

   # Option 2: Manual setup with uv
   uv sync

   # Option 3: Manual setup with pip
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**

   ```bash
   # Copy the example environment file
   cp .env.example .env

   # Edit .env and add your OpenRouter API key
   # OPENROUTER_API_KEY=your_key_here
   ```

3. **Run the agent:**

   ```bash
   # Option 1: Using uv
   uv run uvicorn main:app --reload --port 8000

   # Option 2: Using pip (activate venv first)
   source .venv/bin/activate
   uvicorn main:app --reload --port 8000

   # Option 3: Run main.py directly
   python main.py
   ```

4. **Verify it's running:**

   ```bash
   # Health check
   curl http://localhost:8000/health

   # API documentation
   open http://localhost:8000/docs
   ```

## API Endpoints

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "agent_ready": true
}
```

### POST /ag-ui/stream

AG-UI streaming endpoint for generative UI.

**Request:**
```json
{
  "markdown": "# My Research\n\nContent here...",
  "user_id": "optional-user-id"
}
```

**Response:**
Server-sent events (text/event-stream) with AG-UI protocol messages.

## Project Structure

```
agent/
├── main.py              # FastAPI application
├── pyproject.toml       # Project configuration (uv)
├── requirements.txt     # Dependencies (pip fallback)
├── .env.example         # Environment variables template
├── .env                 # Your environment variables (gitignored)
├── setup.sh            # Setup script
└── README.md           # This file
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | Yes | - | OpenRouter API key for Claude Sonnet 4 |
| `OPENROUTER_MODEL` | No | `anthropic/claude-sonnet-4` | Model identifier |
| `BACKEND_PORT` | No | `8000` | FastAPI server port |
| `ALLOWED_ORIGINS` | No | `http://localhost:3010,http://localhost:3000` | CORS allowed origins |
| `NODE_ENV` | No | `development` | Environment mode |

## Development

### Code Quality

```bash
# Format code with black
black .

# Lint with ruff
ruff check .

# Type checking (if mypy is added)
mypy .
```

### Testing

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=. --cov-report=html
```

## AG-UI Protocol Integration

The `/ag-ui/stream` endpoint implements the AG-UI protocol for streaming generative UI updates:

1. **Client sends POST request** with Markdown content
2. **Agent analyzes content** using Pydantic AI
3. **Agent streams AG-UI messages** with component definitions
4. **Frontend renders components** in real-time using A2UI

### Example AG-UI Message Flow

```
data: {"type": "status", "message": "Agent initialized"}

data: {"type": "component", "component": {"type": "headline", "text": "Breaking News"}}

data: {"type": "component", "component": {"type": "stat", "value": "42", "label": "Items"}}

data: {"type": "complete", "message": "Dashboard generation complete"}
```

## Next Steps (TODO)

- [ ] Implement Pydantic AI agent logic in `/ag-ui/stream`
- [ ] Add content analysis (type detection, structure analysis)
- [ ] Add layout selection (magazine, dashboard, tutorial, etc.)
- [ ] Add A2UI component extraction (headlines, stats, videos, etc.)
- [ ] Add tests for agent logic
- [ ] Add logging and monitoring

## Troubleshooting

**Issue: `OPENROUTER_API_KEY not configured`**
- Solution: Edit `.env` file and add your OpenRouter API key

**Issue: Port 8000 already in use**
- Solution: Change `BACKEND_PORT` in `.env` or use `--port` flag

**Issue: CORS errors from frontend**
- Solution: Add your frontend URL to `ALLOWED_ORIGINS` in `.env`

## License

MIT
