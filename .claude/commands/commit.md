---
description: Create an atomic commit for current changes
---

# Commit Changes

## Process

### 1. Review Changes

```bash
git status
git diff HEAD
git diff --stat HEAD
git ls-files --others --exclude-standard
```

### 2. Stage Files

Add the untracked and changed files relevant to the current work.

**Do NOT stage:** `.env`, credential files, large binaries, files unrelated to the current task.

### 3. Create Commit

Write an atomic commit with a conventional tag:

- `feat:` — New capability or feature
- `fix:` — Bug fix
- `refactor:` — Code restructure without behavior change
- `docs:` — Documentation only
- `test:` — Test additions or fixes
- `chore:` — Build, CI, tooling changes
- `perf:` — Performance improvement

**Message format:**
```
tag(scope): concise description of what changed

[Optional body: WHY this change was made, not just what.
Include context not obvious from the diff.]

[Optional: Fixes #123, Closes #456]
```

### 4. Capture AI Context Changes

If any AI context assets were modified, add a `Context:` section to the commit body:

```
feat(skills): add remove_favorite_recipe script

Users can now remove favorites via chat instead of manual DB edits.
Fuzzy matching handles ambiguous recipe names.

Context:
- Updated skills/meal-planning/SKILL.md with new triggers
- Added .claude/rules/skills.md for path-scoped skill conventions
```

**What counts as AI context changes:**
- `.claude/rules/` — path-scoped conventions added/updated/removed
- `.claude/commands/` — slash commands created/modified
- `.claude/reference/` — reference docs added/updated
- `CLAUDE.md` — global rules changes
- `skills/*/SKILL.md` — skill metadata/routing changes

**Why this matters:** `git log` is long-term memory. Future agents use it to understand project history. If context changes aren't in commits, the AI layer's evolution becomes invisible.
