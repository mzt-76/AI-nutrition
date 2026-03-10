---
name: project-audit
description: >
  Audit complet du codebase avant deploiement. Analyse tout le code sur 6 dimensions
  (simplicite, modularite, efficacite, securite, correctitude, conformite aux standards)
  via 4 agents paralleles specialises + consolidation. Produit un rapport detaille et un
  plan de fixes compatible /execute.
  Triggers: "audit", "code review complet", "pre-deployment review", "check code quality",
  "find all issues", "audit complet", "revue de code", "analyse du projet"
---

# Project Audit — Audit complet du codebase

## Overview

Audit exhaustif du codebase via 4 agents paralleles specialises (Backend, Security, Frontend, Architecture) suivi d'une consolidation. Produit un rapport d'audit dans `.claude/audits/` et un plan de fixes compatible `/execute`.

---

## Workflow — 6 Phases

### Phase 1: Context Gathering

Before launching agents, gather project context:

1. **Read project rules**: Read `CLAUDE.md` to internalize all rules (the 13 rules are the audit checklist)
2. **Read constants**: Read `src/nutrition/constants.py` to know what magic numbers should reference
3. **Project stats**: Run `find src/ -name '*.py' | xargs wc -l`, `find frontend/src -name '*.ts' -o -name '*.tsx' | xargs wc -l` for size overview
4. **Pre-flight linters**: Run these in parallel and capture output (do NOT fix, just collect):
   - `ruff check src/ scripts/ skills/ 2>&1 | tail -30`
   - `mypy src/ 2>&1 | tail -30`
   - `cd frontend && npx tsc --noEmit 2>&1 | tail -30`

Save all outputs — they feed into agent prompts.

---

### Phase 2: Launch 4 Parallel Agents

Launch ALL 4 agents simultaneously using the Agent tool with `run_in_background: true`. Each agent is `subagent_type: "Explore"` with `mode: "bypassPermissions"`.

**CRITICAL**: Send all 4 Agent tool calls in a SINGLE message so they run in parallel.

Each agent receives:
- The project rules from CLAUDE.md (summarized)
- The linter outputs from Phase 1
- Their specific scope and focus areas
- The standardized finding format (below)

#### Standardized Finding Format (shared by all agents)

Every finding MUST use this exact format:
```
### Finding N
- **severity**: critical | high | medium | low
- **category**: simplicity | modularity | efficiency | security | correctness | standards
- **file**: path/to/file.py
- **lines**: 42-58
- **title**: One-line summary
- **what**: What is wrong (2-3 sentences, specific)
- **why**: Why it matters — user impact, maintainability, security
- **evidence**: Code snippet or command output proving the issue
- **suggested_fix**: Concrete description of the fix
- **confidence**: verified | probable | needs-testing
```

---

#### Agent A — Backend & Logic

**Scope**: `src/`, `skills/*/scripts/`, `scripts/`
**Focus**: Correctitude, simplicite, efficacite, types

**Prompt template** (adapt with Phase 1 context):

```
You are Agent A — Backend & Logic auditor for a Python nutrition assistant.

SCOPE: Read and analyze ALL files in src/, skills/*/scripts/, and scripts/

DIMENSIONS (check each):
1. CORRECTNESS: Logic bugs, edge cases, race conditions, wrong calculations
2. SIMPLICITY: Over-engineering, unnecessary abstractions, dead code paths
3. EFFICIENCY: N+1 queries, redundant DB calls, blocking I/O in async, memory leaks
4. TYPES: Missing type hints, bare `dict` in agent tool params (must be precise like dict[str, int])

PROJECT-SPECIFIC CHECKS:
- src/agent.py must have exactly 6 tools (rule 6)
- Skill scripts must NOT reimplement logic from src/nutrition/ — they import it (rule 7)
- Magic numbers must come from src/nutrition/constants.py, not hardcoded inline (rule 7b)
- scripts/ must NOT import anthropic, openai, or any LLM client (rule 10)
- Safety constraints (MIN_CALORIES_WOMEN=1200, MIN_CALORIES_MEN=1500, ALLERGEN_ZERO_TOLERANCE=True) must never be bypassed (rule 3)
- Agent tool parameters must use precise types, not bare dict (rule 2)

LINTER OUTPUT (already collected):
{ruff_output}
{mypy_output}

Read every Python file in scope. For each finding, use the standardized format.
Return ONLY your findings, numbered sequentially. No preamble, no summary.
```

---

#### Agent B — Security & Data

**Scope**: `src/api.py`, `src/tools.py`, `src/db_utils.py`, `sql/`, auth flows, `.env` handling
**Focus**: Securite, input validation, RLS, secrets

**Prompt template**:

```
You are Agent B — Security & Data auditor for a Python/FastAPI nutrition assistant with Supabase backend.

SCOPE: Focus on src/api.py, src/tools.py, src/db_utils.py, sql/ migrations, and any auth-related code. Also scan all files for secrets/credentials.

DIMENSIONS (check each):
1. SECURITY: Injection (SQL, command, XSS), auth bypass, CORS misconfiguration, exposed secrets
2. INPUT VALIDATION: Missing Pydantic models on API endpoints, unsanitized user input, missing UUID validation
3. DATA INTEGRITY: Missing RLS policies, unprotected DB operations, race conditions on shared state
4. SECRETS: Hardcoded API keys, tokens in code, .env files committed, secrets in logs

PROJECT-SPECIFIC CHECKS:
- All user text must go through sanitize_user_text() (existing pattern)
- UUID validation on all user_id parameters
- RLS policies on all Supabase tables
- No secrets in code or logs (check for print/logging statements with sensitive data)
- API endpoints must validate JWT and extract user_id
- Safety constraints never bypassed by user input (rule 3)
- Rate limiting (Semaphore(5) pattern) in place for external API calls

LINTER OUTPUT:
{ruff_output}

Read every file in scope. For each finding, use the standardized format.
Return ONLY your findings, numbered sequentially. No preamble, no summary.
```

---

#### Agent C — Frontend & UX

**Scope**: `frontend/src/`
**Focus**: Types, hooks correctness, render efficiency, modularity

**Prompt template**:

```
You are Agent C — Frontend & UX auditor for a React 18 + TypeScript 5 + Vite application.

SCOPE: Read and analyze ALL files in frontend/src/

DIMENSIONS (check each):
1. TYPES: Any use of `any` type (rule 2 — zero tolerance), missing Zod validation, type mismatches with backend
2. CORRECTNESS: React hooks violations (deps arrays), stale closures, missing error boundaries, broken conditional rendering
3. EFFICIENCY: Unnecessary re-renders, missing React.memo/useMemo/useCallback where needed, large bundle imports
4. MODULARITY: God components (>200 lines), duplicated logic across components, prop drilling >3 levels

PROJECT-SPECIFIC CHECKS:
- No `any` type anywhere (rule 2 — strict)
- Zod validates all UI component props before rendering (generative UI pattern)
- database.types.ts must match actual Supabase schema
- No lovable-tagger (was removed from project)
- French localization consistent (no English strings in UI)

TSC OUTPUT:
{tsc_output}

IMPORTANT: For any finding that involves UI/design changes (layout, styling, visual), the suggested_fix MUST say: "Run /frontend-design first to design the solution before implementing" (per CLAUDE.md rule 13).

Read every file in scope. For each finding, use the standardized format.
Return ONLY your findings, numbered sequentially. No preamble, no summary.
```

---

#### Agent D — Architecture & Standards

**Scope**: Entire project, `tests/`, `evals/`, config files
**Focus**: Conformite CLAUDE.md, DRY, dead code, test quality, dependencies

**Prompt template**:

```
You are Agent D — Architecture & Standards auditor for a Python/React nutrition assistant.

SCOPE: Read project structure, tests/, evals/, config files (pyproject.toml, tsconfig, etc.), and cross-cut across all code.

DIMENSIONS (check each):
1. STANDARDS CONFORMITY: Check ALL 13 rules in CLAUDE.md — flag every violation
2. DRY: Duplicated logic across files, copy-pasted code blocks, redundant utilities
3. DEAD CODE: Unused imports, unreachable branches, commented-out code, unused files
4. TEST QUALITY: Missing tests for calculation functions (rule 8), tests/ vs evals/ separation (rule 11), eval files missing TEST_USER_PROFILE constant (rule 11)
5. DEPENDENCIES: Outdated packages, unused dependencies, missing from requirements

PROJECT-SPECIFIC CHECKS:
- src/prompt.py stays generic — no skill-specific logic (rule 12)
- tests/ = deterministic only, evals/ = real LLM (rule 11)
- Every eval file has TEST_USER_PROFILE constant with ALL required fields (rule 11)
- Skill scripts use async def execute(**kwargs) -> str pattern
- No backward-compatibility hacks (unused _vars, re-exports, "# removed" comments)
- Import style: always use src. prefix (e.g., from src.agent import agent)

ALL LINTER OUTPUTS:
{ruff_output}
{mypy_output}
{tsc_output}

Read broadly across the project. For each finding, use the standardized format.
Return ONLY your findings, numbered sequentially. No preamble, no summary.
```

---

### Phase 3: Consolidation

After ALL 4 agents complete, consolidate their findings:

1. **Merge**: Collect all findings from agents A, B, C, D into one list
2. **Dedup**: If 2 findings refer to the same file within <10 lines and same category, merge them (keep the more detailed one, note both agents found it)
3. **Cross-reference**: If one agent found a bug and another noted missing tests at the same location, create a compound finding with elevated severity
4. **Final severity** using this rubric:
   - **Critical** = security vulnerability, data loss, safety constraint bypass, crash in core flows
   - **High** = logic bugs, race conditions, type safety in agent tools, N+1 queries, `any` in TypeScript
   - **Medium** = DRY violations, complexity, test gaps, standards violations, non-critical error handling
   - **Low** = style, naming, micro-optimizations, doc gaps
5. **Sort**: Critical > High > Medium > Low, then by blast radius (number of files/users affected)

---

### Phase 4: Write Audit Report

Create directory if needed: `mkdir -p .claude/audits`

Write report to `.claude/audits/audit-{YYYY-MM-DD-HHmm}.md` with this structure:

```markdown
# Audit Report — {date}

## Executive Summary

- **Files analyzed**: X Python files, Y TypeScript files
- **Total findings**: N (C critical, H high, M medium, L low)
- **Top concern**: [one sentence describing the most impactful pattern]
- **Overall health**: [Good | Needs Attention | Requires Immediate Action]

## Issues by Category

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| Security | | | | | |
| Correctness | | | | | |
| Simplicity | | | | | |
| Modularity | | | | | |
| Efficiency | | | | | |
| Standards | | | | | |
| **Total** | | | | | |

## Cross-Cutting Patterns

### Pattern 1: [name]
[Description of systemic pattern seen across multiple files/agents]

### Pattern 2: [name]
...

### Pattern 3: [name]
...

## Detailed Findings

### Critical

[Each finding with full detail from the standardized format]

### High

[...]

### Medium

[...]

### Low

[...]

## Recommendations

### Immediate (before deploy)
- [Critical + High fixes that block deployment]

### Short-term (first sprint post-deploy)
- [Medium fixes that improve quality]

### Long-term (backlog)
- [Low items and architectural improvements]
```

---

### Phase 5: Generate Fix Plan

Write `.agents/plans/project-audit-fixes.md` in `/execute`-compatible format:

```markdown
# Plan: Project Audit Fixes

## Context
Auto-generated from audit report .claude/audits/audit-{timestamp}.md

## Phase 1 — Critical Fixes
### Task 1.1: [title from finding]
- ACTION: Edit `{file}`
- IMPLEMENT: {suggested_fix from finding}
- VALIDATE: {appropriate test command}

### Task 1.2: ...

## Phase 2 — High-Priority Fixes
### Task 2.1: ...
[same format]

## Phase 3 — Medium-Priority Fixes
### Task 3.1: ...
[same format]

## NOTES — Low-Priority (no tasks, just awareness)
- [Low findings listed as bullet points for reference]
```

**Special rules for the fix plan:**
- Each task must be atomic (one file, one fix)
- Frontend UI/design tasks MUST include: `PREREQUISITE: Run /frontend-design to design the solution first`
- VALIDATE should reference specific test commands or manual checks
- Low-severity items go in NOTES only, not as tasks

---

### Phase 6: Summary to User

After writing both files, present to the user:

1. The executive summary (from the report)
2. The issues-by-category table
3. The top 3 cross-cutting patterns
4. Path to the full report and fix plan
5. Instruction: "Run `/execute .agents/plans/project-audit-fixes.md` to start fixing issues"
