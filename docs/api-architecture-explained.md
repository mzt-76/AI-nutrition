# API Architecture — Key Concepts Explained

Reference doc for the FastAPI backend (`src/api.py`) concepts.

---

## 1. Why Our API Has Fewer Globals Than the Course

The course initializes all clients as globals in `lifespan()`:

```python
# Course: all clients as globals
embedding_client, supabase = get_agent_clients()
http_client = AsyncClient()
```

We only need 3 globals: `supabase`, `title_agent`, `mem0_client`.

**Why?** Our `create_agent_deps()` factory creates all agent clients internally (embedding, openai, http, brave). We only need globals for things the **API layer** uses directly — not the agent.

| Global | Used by API for |
|---|---|
| `supabase` | `store_message`, `check_rate_limit`, `fetch_conversation_history`, `list_conversations` |
| `title_agent` | Generate conversation titles (separate lightweight agent) |
| `mem0_client` | Search/save user memories before/after agent runs |

Clients like `embedding_client`, `http_client`, `brave_api_key` are only used inside the agent's tools — `create_agent_deps()` handles them.

---

## 2. No Shutdown Cleanup (vs Course)

The course has:

```python
# Shutdown: Clean up resources
if http_client:
    await http_client.aclose()
```

We don't need this because we have no global async clients with open connection pools. The course creates `AsyncClient()` as a global which holds open connections. Our `http_client` is created per-request inside `create_agent_deps()`.

---

## 3. No `security = HTTPBearer()` (vs Course)

The course has real auth wired in:

```python
security = HTTPBearer()

@app.post("/api/pydantic-agent")
async def pydantic_agent(request: AgentRequest, user: Dict = Depends(verify_token)):
    # verify_token extracts JWT from Authorization header using `security`
```

We skip this because **auth is not in scope yet** (later course module). Our endpoint trusts `user_id` from the request body. When auth is implemented, we'll add `HTTPBearer()` + `Depends(verify_token)`.

---

## 4. CORS: Restrictive vs Wildcard

Course uses `allow_origins=["*"]` (any website can call the API).

We use a configurable allowlist:

```python
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
```

This only allows our React dev servers by default. In production, set `CORS_ORIGINS=https://your-app.com` without code changes.

---

## 5. The `try/except` Wrapper Around the Endpoint

The entire endpoint logic is wrapped in a try/except:

```python
async def agent_endpoint(request: AgentRequest):
    try:
        # ... all logic ...
        return StreamingResponse(...)
    except Exception as e:
        return StreamingResponse(
            _stream_error(f"Error: {e}", request.session_id),
            media_type="text/plain",
        )
```

**Why?** Without it, an unexpected crash returns a raw 500 HTML error that the frontend can't parse. With it, the frontend always receives a parseable NDJSON error response.

---

## 6. `asyncio.create_task()` — Parallel Operations

`asyncio.create_task()` starts a coroutine **without waiting for it**. This lets operations run in parallel.

### Without create_task (sequential)

```python
# Generate title — WAIT 1-2 seconds
title = await generate_conversation_title(title_agent, request.query)

# Only THEN start the agent — user waits for both
async with agent.iter(...) as run:
    ...
```

Total time = title + agent (added together).

### With create_task (parallel)

```python
# START title generation — returns IMMEDIATELY
title_task = asyncio.create_task(
    generate_conversation_title(title_agent, request.query)
)

# Start agent RIGHT AWAY (no waiting for title)
async with agent.iter(...) as run:
    # ... stream chunks to user ...

# AFTER streaming, collect the title (already done by now)
title = await title_task
```

Total time = max(title, agent) — they run at the same time.

### Visual timeline

```
Sequential:
  [--- title (1.5s) ---][-------- agent (5s) --------]
                                                       → 6.5s total

Parallel (create_task):
  [--- title (1.5s) ---]
  [-------- agent (5s) --------]
                                → 5s total
```

The event loop switches between tasks whenever one is waiting on I/O (LLM API calls).

---

## 7. Async Generators and StreamingResponse

### Regular function vs async generator

A **regular function** runs immediately:

```python
def greet(name):
    print("Running!")       # Executes NOW
    return f"Hello {name}"

result = greet("Alice")     # "Running!" prints immediately
```

An **async generator** (function with `yield`) does NOT run when called:

```python
async def greet_stream(name):
    print("Running!")          # NOT executed yet
    yield f"Hello {name}\n"    # NOT executed yet
    yield f"How are you?\n"    # NOT executed yet

gen = greet_stream("Alice")    # Nothing happens! No print!
```

The body only runs when something **iterates** over it:

```python
async for chunk in gen:    # NOW "Running!" prints
    print(chunk)           # First loop:  "Hello Alice\n"
                           # Second loop: "How are you?\n"
```

Each `yield` **pauses** the function and sends one piece. The function **resumes** at the next iteration.

### What is StreamingResponse?

Normally, FastAPI builds the **entire response in memory** then sends it all at once:

```python
@app.get("/data")
async def get_data():
    return {"message": "All data at once"}
    # Client waits until fully built, receives everything in one shot
```

`StreamingResponse` sends data **piece by piece** as it becomes available:

```python
return StreamingResponse(some_generator, media_type="text/plain")
```

Internally (simplified):

```python
class StreamingResponse:
    def __init__(self, generator, ...):
        self.generator = generator    # Just stores it, doesn't run it

    async def send_to_client(self):
        async for chunk in self.generator:   # NOW the generator runs
            send_chunk_to_client(chunk)      # Each piece sent immediately
```

### Full flow in our API

```
1. User sends POST /api/agent
         |
2. agent_endpoint() runs setup (rate limit, session, memories)
         |
3. return StreamingResponse(_stream_agent_response(...))
         |
   _stream_agent_response() is CALLED but body does NOT execute.
   Returns a generator object -> passed to StreamingResponse.
         |
4. FastAPI starts iterating the generator
         |
5. _stream_agent_response body NOW executes:

   async with agent.iter(query, ...) as run:
       async for node in run:
           async for event in request_stream:
               yield {"text": "Bon"}           -> sent to client immediately
               yield {"text": "Bonjour"}       -> sent to client immediately
               yield {"text": "Bonjour! Co.."} -> sent to client immediately

   yield {"text": "...", "complete": True}     -> client knows it's done
         |
6. Generator exhausted -> connection closed
```

### Why streaming matters

Without streaming: user stares at a blank screen for 5-10 seconds, then gets the full response.

With streaming: words appear progressively (like ChatGPT). Each `yield` sends a chunk the instant the LLM produces it.

---

## 8. Extracted Streaming Function vs Nested (Course Style)

The course defines `stream_response()` as a nested function inside the endpoint:

```python
# Course: nested
@app.post("/api/agent")
async def endpoint(request):
    # setup...
    async def stream_response():     # nested, uses closure variables
        nonlocal conversation_title
        async with agent.iter(...):
            ...
    return StreamingResponse(stream_response())
```

We extract it as a standalone function:

```python
# Ours: extracted
async def _stream_agent_response(request, session_id, pydantic_messages, ...):
    # receives everything as parameters
    async with agent.iter(...):
        ...

@app.post("/api/agent")
async def endpoint(request):
    # setup...
    return StreamingResponse(_stream_agent_response(request=..., session_id=...))
```

| | Course (nested) | Ours (extracted) |
|---|---|---|
| Variable access | Via closure (`nonlocal`) | Via parameters |
| Readability | One big function, deeply indented | Endpoint stays short |
| Testability | Harder to test in isolation | Can test separately |

Same result — purely organizational preference.
