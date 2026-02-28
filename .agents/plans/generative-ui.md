# Feature: Generative UI for AI Nutrition Assistant

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Replace plain markdown text responses with **rich, interactive React components** rendered alongside text. The agent decides WHAT to show (component selection via structured JSON markers in text), and the frontend decides HOW to render it (component catalog + zone-based layout).

This extends the existing NDJSON streaming pipeline with a new `ui_component` chunk type. Zero new dependencies. Domain-specific nutrition components (MacroGauges, MealCard, etc.) instead of generic UI.

## User Story

As a nutrition app user
I want to see rich visual components (gauges, cards, charts) alongside text responses
So that I can quickly understand my macro breakdown, meal plans, and weekly coaching results at a glance

## Problem Statement

All agent responses render as walls of markdown text. Structured data (macro breakdowns, meal plans, weekly coaching results) loses visual impact and interactivity. Users must parse long text to find key numbers.

## Solution Statement

Extend the NDJSON streaming protocol with `<!--UI:ComponentName:{json}-->` markers that the backend extracts and emits as separate `ui_component` chunks. The frontend accumulates these and renders them via a component catalog mapped by semantic zones.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `src/api.py` (streaming), `src/prompt.py` (agent instructions), `src/db_utils.py` (storage), frontend chat components, frontend types
**Dependencies**: None new — uses existing NDJSON pipeline, React, Tailwind CSS classes

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

**Backend:**
- `src/api.py` (lines 321-397) — `_stream_agent_response()`: the NDJSON streaming loop. Yields `{"text": full_response}` chunks. Final chunk has `{"complete": true, "session_id": ..., "text": ...}`. Extension point: after line 358 (streaming loop ends), before line 362 (store_message).
- `src/api.py` (lines 362-370) — Where AI message is stored. `data={"request_id": request.request_id}` passed to `store_message()`.
- `src/api.py` (lines 389-397) — Final chunk construction. `final_data` dict gets conditional fields.
- `src/db_utils.py` (lines 148-178) — `store_message()` function. Message JSONB: `{"type": "human"|"ai", "content": str, "data"?: dict, "files"?: list}`. JSONB accepts arbitrary keys — no migration needed.
- `src/prompt.py` (lines 8-112) — `AGENT_SYSTEM_PROMPT` constant. French language. Sections: personality, capabilities, safety constraints, profile workflow, progressive disclosure, communication style, memory, limits.
- `src/agent.py` (lines 358-364) — Agent definition. 6 fixed tools. Never add tools here.

**Frontend:**
- `frontend/src/lib/api.ts` (lines 15-23) — `StreamingChunk` interface: `{text?, title?, session_id?, done?, complete?, conversation_title?, error?}`. Parsing at lines 112-169 in `sendMessage()`.
- `frontend/src/lib/api.ts` (lines 25-32) — `sendMessage()` signature with `onStreamChunk` callback.
- `frontend/src/components/chat/MessageHandling.tsx` (lines 72-173) — Streaming callback. Creates AI message at lines 86-99, updates at lines 101-118. **Insertion point**: handle `ui_component` chunks alongside text.
- `frontend/src/components/chat/MessageItem.tsx` (lines 75-111) — `memoizedMarkdown` with ReactMarkdown. **Insertion point**: after line 162 (after `{memoizedMarkdown}`), render `<ComponentRenderer>`.
- `frontend/src/components/chat/MessageItem.tsx` (lines 139-164) — Message bubble container. AI messages use `glass-effect text-foreground`.
- `frontend/src/types/database.types.ts` (lines 40-74) — Message type: `message: {type, content, files?}`. **Extend**: add `ui_components?` field.
- `frontend/src/components/chat/ChatLayout.tsx` (lines 13-25) — Props include `onSendMessage`. Flow: `Chat.tsx → ChatLayout → MessageList → MessageItem`.
- `frontend/src/index.css` (lines 97-109) — `.glass-effect` and `.gradient-green` CSS classes.

**Reference patterns (read-only):**
- `generative_UI_project_example/` — Contains `a2ui-catalog.tsx` (catalog pattern: `Record<string, ComponentRenderer>`), `A2UIRenderer.tsx` (recursive render + error handling), `layout-engine.ts` (width-to-grid mapping, semantic zones). Key interface: `A2UIComponent { id, type, props, children?, layout?, styling?, zone? }`.

### New Files to Create

- `src/ui_components.py` — Backend marker extraction
- `frontend/src/types/generative-ui.types.ts` — TypeScript types for UI components
- `frontend/src/components/generative-ui/ComponentRenderer.tsx` — Catalog + zone renderer
- `frontend/src/components/generative-ui/components/NutritionSummaryCard.tsx`
- `frontend/src/components/generative-ui/components/MacroGauges.tsx`
- `frontend/src/components/generative-ui/components/MealCard.tsx`
- `frontend/src/components/generative-ui/components/DayPlanCard.tsx`
- `frontend/src/components/generative-ui/components/WeightTrendIndicator.tsx`
- `frontend/src/components/generative-ui/components/AdjustmentCard.tsx`
- `frontend/src/components/generative-ui/components/QuickReplyChips.tsx`
- `tests/test_ui_components.py` — Backend unit tests

### Patterns to Follow

**NDJSON Chunk Pattern** (from `src/api.py`):
```python
yield json.dumps({"text": full_response}).encode("utf-8") + b"\n"
```
New UI chunks follow same pattern:
```python
yield json.dumps({"type": "ui_component", "component": name, "props": {...}, "zone": zone, "id": id}).encode("utf-8") + b"\n"
```

**Message JSONB Extension** (from `src/db_utils.py`):
```python
message_obj["ui_components"] = ui_components  # list[dict] — JSONB accepts this
```

**Frontend Streaming Callback Pattern** (from `MessageHandling.tsx`):
```typescript
if (chunk.text) { /* update message content */ }
// NEW:
if (chunk.type === 'ui_component') { /* push to accumulated components */ }
```

**CSS Theme Classes**: `glass-effect` (dark glass background), `gradient-green` (green gradient), `bg-chat-user` (user message bg). All AI components should use `glass-effect` with green accents.

**Component Catalog Pattern** (from reference `a2ui-catalog.tsx`):
```typescript
const COMPONENT_CATALOG: Record<string, React.FC<any>> = {
  NutritionSummaryCard,
  MacroGauges,
  // ...
};
```

---

## IMPLEMENTATION PLAN

### Phase 1: Backend Foundation (src/ui_components.py + tests)

Create the marker extraction module and comprehensive tests. This is the core backend logic — everything else depends on it.

### Phase 2: Backend Integration (api.py, db_utils.py, prompt.py)

Wire extraction into the streaming pipeline. Extend message storage. Teach the agent about UI components in the system prompt.

### Phase 3: Frontend Types & Stream Parser

Define TypeScript types, extend the streaming chunk interface, update the NDJSON parser and message accumulation hook.

### Phase 4: Frontend Component Catalog & 7 Components

Build the ComponentRenderer and all 7 Phase 1 components with green glass-morphism styling.

### Phase 5: Integration & QuickReplyChips Wiring

Wire ComponentRenderer into MessageItem, pass onAction callback through the component tree for QuickReplyChips interaction.

### Phase 6: Testing & Validation

Backend unit tests, frontend lint/type-check, manual integration test.

---

## STEP-BY-STEP TASKS

### Task 1: CREATE `src/ui_components.py`

**IMPLEMENT**: Module with two functions:

```python
import json
import re
import logging

logger = logging.getLogger(__name__)

UI_MARKER_PATTERN = re.compile(r'<!--UI:(\w+):(\{.*?\})-->', re.DOTALL)

ZONE_MAP: dict[str, str] = {
    "NutritionSummaryCard": "hero",
    "MacroGauges": "macros",
    "MealCard": "meals",
    "DayPlanCard": "meals",
    "WeightTrendIndicator": "progress",
    "AdjustmentCard": "progress",
    "QuickReplyChips": "actions",
}

def _infer_zone(component_name: str) -> str:
    return ZONE_MAP.get(component_name, "content")

def extract_ui_components(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Extract <!--UI:ComponentName:{json}--> markers from text.
    Returns (cleaned_text, components_list).
    """
    components: list[dict[str, Any]] = []
    counter: dict[str, int] = {}

    for match in UI_MARKER_PATTERN.finditer(text):
        component_name = match.group(1)
        json_str = match.group(2)
        try:
            props = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning(f"Malformed JSON in UI marker for {component_name}, skipping")
            continue

        count = counter.get(component_name, 0)
        counter[component_name] = count + 1
        component_id = f"{component_name.lower()}-{count}"

        components.append({
            "id": component_id,
            "component": component_name,
            "props": props,
            "zone": _infer_zone(component_name),
        })

    cleaned = UI_MARKER_PATTERN.sub("", text).strip()
    return cleaned, components
```

- **IMPORTS**: `re`, `json`, `logging`, `typing.Any`
- **GOTCHA**: Regex must use `re.DOTALL` for multiline JSON. Use non-greedy `.*?` to avoid matching across multiple markers.
- **VALIDATE**: `pytest tests/test_ui_components.py -v`

### Task 2: CREATE `tests/test_ui_components.py`

**IMPLEMENT**: Comprehensive tests for `extract_ui_components`:

```python
# Test cases:
# 1. Single valid marker → extracts component, strips from text
# 2. Multiple markers → extracts all, correct IDs (component-0, component-1)
# 3. No markers → returns original text, empty list
# 4. Malformed JSON → skips bad marker, keeps good ones
# 5. Zone inference → each component maps to correct zone
# 6. Unknown component → zone defaults to "content"
# 7. Unique ID generation → counter increments per component type
# 8. Empty text → returns empty string, empty list
# 9. Markers with multiline JSON → handles correctly
# 10. Mixed text and markers → text preserved, markers stripped
```

- **PATTERN**: Follow `tests/test_nutrition_calculator.py` structure
- **VALIDATE**: `pytest tests/test_ui_components.py -v`

### Task 3: UPDATE `src/api.py` — Extend `_stream_agent_response()`

**IMPLEMENT**: After streaming loop completes (after line ~358), before storing message (line ~362):

1. Import `extract_ui_components` from `src.ui_components`
2. After `full_response` is fully accumulated, call `extract_ui_components(full_response)`
3. Yield one `{"type": "ui_component", ...}` chunk per extracted component
4. Use `cleaned_text` (without markers) for storage and final chunk
5. Include `ui_components` list in `final_data` dict

```python
# After streaming loop, before store_message:
from src.ui_components import extract_ui_components

cleaned_text, ui_components = extract_ui_components(full_response)
if ui_components:
    full_response = cleaned_text  # Use cleaned text for storage
    for comp in ui_components:
        yield json.dumps({"type": "ui_component", **comp}).encode("utf-8") + b"\n"

# In final_data dict:
if ui_components:
    final_data["ui_components"] = ui_components
```

- **GOTCHA**: `full_response` variable must be reassigned to `cleaned_text` BEFORE `store_message` call. Don't break the existing `full_response` accumulation during streaming.
- **VALIDATE**: Manual test with curl or frontend

### Task 4: UPDATE `src/db_utils.py` — Store ui_components

**IMPLEMENT**: In `store_message()`, add `ui_components` parameter:

```python
async def store_message(
    supabase: Client,
    session_id: str,
    message_type: str,
    content: str,
    message_data: bytes | None = None,
    data: dict[str, Any] | None = None,
    files: list[dict[str, str]] | None = None,
    ui_components: list[dict[str, Any]] | None = None,  # NEW
) -> None:
```

Add to message_obj:
```python
if ui_components:
    message_obj["ui_components"] = ui_components
```

Then update the `store_message` call in `src/api.py` to pass `ui_components=ui_components`.

- **GOTCHA**: No DB migration needed — JSONB column accepts arbitrary keys.
- **VALIDATE**: Check stored messages in Supabase dashboard after a test message.

### Task 5: UPDATE `src/prompt.py` — Add UI component instructions

**IMPLEMENT**: Add a new section to `AGENT_SYSTEM_PROMPT` after the communication style section (around line 100). In French:

```python
# Section: Composants UI Visuels
# Teach the agent:
# - Available components: NutritionSummaryCard, MacroGauges, MealCard, DayPlanCard, WeightTrendIndicator, AdjustmentCard, QuickReplyChips
# - Marker syntax: <!--UI:ComponentName:{"prop": "value"}-->
# - Rules:
#   1. ALWAYS write text explanation FIRST, then emit markers AFTER
#   2. Props must contain real data from skill calculations (never fabricate)
#   3. Don't emit components when you don't have the data
#   4. Text is always present — components are visual complements
#   5. QuickReplyChips: use for follow-up suggestions
# - Props schemas for each component (brief)
```

- **PATTERN**: Match existing prompt style — concise, numbered rules, French
- **GOTCHA**: Keep the prompt addition compact (~30-40 lines). Don't bloat the system prompt.
- **VALIDATE**: `ruff check src/prompt.py && mypy src/prompt.py`

### Task 6: CREATE `frontend/src/types/generative-ui.types.ts`

**IMPLEMENT**:

```typescript
export type SemanticZone = 'hero' | 'macros' | 'meals' | 'progress' | 'actions' | 'content';

export interface UIComponentBlock {
  id: string;
  component: string;
  props: Record<string, unknown>;
  zone: SemanticZone;
}

// Props interfaces for each component
export interface NutritionSummaryCardProps {
  bmr: number;
  tdee: number;
  target_calories: number;
  primary_goal: string;
  rationale?: string;
}

export interface MacroGaugesProps {
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  target_calories: number;
}

export interface MealCardProps {
  meal_type: string;
  recipe_name: string;
  calories: number;
  macros: { protein_g: number; carbs_g: number; fat_g: number };
  prep_time?: number;
  ingredients?: string[];
}

export interface DayPlanCardProps {
  day_name: string;
  meals: MealCardProps[];
  totals: { calories: number; protein_g: number; carbs_g: number; fat_g: number };
}

export interface WeightTrendIndicatorProps {
  weight_start: number;
  weight_end: number;
  trend: 'up' | 'down' | 'stable';
  rate: number;
}

export interface AdjustmentCardProps {
  calorie_adjustment: number;
  new_target: number;
  reason: string;
  red_flags?: string[];
}

export interface QuickReplyChipsProps {
  options: Array<{ label: string; value: string }>;
}
```

- **VALIDATE**: `cd frontend && npx tsc --noEmit`

### Task 7: UPDATE `frontend/src/types/database.types.ts`

**IMPLEMENT**: Add `ui_components` to message type (around line 45-49):

```typescript
message: {
  type: 'human' | 'ai';
  content: string;
  files?: FileAttachment[];
  ui_components?: Array<{
    id: string;
    component: string;
    props: Record<string, unknown>;
    zone: string;
  }>;
};
```

- **IMPORTS**: No new imports needed (inline type)
- **VALIDATE**: `cd frontend && npx tsc --noEmit`

### Task 8: UPDATE `frontend/src/lib/api.ts` — Parse ui_component chunks

**IMPLEMENT**: Extend `StreamingChunk` interface (line 15-23):

```typescript
interface StreamingChunk {
  text?: string;
  type?: string;         // NEW: 'ui_component' for component chunks
  component?: string;    // NEW
  props?: Record<string, unknown>;  // NEW
  zone?: string;         // NEW
  id?: string;           // NEW (component id)
  // ... existing fields
}
```

In the NDJSON parsing loop (lines 112-169), the callback already receives the full parsed chunk object. No change to parsing logic needed — the `onStreamChunk` callback already passes `chunk` as-is. The handling happens in `MessageHandling.tsx`.

- **GOTCHA**: Backward compatible — if no `type` field, treated as text chunk (existing behavior).
- **VALIDATE**: `cd frontend && npx tsc --noEmit`

### Task 9: UPDATE `frontend/src/components/chat/MessageHandling.tsx` — Accumulate components

**IMPLEMENT**: In the streaming callback (lines 72-173):

1. Add `accumulatedComponents` array outside the callback:
```typescript
const accumulatedComponents: UIComponentBlock[] = [];
```

2. Inside the callback, handle ui_component chunks:
```typescript
// After text handling, before completion handling:
if (chunk.type === 'ui_component' && chunk.component) {
  accumulatedComponents.push({
    id: chunk.id || `${chunk.component}-${accumulatedComponents.length}`,
    component: chunk.component,
    props: chunk.props || {},
    zone: (chunk.zone as SemanticZone) || 'content',
  });
  // Update the AI message's ui_components
  setMessages((prev) => {
    const updated = [...prev];
    const idx = updated.findIndex(msg => msg.id === aiMessageId);
    if (idx !== -1) {
      updated[idx] = {
        ...updated[idx],
        message: {
          ...updated[idx].message,
          ui_components: [...accumulatedComponents],
        },
      };
    }
    return updated;
  });
}
```

- **IMPORTS**: `import { UIComponentBlock, SemanticZone } from '@/types/generative-ui.types';`
- **VALIDATE**: `cd frontend && npx tsc --noEmit`

### Task 10: CREATE `frontend/src/components/generative-ui/ComponentRenderer.tsx`

**IMPLEMENT**: Component catalog + zone-based renderer.

```typescript
import React from 'react';
import { UIComponentBlock, SemanticZone } from '@/types/generative-ui.types';
import { NutritionSummaryCard } from './components/NutritionSummaryCard';
import { MacroGauges } from './components/MacroGauges';
import { MealCard } from './components/MealCard';
import { DayPlanCard } from './components/DayPlanCard';
import { WeightTrendIndicator } from './components/WeightTrendIndicator';
import { AdjustmentCard } from './components/AdjustmentCard';
import { QuickReplyChips } from './components/QuickReplyChips';

const COMPONENT_CATALOG: Record<string, React.FC<any>> = {
  NutritionSummaryCard,
  MacroGauges,
  MealCard,
  DayPlanCard,
  WeightTrendIndicator,
  AdjustmentCard,
  QuickReplyChips,
};

const ZONE_ORDER: SemanticZone[] = ['hero', 'macros', 'meals', 'progress', 'content', 'actions'];

function getZoneClassName(zone: SemanticZone): string {
  switch (zone) {
    case 'hero': return 'col-span-full';
    case 'macros': return 'col-span-full';
    case 'meals': return 'col-span-full md:col-span-6';
    case 'progress': return 'col-span-full md:col-span-6';
    case 'actions': return 'col-span-full';
    case 'content': return 'col-span-full';
    default: return 'col-span-full';
  }
}

interface ComponentRendererProps {
  components: UIComponentBlock[];
  onAction?: (value: string) => void;
}

export function ComponentRenderer({ components, onAction }: ComponentRendererProps) {
  // Group by zone
  const grouped = new Map<SemanticZone, UIComponentBlock[]>();
  for (const comp of components) {
    const zone = comp.zone as SemanticZone;
    if (!grouped.has(zone)) grouped.set(zone, []);
    grouped.get(zone)!.push(comp);
  }

  return (
    <div className="grid grid-cols-12 gap-3 mt-4">
      {ZONE_ORDER.map(zone => {
        const zoneComponents = grouped.get(zone);
        if (!zoneComponents?.length) return null;
        return zoneComponents.map(comp => {
          const Component = COMPONENT_CATALOG[comp.component];
          if (!Component) {
            console.warn(`Unknown UI component: ${comp.component}`);
            return null;
          }
          return (
            <div key={comp.id} className={getZoneClassName(zone)}>
              <Component {...comp.props} onAction={onAction} />
            </div>
          );
        });
      })}
    </div>
  );
}
```

- **PATTERN**: Mirrors `a2ui-catalog.tsx` catalog pattern from reference project
- **VALIDATE**: `cd frontend && npx tsc --noEmit`

### Task 11: CREATE 7 frontend components

**IMPLEMENT**: All in `frontend/src/components/generative-ui/components/`. All use green glass-morphism dark theme (`glass-effect`, green accents via `text-emerald-400`, `border-emerald-500/30`).

Each component is a simple presentational React FC. Key design:
- **NutritionSummaryCard**: Hero card showing BMR, TDEE, target calories, goal badge, rationale text
- **MacroGauges**: Three circular/bar gauges for protein/carbs/fat with gram values and percentages
- **MealCard**: Single meal with recipe name, calories, macros mini-bar, prep time, ingredient list
- **DayPlanCard**: Day header + list of MealCards + daily totals row
- **WeightTrendIndicator**: Arrow up/down/stable with start→end weight, rate badge
- **AdjustmentCard**: Calorie adjustment delta (+/-), new target, reason text, red flags list
- **QuickReplyChips**: Row of clickable chip buttons, calls `onAction(value)` on click

Style patterns:
```tsx
// Glass card wrapper (reuse across all components)
<div className="glass-effect rounded-lg border border-emerald-500/20 p-4">
  ...
</div>

// Green accent text
<span className="text-emerald-400 font-semibold">1850 kcal</span>

// Stat label
<span className="text-sm text-gray-400">BMR</span>
```

- **VALIDATE**: `cd frontend && npx tsc --noEmit && npm run lint`

### Task 12: UPDATE `frontend/src/components/chat/MessageItem.tsx` — Render ComponentRenderer

**IMPLEMENT**: After the `{memoizedMarkdown}` div (around line 162), add:

```tsx
import { ComponentRenderer } from '@/components/generative-ui/ComponentRenderer';

// Inside the message bubble, after the prose div:
{message.message.type === 'ai' && message.message.ui_components && message.message.ui_components.length > 0 && (
  <ComponentRenderer
    components={message.message.ui_components}
    onAction={onAction}
  />
)}
```

Add `onAction` prop to `MessageItemProps`:
```typescript
interface MessageItemProps {
  message: Message;
  isLastMessage?: boolean;
  onAction?: (value: string) => void;  // NEW
}
```

- **GOTCHA**: `onAction` must be threaded from `ChatLayout` → `MessageList` → `MessageItem`.
- **VALIDATE**: `cd frontend && npx tsc --noEmit`

### Task 13: Wire QuickReplyChips onAction through component tree

**IMPLEMENT**: Thread `onAction` callback:

1. **MessageList.tsx**: Add `onAction` prop, pass to each `MessageItem`
2. **ChatLayout.tsx**: Pass `onSendMessage` as `onAction` to `MessageList`
3. **MessageItem.tsx**: Pass `onAction` to `ComponentRenderer` (done in Task 12)
4. **QuickReplyChips.tsx**: Calls `onAction(option.value)` on chip click

This allows QuickReplyChips clicks to send the chip's value as a new user message.

- **VALIDATE**: Manual test — click a chip, verify message sends

### Task 14: UPDATE `PRD.md` — Add Generative UI section

**IMPLEMENT**: Add section 16 before Next Steps. Content:
- Philosophy: agent decides WHAT, frontend decides HOW
- Architecture Decision Record (DIY vs CopilotKit)
- Streaming Protocol Extension (NDJSON + ui_component chunks)
- Component Catalog (Phase 1 list)
- Semantic Zones

- **VALIDATE**: Read the file, ensure section numbering is correct

---

## TESTING STRATEGY

### Backend Unit Tests (`tests/test_ui_components.py`)

```python
# 10 test cases covering:
# - Valid single/multiple marker extraction
# - Cleaned text output (markers stripped)
# - Malformed JSON handling (skip, no crash)
# - No markers (passthrough)
# - Zone inference for all 7 components + unknown
# - Unique ID generation with counters
# - Empty text edge case
# - Multiline JSON in markers
```

### Frontend Type Checking

- `npx tsc --noEmit` — Ensures all new types integrate correctly
- `npm run lint` — ESLint passes with no errors

### Manual Integration Test

1. Start backend + frontend
2. Send "Calcule mes besoins nutritionnels" (nutrition calculation)
3. Verify: text response appears first, then NutritionSummaryCard + MacroGauges render below
4. Load an old conversation → verify text-only messages render unchanged
5. Click a QuickReplyChip → verify message sends

---

## VALIDATION COMMANDS

### Level 1: Backend Lint & Type Check

```bash
ruff format src/ui_components.py tests/test_ui_components.py
ruff check src/ tests/
mypy src/
```

**Expected**: All pass with exit code 0

### Level 2: Backend Unit Tests

```bash
pytest tests/test_ui_components.py -v
```

**Expected**: All tests pass

### Level 3: Frontend Type Check & Lint

```bash
cd frontend && npx tsc --noEmit && npm run lint
```

**Expected**: No errors

### Level 4: Manual Integration

```bash
# Terminal 1: Backend
cd /mnt/c/Users/meuze/AI-nutrition && python -m uvicorn src.api:app --reload --port 8000

# Terminal 2: Frontend
cd /mnt/c/Users/meuze/AI-nutrition/frontend && npm run dev
```

1. Send nutrition calculation request → verify rich components render
2. Load old conversation → verify backward compatibility
3. Click QuickReplyChip → verify message sends

---

## ACCEPTANCE CRITERIA

- [ ] `extract_ui_components()` parses markers and returns clean text + component list
- [ ] Malformed JSON markers are skipped gracefully (no crash)
- [ ] NDJSON stream includes `ui_component` chunks after text chunks
- [ ] `ui_components` stored in message JSONB for history replay
- [ ] System prompt teaches agent when/how to emit UI markers
- [ ] Frontend accumulates components during streaming
- [ ] ComponentRenderer renders known types, ignores unknown
- [ ] All 7 Phase 1 components render with green glass-morphism theme
- [ ] QuickReplyChips clicks send messages
- [ ] Old text-only conversations render unchanged (backward compatible)
- [ ] All backend tests pass
- [ ] Frontend type-check and lint pass
- [ ] No new npm dependencies added

---

## COMPLETION CHECKLIST

- [ ] All 14 tasks completed in order
- [ ] `pytest tests/test_ui_components.py -v` — all pass
- [ ] `ruff check src/ tests/` — no errors
- [ ] `mypy src/` — no errors
- [ ] `cd frontend && npx tsc --noEmit` — no errors
- [ ] `cd frontend && npm run lint` — no errors
- [ ] Manual integration test passed
- [ ] Backward compatibility verified
- [ ] All acceptance criteria met

---

## NOTES

- **No new dependencies**: This is intentional. The entire feature is ~15 files of glue code.
- **Phase 2 components** (future): CalorieBar, RecipeCard, MealTimeline, WeeklyProgressChart, ShoppingListCard, ProfileSummaryCard, GoalIndicator, ActionButton.
- **The agent won't emit markers immediately** — it needs to be prompted with the right system prompt instructions. The first real test is sending a nutrition calculation request after the prompt update.
- **JSONB flexibility**: Supabase JSONB columns accept arbitrary keys without migration. The `ui_components` field is simply added to the existing message object.
- **Streaming order**: Text chunks stream first (accumulated), then ui_component chunks emit after streaming completes. This ensures text is visible immediately while components appear at the end.
