---
paths:
  - "frontend/src/**"
  - "frontend/*.ts"
  - "frontend/*.json"
---

# Frontend Conventions

## Stack & Setup

React 18 + TypeScript 5 + Vite 5 + shadcn/ui + Tailwind
Run: `cd frontend && npm run dev` (port 8080), needs `frontend/.env` with Supabase keys

## Design System

- **Theme**: green glass-morphism dark theme
- **Localization**: French (all UI text in French)
- **Do not use lovable-tagger** — it was removed from the project

## Auth Flow

Supabase Auth (email/password + Google OAuth) → JWT session → `user.id` sent to backend

## Streaming & API

- `POST /api/agent` with NDJSON response, parsed in `src/lib/api.ts`
- Conversations loaded from Supabase `conversations`/`messages` tables via JS client

## Generative UI

Agent emits `<!--UI:Component:{json}-->` markers in text → `src/ui_components.py` extracts them → API streams as `ui_component` NDJSON chunks → frontend renders via `ComponentRenderer`. Zod validates all props.

7 components: `NutritionSummaryCard`, `MacroGauges`, `MealCard`, `DayPlanCard`, `WeightTrendIndicator`, `AdjustmentCard`, `QuickReplyChips`

## Known Bugs / Workarounds

- **Radix ScrollArea `display: table` bug**: Viewport wraps children in `<div style="display: table">` which clips content. Fix in `scroll-area.tsx`: `[&>div]:!block` forces `display: block`.
- **Sidebar icon visibility**: `text-muted-foreground` is invisible on dark glass background. Use `text-white/40` with `hover:text-red-400` (or other color). Keep icons always visible — no `opacity-0 group-hover:opacity-100`.

## Workflow

For any frontend task: (1) use `/frontend-design` skill to design the UI, (2) implement it, (3) test with `agent-browser` on desktop (`1280x720`) and mobile (`390x844`). Screenshot and verify before marking complete.

Full checklist: `.claude/reference/frontend-workflow.md`

## Anti-patterns

- Never use `any` in TypeScript — strict mode enforced
- Never skip mobile viewport testing
- Never add English text — everything is French-localized
- Never use lovable-tagger
