---
description: "Create evals for a feature we just built (from conversation context) and run it"
argument-hint: "[feature-name or description — leave empty to infer from conversation]"
---

# Create Feature Eval

Generate a `pydantic-evals` evaluation file for the feature implemented in this conversation.

## Feature to evaluate: $ARGUMENTS

---

## Step 1 — Gather context

1. **Review the conversation** to identify:
   - What feature was implemented (files changed, behavior added/modified)
   - What the agent should now do differently (tool calls, responses, side effects)
   - What user inputs trigger the new behavior
   - What the expected outputs/tool calls are

2. **Read the reference eval** for patterns and reusable evaluators:
   ```
   Read evals/test_agent_e2e.py
   ```

3. **Read the Pydantic AI evals documentation**:
   ```
   WebFetch https://ai.pydantic.dev/evals/
   ```

---

## Step 2 — Design scenarios

For each distinct behavior the feature introduces, design one scenario. Each scenario = one `Dataset` with 1-3 `Case`s.

### Scenario design checklist

- [ ] **What LLM decision is being evaluated?** (tool choice, parameter extraction, response quality, routing)
- [ ] **What is the input?** Natural language message in French (matching our agent's language)
- [ ] **What are the success criteria?** (tool was called, args are correct, response contains X, number in range Y)
- [ ] **What is the pre-calculated expected value?** (if numeric — compute it manually using `src.nutrition.calculations`)

### Good scenario categories

| Category | Example | Key evaluators |
|----------|---------|----------------|
| Tool routing | Agent calls the right skill/script | `ToolWasCalled`, `ToolCalledWithArgs` |
| Parameter extraction | Agent extracts age/weight/etc from NL | `ToolCalledWithArgs` with required_args |
| Numeric accuracy | TDEE/BMR/macros in expected range | `NumberInRange` with pre-calculated bounds |
| Safety constraint | Allergens excluded, min calories respected | `ContainsAnyOf` (negative check) |
| Response quality | Substantive, no refusal, mentions key terms | `NoRefusal`, `ResponseMinLength`, `ContainsAnyOf` |
| Behavior change | Old behavior → new behavior (regression) | `ToolWasCalled` (tool that wasn't called before) |

---

## Step 3 — Write the eval file

Create `evals/test_<feature_name>_e2e.py` following these rules:

### File structure (copy this skeleton)

```python
"""E2E eval — <feature description> with real LLM.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM (Haiku 4.5) making decisions:
  - <decision 1>
  - <decision 2>
  - <decision 3>

Outcomes are non-deterministic → scored criteria, not exact assertions.
Run on demand before releases, NOT in CI (slow, costs API credits).

    pytest evals/test_<feature>_e2e.py -m integration -v

TEST PERSONA — all required fields defined here, never assumed elsewhere.
=========================================================================
<persona details with pre-calculated expected values>
"""

import json
import re
from dataclasses import dataclass, field

import pytest
from pydantic_ai.messages import ToolCallPart
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import (
    Evaluator,
    EvaluationReason,
    EvaluatorContext,
    MaxDuration,
)

from src.agent import agent, create_agent_deps


# --- Test persona (single source of truth) ---
TEST_USER_PROFILE = { ... }

# --- Pre-calculated expected values ---
EXPECTED_X = ...


# --- Structured output (text + tool calls) ---
@dataclass
class AgentResult:
    text: str
    tool_calls: list[dict]


# --- Evaluators (reuse from evals/test_agent_e2e.py or create new) ---
# ...

# --- Task function ---
async def _run_agent(message: str) -> AgentResult:
    deps = create_agent_deps()
    result = await agent.run(message, deps=deps)
    tool_calls = []
    for msg in result.all_messages():
        for part in getattr(msg, "parts", []):
            if isinstance(part, ToolCallPart):
                args = part.args
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append({"name": part.tool_name, "args": args})
    return AgentResult(text=result.output, tool_calls=tool_calls)


# --- Scenarios (one Dataset per behavior) ---
def scenario_N_description() -> Dataset:
    return Dataset(
        name="scenario_N_short_name",
        cases=[Case(name="...", inputs="...", evaluators=(...))],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# --- Pytest functions (marked integration) ---
@pytest.mark.integration
async def test_scenario_N_description():
    dataset = scenario_N_description()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
```

### Evaluator catalog (reuse these — don't reinvent)

Check `evals/test_agent_e2e.py` and `evals/test_profile_caching_e2e.py` for existing evaluators before writing new ones:

| Evaluator | What it checks | When to use |
|-----------|---------------|-------------|
| `NoRefusal()` | Agent didn't refuse the task | Always include |
| `ResponseMinLength(min_chars=N)` | Response is substantive | When response quality matters |
| `NumberInRange(min_val, max_val, label)` | A number in text is in range | Numeric calculations (BMR, TDEE, macros) |
| `ContainsAnyOf(options=[...])` | At least one substring present | Keywords, acknowledgments, domain terms |
| `ContainsAllDays()` | All 7 French day names present | Weekly meal plans |
| `MentionsSkill(keywords=[...])` | Domain keywords appear | Verify skill was used |
| `ToolWasCalled(tool_name)` | Tool was called during run | Verify agent routing/behavior |
| `ToolCalledWithArgs(tool_name, required_args)` | Tool called with specific args | Verify parameter extraction |
| `ToolCallCount(tool_name, min_count)` | Tool called >= N times | Multi-step workflows |
| `MaxDuration(seconds=N)` | Completed within time limit | Dataset-level, always include |

**Only create a new evaluator if none of the above fit.** New evaluators must:
- Be a `@dataclass` inheriting `Evaluator`
- Have `evaluation_name: str | None = field(default=None)`
- Return `EvaluationReason(value=bool, reason=str)`
- Access output via `ctx.output` (typed as `AgentResult`)

---

## Step 4 — Good practices (MUST follow)

### From CLAUDE.md
- **Always define `TEST_USER_PROFILE`** at the top with ALL required fields (age, gender, height_cm, weight_kg, activity_level, goals). Never rely on implicit profile data.
- **Pre-calculate expected values** using `src.nutrition.calculations` formulas and document them in the docstring.
- **Mark all test functions `@pytest.mark.integration`** — evals use real LLM, never run in CI.
- **Evals are scored, not asserted** — use `EvaluationReason` with explanatory `reason` strings.
- **`tests/` vs `evals/` rule**: "Is a real LLM making a decision?" Yes → `evals/`. No → `tests/`.

### From Pydantic AI docs
- **Task function signature**: `async def task(inputs: InputType) -> OutputType` — the eval framework calls it.
- **Dataset-level evaluators** (like `MaxDuration`) apply to ALL cases. Case-level evaluators are specific.
- **Use `report.print(include_input=True, include_output=True)`** — shows the full context on failure.
- **Combine evaluator types**: cheap deterministic checks (text, tool calls) + expensive LLM judges (only if needed).
- **Span-based evaluation** (via `ctx.span_tree`) is available if `logfire.configure()` is called — use for deep agent introspection when tool call inspection isn't enough.

### Project conventions
- **French inputs** — the agent speaks French, test with French messages.
- **`AgentResult` dataclass** — always return `text` + `tool_calls` from the task function. This enables both text evaluators and tool call evaluators on the same run.
- **Scenario naming**: `scenario_N_short_description` → `test_scenario_N_short_description`.
- **One Dataset per behavior** — don't mix unrelated behaviors in one Dataset.
- **Tolerant ranges** for numeric checks — LLM may round differently. Use ±10-15% margins.
- **`evaluation_name` parameter** — set it on critical evaluators for clearer failure reports.

### Anti-patterns to avoid
- **Don't test deterministic logic in evals** — that belongs in `tests/` with `FunctionModel`.
- **Don't assert exact strings** — LLM wording varies. Use `ContainsAnyOf` with synonyms.
- **Don't test internal implementation** — test observable behavior (tool calls, response content).
- **Don't set `MaxDuration` too tight** — LLM latency varies. Use 60-120s per scenario.
- **Don't forget `NoRefusal()`** — a refusal means the agent failed entirely, always check.

---

## Step 5 — Validate

```bash
# Format & lint
ruff format evals/test_<feature>_e2e.py
ruff check evals/test_<feature>_e2e.py

# Run evals (costs API credits — real LLM)
pytest evals/test_<feature>_e2e.py -m integration -v -s
```

**Expected**: All scenarios pass. If a scenario fails, check:
1. Is the evaluator too strict? (tighten/loosen ranges)
2. Is the agent prompt missing guidance? (update `src/prompt.py` or SKILL.md)
3. Is it a genuine agent bug? (fix the implementation)

---

## Step 6 — Run the eval & analyze agent behavior

**IMPORTANT**: You MUST run the eval with `-s` (no capture) and carefully study the full output.

```bash
pytest evals/test_<feature>_e2e.py -m integration -v -s
```

After running, read the full output and perform a **behavioral analysis**:

### 6a — For each scenario, extract and study:

1. **Tool call sequence**: Which tools did the agent call, in what order? Was this the expected sequence?
2. **Arguments passed**: Did the agent extract the right parameters from the natural language input? Any misinterpretations?
3. **Response content**: What did the agent actually say? Does it match what a human nutrition coach would say?
4. **Evaluator scores**: Which evaluators passed (✔) and failed (✗)? For each ✗, explain WHY.

### 6b — Flag unexpected behaviors

Look specifically for these patterns and report them:

| Pattern | What to look for | Severity |
|---------|-----------------|----------|
| **Clarification loop** | Agent asks a follow-up question instead of executing the task directly | LOW — conversational but may frustrate users who gave complete info |
| **Tool over-calling** | Agent calls the same tool multiple times unnecessarily (e.g. 3 RAG searches for one question) | LOW — wastes tokens/latency but may improve answer quality |
| **Wrong skill routing** | Agent calls `knowledge-searching` when it should call `nutrition-calculating`, or vice versa | HIGH — fundamentally wrong approach |
| **Parameter hallucination** | Agent invents values not present in the user message (e.g. adds allergies the user didn't mention) | HIGH — safety risk |
| **Parameter over-interpretation** | Agent expands a simple term into a complex structure (e.g. "fromage" → list of 8 cheese types) | MEDIUM — creative but unpredictable, may miss some variants |
| **Ignored instruction** | Agent ignores an explicit user instruction (e.g. "pas de fromage" but suggests cheese recipes) | CRITICAL — trust violation |
| **Stale profile data** | Agent uses profile data from DB that contradicts the current message | MEDIUM — context confusion |
| **Missing next steps** | Agent doesn't offer follow-up actions after completing a task | LOW — less engaging UX |
| **Numeric drift** | Calculated values differ from pre-calculated expectations by >5% | MEDIUM — may indicate calculation bug or LLM rounding |

### 6c — Produce the analysis report

For each scenario, report:

```
### Scenario N — <name>
- **Score**: X/Y evaluators passed (Z%)
- **Tool calls**: tool1(args) → tool2(args) → ...
- **Agent response summary**: <2-3 sentence summary of what the agent said>
- **Expected behavior**: <what we expected>
- **Actual behavior**: <what actually happened>
- **Unexpected behaviors**: <list any from 6b, or "None">
- **Verdict**: ✅ As expected / ⚠️ Minor deviation / ❌ Bug found
```

Then provide an overall summary:

| Scenario | Score | Verdict | Unexpected behaviors |
|----------|-------|---------|---------------------|
| 1. ... | X% | ✅/⚠️/❌ | None / description |
| 2. ... | X% | ✅/⚠️/❌ | None / description |

### 6d — Recommendations

If any unexpected behaviors were found:
1. **Is it a bug to fix?** → describe what code change is needed
2. **Is it an eval to adjust?** → the evaluator was too strict/loose, suggest changes
3. **Is it acceptable agent creativity?** → document it as known behavior, no action needed
4. **Is it a prompt issue?** → suggest changes to `src/prompt.py` or SKILL.md

