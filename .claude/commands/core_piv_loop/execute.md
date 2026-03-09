---
description: Execute an implementation plan
argument-hint: [path-to-plan]
---

# Execute: Implement from Plan

## Plan to Execute

Read plan file: `$ARGUMENTS`

## Execution Instructions

### 0. Environment Pre-Check (Optional but Recommended)

Before starting implementation, validate the environment if the feature requires specific libraries:

**If feature uses Pydantic AI, agent tools, or LLM integrations:**
```bash
python -c "from agent import agent; print('✅ Agent initialization successful')"
```

**If validation fails:**
- Document the blocker in execution report
- Proceed with implementation and unit testing only
- Mark integration tests as "blocked by environment"
- User will validate when environment is fixed

**Decision Rule:** Core implementation can proceed even if environment validation fails, as long as unit tests validate all logic paths.

### 1. Read and Understand

- Read the ENTIRE plan carefully
- Understand all tasks and their dependencies
- Note the validation commands to run
- Review the testing strategy

### 2. Execute Tasks in Order

For EACH task in "Step by Step Tasks":

#### a. Navigate to the task
- Identify the file and action required
- Read existing related files if modifying

#### b. Implement the task
- Follow the detailed specifications exactly
- Maintain consistency with existing code patterns
- Include proper type hints and documentation
- Add structured logging where appropriate

#### c. Verify as you go
- After each file change, check syntax
- Ensure imports are correct
- Verify types are properly defined

### 3. Implement Testing Strategy

After completing implementation tasks:

- Create all test files specified in the plan
- Implement all test cases mentioned
- Follow the testing approach outlined
- Ensure tests cover edge cases

### 4. Run Validation Commands

Execute ALL validation commands from the plan in order:

```bash
# Run each command exactly as specified in plan
```

If any command fails:
- Fix the issue
- Re-run the command
- Continue only when it passes

### 5. Seam Review (mandatory before declaring "ready")

Tests passing proves the NEW code works in isolation. This step checks the SEAMS — where new code touches existing code.

For each modified function, answer:

1. **State assumptions**: Does the new code change any variable's possible values (e.g., something that was `None` before is now always set)? If yes → find every place that checks that variable's state.
2. **Callers without the new param**: Which callers of the modified function do NOT pass the new parameter? Do they still get correct behavior, or do they silently get worse behavior? (e.g., `repair()` calling a function without the new override)
3. **Plan says "unchanged"**: For each thing the plan says is unchanged — verify it actually still works correctly with the new state, not just that it still compiles.

If any issue is found → fix it before proceeding. If the fix is out of scope, document it explicitly in the output report as a known limitation.

### 5b. Run Evals (mandatory if feature touches a skill)

If the feature modifies a skill's behavior (script logic, recipe selection, agent routing, etc.):
- Use `/run-eval` to create and run an eval that verifies the agent behaves as expected with a real LLM
- This catches issues that unit tests cannot: routing failures, parameter extraction errors, degraded response quality
- Do NOT skip this step because unit tests pass — unit tests verify logic in isolation, evals verify behavior at the seams

### 6. Final Verification

Before completing:

- ✅ All tasks from plan completed
- ✅ All tests created and passing
- ✅ All validation commands pass
- ✅ Seam review completed (step 5)
- ✅ Code follows project conventions
- ✅ Documentation added/updated as needed

## Output Report

Provide summary:

### Completed Tasks
- List of all tasks completed
- Files created (with paths)
- Files modified (with paths)

### Tests Added
- Test files created
- Test cases implemented
- Test results

### Validation Results
```bash
# Output from each validation command
```

### Ready for Commit
- Confirm all changes are complete
- Confirm all validations pass
- Ready for `/commit` command

## Notes

- If you encounter issues not addressed in the plan, document them
- If you need to deviate from the plan, explain why
- If tests fail, fix implementation until they pass
- Don't skip validation steps
