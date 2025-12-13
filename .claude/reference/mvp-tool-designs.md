# MVP Tool Design: Obsidian AI Agent

## Design Philosophy

Based on [Anthropic's best practices for writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents), our MVP uses **3 consolidated, workflow-oriented tools** instead of many single-purpose tools.

**Core Principle:** "Fewer, smarter tools beat many simple ones"

### Key Design Principles

1. **Consolidate operations into high-impact tools** - Group related operations by workflow, not just CRUD actions
2. **Match user workflows, not just APIs** - Tools should represent how users think about their tasks
3. **Clear namespacing** - All Obsidian-specific tools prefixed with `obsidian_`
4. **Response format flexibility** - Support detailed vs concise responses to manage token usage
5. **Natural language over IDs** - Use human-readable paths and names to reduce hallucinations
6. **Helpful error messages** - Guide agents toward correct patterns with actionable feedback

---

## The Three-Tool Architecture

```
1. obsidian_query_vault       → Discovery & Search (read-only)
2. obsidian_vault_manager     → All Modifications (notes + folders + bulk)
3. obsidian_get_context       → Reading with Context (workflow-oriented reading)
```

**Why 3 Tools?**

- ✅ Cleanest separation: discover → read → modify
- ✅ Fewest tools following Anthropic's guidance
- ✅ Bulk operations naturally integrated via parameters
- ✅ Folder operations integrated (they're vault organization, not separate workflow)
- ✅ Each tool has clear, distinct purpose
- ✅ Reduces agent confusion about tool selection

---

## Tool 1: `obsidian_query_vault`

### Purpose
All discovery, search, and listing operations (read-only). Use this tool when you need to **find** something in the vault.

### When to Use
- Finding notes by content or metadata
- Exploring vault structure
- Discovering relationships between notes
- Listing recently changed files

### Parameters

```python
async def obsidian_query_vault(
    ctx: RunContext[VaultDependencies],
    query_type: Literal[
        "semantic_search",      # Natural language search across content
        "list_structure",       # Browse folders and files
        "find_related",         # Discover connected notes
        "search_by_metadata",   # Filter by tags, dates, properties
        "recent_changes"        # Recently modified files
    ],
    query: str | None = None,           # Search query (required for semantic_search, search_by_metadata)
    path: str = "",                      # Specific folder path (for list_structure)
    reference_note: str | None = None,   # Note path for finding related (find_related)
    filters: dict | None = None,         # Metadata filters: {tags: [...], date_range: {...}}
    limit: int = 10,                     # Max results to return
    response_format: Literal["detailed", "concise"] = "detailed"
) -> QueryResult:
    """
    Query the Obsidian vault for discovery and search operations.

    This is a read-only tool for finding and discovering vault content.
    Use obsidian_get_context to read the actual content of notes.

    Examples:

    1. Find notes about machine learning:
       query_type="semantic_search",
       query="machine learning"

    2. List all files in Projects folder:
       query_type="list_structure",
       path="Projects"

    3. Find notes related to "Architecture Decisions.md":
       query_type="find_related",
       reference_note="Architecture Decisions.md"

    4. Find notes tagged 'urgent' from last week:
       query_type="search_by_metadata",
       filters={"tags": ["urgent"], "date_range": {"days": 7}}

    5. See what files changed recently:
       query_type="recent_changes",
       limit=20
    """
```

### Response Format

```python
class QueryResult(BaseModel):
    results: list[NoteInfo]
    total_found: int
    truncated: bool
    suggestion: str | None  # If truncated: "Try narrowing by date or tags"

class NoteInfo(BaseModel):
    # Always included (concise mode)
    path: str           # "Projects/ML Project.md"
    title: str          # "ML Project"
    relevance: float    # 0.95 (for semantic search)

    # Detailed mode only
    excerpt: str | None      # First 200 chars or matching context
    tags: list[str] | None
    created: str | None
    modified: str | None
```

### Token Efficiency

- **Concise mode**: ~50 tokens per result
- **Detailed mode**: ~200 tokens per result
- 67% token reduction when using concise mode for large result sets

### Error Handling Examples

```python
# No results found
{
    "results": [],
    "total_found": 0,
    "truncated": False,
    "suggestion": "No notes found matching 'quantum physics'. Try broader terms like 'physics' or check spelling."
}

# Results truncated
{
    "results": [...],  # First 10 results
    "total_found": 247,
    "truncated": True,
    "suggestion": "Showing 10 of 247 results. Try narrowing your search with filters={'tags': ['specific-tag']} or a more specific query."
}
```

---

## Tool 2: `obsidian_vault_manager`

### Purpose
All modification operations (notes, folders, organization). Use this tool when you need to **change** something in the vault.

### When to Use
- Creating, updating, deleting notes
- Creating, deleting, moving folders
- Moving notes between folders
- Bulk operations on multiple notes/folders
- Organizing vault structure

### Parameters

```python
async def obsidian_vault_manager(
    ctx: RunContext[VaultDependencies],
    operation: Literal[
        # Note operations
        "create_note",
        "update_note",
        "append_note",
        "delete_note",
        "move_note",

        # Folder operations
        "create_folder",
        "delete_folder",
        "move_folder",

        # Bulk operations
        "bulk_tag",              # Add/remove tags from multiple notes
        "bulk_move",             # Move multiple notes to folder
        "bulk_update_metadata"   # Update frontmatter on multiple notes
    ],

    # Single target operations
    target: str | None = None,           # Note/folder path for single operations

    # Bulk target operations
    targets: list[str] | None = None,    # Multiple paths for bulk operations

    # Content parameters
    content: str | None = None,          # Note content (create, update, append)
    destination: str | None = None,      # Target folder (move operations)

    # Metadata parameters
    metadata: dict | None = None,        # Frontmatter: {tags: [...], title: "...", ...}
    metadata_changes: dict | None = None, # For bulk_update_metadata

    # Safety parameters
    confirm_destructive: bool = False,   # Required true for delete operations
    create_folders: bool = True          # Auto-create parent folders if missing
) -> OperationResult:
    """
    Manage notes, folders, and perform bulk operations on the Obsidian vault.

    This tool handles all vault modifications. Use obsidian_query_vault first
    to find notes you want to modify.

    Examples:

    1. Create note with frontmatter:
       operation="create_note",
       target="Projects/New Project.md",
       content="# New Project\n\nProject details...",
       metadata={"tags": ["project", "active"], "status": "planning"}

    2. Append to daily note:
       operation="append_note",
       target="Daily/2025-01-15.md",
       content="\n## Meeting Notes\n- Discussed architecture"

    3. Update entire note:
       operation="update_note",
       target="Draft.md",
       content="# Revised Draft\n\nCompletely new content..."

    4. Move note to archive:
       operation="move_note",
       target="Old Project.md",
       destination="Archive/2024"

    5. Bulk tag multiple notes:
       operation="bulk_tag",
       targets=["note1.md", "note2.md", "note3.md"],
       metadata={"tags": ["reviewed"]}

    6. Create nested folder structure:
       operation="create_folder",
       target="Projects/2025/Q1",
       create_folders=True

    7. Delete note (requires confirmation):
       operation="delete_note",
       target="Draft.md",
       confirm_destructive=True

    8. Bulk move notes to new folder:
       operation="bulk_move",
       targets=["note1.md", "note2.md"],
       destination="Archive/Old Projects"
    """
```

### Response Format

```python
class OperationResult(BaseModel):
    success: bool
    operation: str
    affected_count: int        # Number of items affected
    affected_paths: list[str]  # Paths that were modified
    message: str               # Human-readable summary
    warnings: list[str] | None # Any non-fatal issues

    # For bulk operations
    partial_success: bool | None  # True if some succeeded, some failed
    failures: list[dict] | None   # Failed items with reasons
```

### Error Handling Examples

```python
# Missing confirmation for destructive operation
{
    "success": False,
    "message": "Invalid operation: delete_note requires confirm_destructive=True. This prevents accidental data loss. Set confirm_destructive=True to proceed.",
    "affected_count": 0,
    "affected_paths": []
}

# Missing parent folder
{
    "success": False,
    "message": "Cannot create note at 'Projects/Q1/note.md': folder 'Projects/Q1' doesn't exist. Set create_folders=True to automatically create missing folders, or use operation='create_folder' first.",
    "affected_count": 0,
    "affected_paths": []
}

# Partial bulk operation success
{
    "success": True,
    "partial_success": True,
    "operation": "bulk_tag",
    "affected_count": 3,
    "affected_paths": ["note3.md", "note4.md", "note5.md"],
    "message": "Bulk operation partially completed: 3 of 5 notes updated successfully.",
    "failures": [
        {"path": "note1.md", "reason": "File not found"},
        {"path": "note2.md", "reason": "Permission denied"}
    ]
}
```

### Safety Mechanisms

1. **Destructive operations require confirmation**: Delete operations must set `confirm_destructive=True`
2. **Partial success reporting**: Bulk operations report which items succeeded and which failed
3. **Automatic folder creation**: Optional `create_folders` parameter prevents multi-step workflows
4. **Clear warnings**: Non-fatal issues reported in `warnings` field

---

## Tool 3: `obsidian_get_context`

### Purpose
Workflow-oriented reading that compiles relevant context. Use this tool when you need to **read** content with surrounding context.

### When to Use
- Reading note content with metadata
- Gathering related information for synthesis
- Reading multiple notes together
- Exploring note relationships via backlinks
- Getting daily notes

### Parameters

```python
async def obsidian_get_context(
    ctx: RunContext[VaultDependencies],
    context_type: Literal[
        "read_note",           # Read single note with metadata
        "read_multiple",       # Read several specific notes
        "gather_related",      # Read note + its related notes
        "daily_note",          # Get today's (or specific) daily note
        "note_with_backlinks"  # Read note + all notes linking to it
    ],

    # Target specification
    target: str | None = None,           # Primary note path
    targets: list[str] | None = None,    # Multiple note paths (read_multiple)
    date: str | None = None,             # For daily_note: "2025-01-15" or "today"

    # Context control
    include_metadata: bool = True,       # Include frontmatter
    include_backlinks: bool = False,     # Include linking note info
    max_related: int = 3,                # Max related notes to include
    response_format: Literal["detailed", "concise"] = "detailed"
) -> ContextResult:
    """
    Retrieve note content with optional context for analysis and synthesis.

    This tool is optimized for reading workflows where you need content
    plus surrounding context (metadata, related notes, backlinks).

    Use obsidian_query_vault to find notes first, then use this tool
    to read their content.

    Examples:

    1. Read single note with metadata:
       context_type="read_note",
       target="Projects/ML Project.md",
       include_metadata=True

    2. Read note and its related notes:
       context_type="gather_related",
       target="Architecture.md",
       max_related=5

    3. Get today's daily note:
       context_type="daily_note",
       date="today"

    4. Read multiple notes for comparison:
       context_type="read_multiple",
       targets=["note1.md", "note2.md", "note3.md"]

    5. Read note with all backlinks:
       context_type="note_with_backlinks",
       target="Concepts/Zettelkasten.md"

    6. Read note in concise format (save tokens):
       context_type="read_note",
       target="Long Article.md",
       response_format="concise"
    """
```

### Response Format

```python
class ContextResult(BaseModel):
    primary_note: NoteContent
    related_notes: list[NoteContent] | None
    backlinks: list[BacklinkInfo] | None
    metadata_summary: dict | None  # Compiled metadata (tags, dates, etc.)
    token_estimate: int            # Approximate tokens in response

class NoteContent(BaseModel):
    path: str
    title: str
    content: str
    metadata: dict | None
    word_count: int

class BacklinkInfo(BaseModel):
    note_path: str
    note_title: str
    context: str  # Surrounding text where link appears
```

### Why Separate from `obsidian_query_vault`?

**Key Difference:**
- `obsidian_query_vault` returns **summaries** and **excerpts** (discovery)
- `obsidian_get_context` returns **full content** (reading)

This separation:
- ✅ Prevents token waste from reading full notes during search
- ✅ Follows Anthropic's pattern of `search_logs` (summaries) vs `get_customer_context` (full data)
- ✅ Enables two-step workflow: find → read
- ✅ Provides workflow-oriented context (related notes, backlinks)

---

## Rationale: Why These 3 Tools?

### 1. Follows Anthropic's Core Principle

> "Fewer, smarter tools beat many simple ones"

Three tools is the minimum viable set covering all workflows:
- **Query** (find things) → `obsidian_query_vault`
- **Read** (get content) → `obsidian_get_context`
- **Modify** (change things) → `obsidian_vault_manager`

### 2. Bulk Operations Belong in Manager

Bulk is just a parameter variation, not a separate workflow:

```python
# Single operation
operation="update_note", target="note.md"

# Bulk operation
operation="bulk_update_metadata", targets=["note1.md", "note2.md", "note3.md"]
```

**Benefits:**
- ✅ No artificial tool separation
- ✅ Agent doesn't choose between similar tools
- ✅ Consistent parameter patterns
- ✅ Follows Anthropic's consolidation principle

### 3. Folders Are Part of Vault Management

Folders don't have distinct workflows from notes:
- Creating notes often creates folders: `create_note(target="Projects/2025/note.md", create_folders=True)`
- Moving notes IS organizing folders
- Folders exist to organize notes

**Benefits:**
- ✅ Single tool for all organization
- ✅ No confusion about which tool to use
- ✅ Natural parameter model

### 4. Each Tool Has Clear Purpose

Mental model is simple:
- **Need to find?** → `obsidian_query_vault`
- **Need to read?** → `obsidian_get_context`
- **Need to change?** → `obsidian_vault_manager`

### 5. Real-World Usage Patterns

Common workflows naturally map to these tools:

**Workflow: "Find my notes about Python and summarize them"**
```python
# Step 1: Find notes
results = obsidian_query_vault(
    query_type="semantic_search",
    query="Python programming"
)

# Step 2: Read content
context = obsidian_get_context(
    context_type="read_multiple",
    targets=[r.path for r in results.results[:3]]
)

# Step 3: Agent synthesizes summary
```

**Workflow: "Create a new project note in the 2025 folder"**
```python
obsidian_vault_manager(
    operation="create_note",
    target="Projects/2025/New Project.md",
    content="# New Project\n\nProject goals...",
    metadata={"tags": ["project", "2025"], "status": "planning"},
    create_folders=True
)
```

**Workflow: "Tag all my meeting notes from last week as 'reviewed'"**
```python
# Step 1: Find meeting notes
results = obsidian_query_vault(
    query_type="search_by_metadata",
    filters={"folder": "Meetings", "date_range": {"days": 7}}
)

# Step 2: Bulk tag them
obsidian_vault_manager(
    operation="bulk_tag",
    targets=[r.path for r in results.results],
    metadata={"tags": ["reviewed"]}
)
```

---

## Implementation Structure

```
app/features/
├── vault_query/              # Discovery operations
│   ├── __init__.py
│   ├── tools.py              # obsidian_query_vault
│   └── models.py             # QueryResult, NoteInfo
│
├── vault_context/            # Reading with context
│   ├── __init__.py
│   ├── tools.py              # obsidian_get_context
│   └── models.py             # ContextResult, NoteContent, BacklinkInfo
│
└── vault_management/         # All modifications
    ├── __init__.py
    ├── tools.py              # obsidian_vault_manager
    └── models.py             # OperationResult
```

---

## Key Anthropic Principles Applied

### 1. Token Efficiency
- **Response format parameter**: `"detailed"` vs `"concise"` (67% token reduction)
- **Pagination & limits**: Sensible defaults with override capability
- **Truncation guidance**: Clear suggestions when results are truncated

### 2. Natural Language Over IDs
- Use human-readable paths: `"Projects/ML Project.md"`
- Not cryptic identifiers: `"uuid-abc-123-def-456"`
- Reduces hallucinations and improves precision

### 3. Helpful Error Messages
```python
# ✅ Good: Specific, actionable guidance
"Cannot create note at 'Projects/Q1/note.md': folder 'Projects/Q1' doesn't exist.
Set create_folders=True to automatically create missing folders, or use
operation='create_folder' first."

# ❌ Bad: Opaque error
"Error: ENOENT"
```

### 4. Clear Parameter Naming
- `target` not `file` (explicit about what it refers to)
- `confirm_destructive` not `force` (clear about safety)
- `max_related` not `limit` (specific about what's being limited)

### 5. Workflow Consolidation
- `schedule_event` pattern: Combines find availability + book meeting
- Our `gather_related`: Combines read note + find related + read related
- Our `bulk_tag`: Combines validate paths + update metadata on all
