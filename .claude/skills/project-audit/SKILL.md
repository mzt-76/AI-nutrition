---
name: project-audit
description: >
  Audit complet du codebase avant deploiement. Analyse tout le code sur 6 dimensions
  (simplicite, modularite, efficacite, securite, correctitude, conformite aux standards)
  via une equipe de 4 agents coordonnes (Agent Teams) qui se cross-review mutuellement.
  Produit un rapport detaille et un plan de fixes compatible /execute.
  Triggers: "audit", "code review complet", "pre-deployment review", "check code quality",
  "find all issues", "audit complet", "revue de code", "analyse du projet"
---

# Project Audit — Agent Teams Edition

Audit exhaustif via 4 teammates specialises qui communiquent entre eux, cross-review leurs findings, et produisent un rapport consolide dans `.claude/audits/`.

**Prerequisite**: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings.

---

## Phase 1: Context Gathering

Gather project context before creating the team:

1. **Read project rules**: Read `CLAUDE.md` (the 13 rules are the audit checklist)
2. **Read constants**: Read `src/nutrition/constants.py` for magic number references
3. **Project stats**: `find src/ -name '*.py' | xargs wc -l` + `find frontend/src -name '*.ts' -o -name '*.tsx' | xargs wc -l`
4. **Pre-flight linters** (parallel, do NOT fix — just collect):
   - `ruff check src/ scripts/ skills/ 2>&1 | tail -30`
   - `mypy src/ 2>&1 | tail -30`
   - `cd frontend && npx tsc --noEmit 2>&1 | tail -30`
5. **Create working directory**: `mkdir -p .claude/audits/wip`

Save all outputs — they feed into teammate prompts.

---

## Phase 2: Create Team & Assign Scan Tasks

Create an agent team with 4 specialized teammates. Each teammate scans its scope and writes findings to a shared file.

**Team creation prompt** (adapt with Phase 1 context):

```
Create an agent team called "audit" with 4 teammates:

1. "backend" — Backend & Logic auditor
   Scope: src/, skills/*/scripts/, scripts/
   [Insert prompt from references/agent-prompts.md, filled with linter outputs]

2. "security" — Security & Data auditor
   Scope: src/api.py, src/tools.py, src/db_utils.py, sql/, auth
   [Insert prompt from references/agent-prompts.md, filled with linter outputs]

3. "frontend" — Frontend & UX auditor
   Scope: frontend/src/
   [Insert prompt from references/agent-prompts.md, filled with linter outputs]

4. "standards" — Architecture & Standards auditor
   Scope: tests/, evals/, config files, cross-cutting
   [Insert prompt from references/agent-prompts.md, filled with linter outputs]

Each teammate writes findings to .claude/audits/wip/{name}-findings.md then messages me when done.
```

Read `references/agent-prompts.md` for the full prompt templates with dimensions, project rules, and finding format.

**Review methodology reference**: Each teammate should read `.claude/commands/validation/code-review-claude-code.md` for the shared review methodology — 8 analysis dimensions (logic, security, performance, quality, tests, breaking changes, standards, AI-specific patterns), severity rubric, and verification requirements. This ensures all teammates use the same quality bar and verification standards.

**Wait for all 4 teammates to report scan complete before proceeding.**

---

## Phase 3: Cross-Review

This is the key advantage over isolated subagents. Each teammate reads 2 other teammates' findings and validates them.

**Review assignments** (minimize overlap, maximize cross-domain insight):

| Reviewer | Reviews findings from |
|----------|----------------------|
| backend | security, standards |
| security | backend, frontend |
| frontend | standards, security |
| standards | backend, frontend |

**Message each teammate** with the cross-review prompt from `references/agent-prompts.md`. Each writes their review to `.claude/audits/wip/{name}-review.md`.

The cross-review catches:
- **Duplicates**: Same issue found by 2 agents → merge, note both found it
- **Compounds**: Bug + missing test at same location → elevate severity
- **Disagreements**: One agent says correct, another says bug → investigate
- **Blind spots**: Security implications of logic bugs, type issues enabling injection

**Wait for all 4 reviews before proceeding.**

---

## Phase 4: Consolidation (Lead)

Read ALL 8 files from `.claude/audits/wip/` (4 findings + 4 reviews). Consolidate:

1. **Merge** all findings into one list
2. **Apply cross-review verdicts**:
   - `agree` → keep finding, note cross-validated (higher confidence)
   - `disagree` → investigate, keep only if evidence supports it
   - `duplicate-of-mine-N` → merge into single finding, note both agents
   - `compounds-with-mine-N` → create compound finding, elevate severity
3. **Re-score severity** using rubric from `references/templates.md`
4. **Sort**: Critical > High > Medium > Low, then by blast radius

---

## Phase 5: Write Report

Read `references/templates.md` for the full report template.

Write to `.claude/audits/audit-{YYYY-MM-DD-HHmm}.md`. Include:
- Executive summary with stats and overall health assessment
- Issues-by-category matrix table
- Top 3 cross-cutting patterns (systemic issues across files/agents)
- All detailed findings sorted by severity
- Recommendations (immediate / short-term / long-term)

---

## Phase 6: Generate Fix Plan

Write `.agents/plans/project-audit-fixes.md` using template from `references/templates.md`.

Rules:
- Each task = one file, one atomic fix
- Frontend UI tasks include: `PREREQUISITE: Run /frontend-design first`
- VALIDATE = specific test command
- Low-severity → NOTES section only

---

## Phase 7: Cleanup & Summary

1. **Clean up team**: `Clean up the team` (removes shared resources)
2. **Remove wip files**: `rm -rf .claude/audits/wip/`
3. **Present to user**:
   - Executive summary
   - Issues-by-category table
   - Top 3 cross-cutting patterns
   - Path to full report and fix plan
   - Instruction: "Run `/execute .agents/plans/project-audit-fixes.md` to start fixing"
