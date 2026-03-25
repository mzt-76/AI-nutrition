---
description: Write a session handoff document for the next agent or session
---

# Handoff: Capture Session State for Continuation

## Objective

Create a structured handoff document that lets the next session (or agent) seamlessly continue this work. Externalize the session's memory into a persistent file AND compress it to essentials only.

## Process

### 1. Analyze the Current Session

Review everything that happened in this conversation:
- What was the original goal or task?
- What has been completed so far?
- What is still in progress or blocked?
- What key decisions were made and WHY?
- What files were read, created, or modified?
- What dead ends were explored (so the next session doesn't repeat them)?

### 2. Gather Current State

```bash
git status
git diff --stat HEAD
git log --oneline -5
git branch --show-current
```

### 3. Write the Handoff Document

Save to: `HANDOFF.md` in the project root.

**Use this exact structure:**

```markdown
# Handoff: [Brief Task Description]

**Date:** [current date]
**Branch:** [current branch name]
**Last Commit:** [hash + message, or "uncommitted changes"]

## Goal

[1-2 sentences: what we're trying to accomplish. Include the original user request or plan reference.]

## Completed

- [x] [Task 1 — brief description of what was done]
- [x] [Task 2 — brief description]

## In Progress / Next Steps

- [ ] [Task 3 — what needs to happen next, with file paths and specific areas]
- [ ] [Task 4 — any blocked items with explanation of the blocker]

## Key Decisions

Document WHY choices were made, not just what was chosen:

- **[Decision]**: [What was chosen] — [Why, including alternatives rejected]

## Dead Ends (Don't Repeat These)

- [Approach tried and didn't work] — [Why it failed]

## Files Changed

- `path/to/file.ts` — [what changed and why, 1 line]
- `path/to/new-file.ts` — [NEW: what this file does]

## Current State

- **Tests:** [passing/failing — which ones and why]
- **Lint:** [clean/N warnings]
- **Build:** [working/broken]

## Context for Next Session

[2-4 sentences: the MOST IMPORTANT thing the next agent needs to know. What's the current situation? What's the biggest risk? What should they do first?]

**Recommended first action:** [Exact command or step to take first]
```

### 4. Confirm and Advise

After writing the handoff:
1. Confirm the file was written with its full path
2. If there are uncommitted changes, suggest `/commit` first
3. Suggest the next session starts with: `Read HANDOFF.md and continue from where the previous session left off.`

## Quality Criteria

- Lets a fresh agent continue **without asking clarifying questions**
- Under **100 lines** (link to files rather than duplicating content)
- Includes enough "why" context for consistent decision-making
- Explicitly lists dead ends to prevent wasted re-exploration
- Has a concrete "first action" recommendation
