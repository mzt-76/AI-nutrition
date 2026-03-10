# Audit Report & Fix Plan Templates

## Audit Report Template

Write to `.claude/audits/audit-{YYYY-MM-DD-HHmm}.md`:

```markdown
# Audit Report — {date}

## Executive Summary

- **Files analyzed**: X Python files, Y TypeScript files
- **Total findings**: N (C critical, H high, M medium, L low)
- **Top concern**: [one sentence]
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
[Systemic pattern seen across multiple files/agents]

### Pattern 2: [name]
...

## Detailed Findings

### Critical
[Full findings]

### High
[...]

### Medium
[...]

### Low
[...]

## Recommendations

### Immediate (before deploy)
- [Critical + High fixes]

### Short-term (first sprint)
- [Medium fixes]

### Long-term (backlog)
- [Low items]
```

---

## Fix Plan Template

Write to `.agents/plans/project-audit-fixes.md`:

```markdown
# Plan: Project Audit Fixes

## Context
Auto-generated from audit report .claude/audits/audit-{timestamp}.md

## Phase 1 — Critical Fixes
### Task 1.1: [title]
- ACTION: Edit `{file}`
- IMPLEMENT: {suggested_fix}
- VALIDATE: {test command}

## Phase 2 — High-Priority Fixes
### Task 2.1: [title]
[same format]

## Phase 3 — Medium-Priority Fixes
### Task 3.1: [title]
[same format]

## NOTES — Low-Priority (awareness only)
- [Low findings as bullet points]
```

**Fix plan rules:**
- Each task = one file, one fix (atomic)
- Frontend UI tasks: `PREREQUISITE: Run /frontend-design first`
- VALIDATE = specific test command or manual check
- Low-severity → NOTES only, not tasks

---

## Severity Rubric

- **Critical** = security vulnerability, data loss, safety constraint bypass, crash in core flows
- **High** = logic bugs, race conditions, type safety in agent tools, N+1 queries, `any` in TypeScript
- **Medium** = DRY violations, complexity, test gaps, standards violations, non-critical error handling
- **Low** = style, naming, micro-optimizations, doc gaps
