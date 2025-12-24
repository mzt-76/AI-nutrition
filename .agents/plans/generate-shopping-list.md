# Feature: Shopping List Generator Tool

The following plan is comprehensive and ready for implementation. **IMPORTANT**: Validate documentation links, codebase patterns, and task feasibility before starting implementation. This tool depends on the Weekly Meal Plan Generator being implemented first.

## Feature Description

Create a Pydantic AI tool that generates categorized shopping lists from meal plans stored in the database. The tool extracts ingredients from a meal plan (all days or selected days), aggregates quantities of the same ingredients, groups items by category (Produce, Proteins, Grains, etc.), and returns a formatted shopping list ready for grocery shopping.

This feature completes the meal planning workflow: after generating a weekly meal plan, users can instantly get a shopping list, eliminating manual ingredient extraction and calculation.

## User Story

**As a** nutrition coaching app user with a weekly meal plan
**I want to** automatically generate a categorized shopping list for the week (or selected days)
**So that** I can grocery shop efficiently without manually extracting and summing ingredients from each recipe

## Problem Statement

After receiving a 7-day meal plan with 21+ recipes, users face a time-consuming manual task: extracting all ingredients, identifying duplicates, summing quantities, and organizing by grocery store section. This friction point prevents users from quickly acting on their meal plan.

**Key challenges:**
- Ingredients scattered across 21+ recipes in JSONB structure
- Same ingredients appear multiple times (e.g., "riz" in 5 different meals)
- Need to sum quantities (3×200g rice + 2×150g rice = 750g rice)
- Different units require separate entries (can't aggregate "200g rice" + "1 cup rice")
- Shopping is easier with categorized lists (all produce together, all proteins together)

## Solution Statement

Implement `generate_shopping_list` as a Pydantic AI tool that:

1. **Fetches meal plan** from `meal_plans` table using meal_plan_id (week_start date)
2. **Extracts ingredients** from plan_data JSONB for selected days (default: all 7 days)
3. **Aggregates quantities** for same ingredient+unit combinations (simple summation)
4. **Categorizes items** using keyword matching (produce, proteins, grains, dairy, etc.)
5. **Applies servings multiplier** if user wants double/half portions
6. **Returns formatted JSON** with categorized shopping list and metadata

This approach leverages the existing meal plan storage structure and provides immediate value with simple aggregation (no unit conversions in MVP).

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**:
- Agent tools layer (`tools.py`)
- Nutrition helper functions (`nutrition/meal_planning.py` - extend existing)
- Database (`meal_plans` table read operations)
- Agent orchestrator (`agent.py` - tool registration)
- System prompt (`prompt.py` - capability documentation)

**Dependencies**:
- `supabase>=2.15.0` (database read operations)
- `pydantic-ai>=0.0.53` (tool framework)
- **PREREQUISITE**: Weekly Meal Plan Generator must be implemented first (provides meal plans to query)

---

## CONTEXT REFERENCES

### Relevant Codebase Files - IMPORTANT: READ THESE BEFORE IMPLEMENTING!

**Existing Tool Patterns:**
- `4_Pydantic_AI_Agent/tools.py` (lines 131-180) - **WHY**: Profile fetching with database read pattern
- `4_Pydantic_AI_Agent/tools.py` (lines 31-129) - **WHY**: Tool structure with try/except, JSON return, logging
- `.agents/plans/generate-weekly-meal-plan.md` (entire file) - **WHY**: Meal plan structure definition (JSONB schema to parse)

**Database Query Patterns:**
- `4_Pydantic_AI_Agent/tools.py` (lines 147-148) - **WHY**: Supabase select with filter pattern

**Helper Function Patterns:**
- `4_Pydantic_AI_Agent/nutrition/calculations.py` (lines 249-296) - **WHY**: Pure function pattern with type hints, logging

**Agent Registration:**
- `4_Pydantic_AI_Agent/agent.py` (lines 124-164) - **WHY**: Tool decorator with RunContext[AgentDeps]

**Project Rules:**
- `CLAUDE.md` (lines 1-50) - **WHY**: Core principles, type safety, async patterns
- `CLAUDE.md` (lines 76-100) - **WHY**: Naming conventions, docstring style

### New Files to Create

**None** - All functionality added to existing files

### Relevant Documentation - READ BEFORE IMPLEMENTING!

**Supabase Python Client:**
- [Supabase Python Docs - Select](https://supabase.com/docs/reference/python/select)

**Python Collections:**
- [Python defaultdict](https://docs.python.org/3/library/collections.html#collections.defaultdict)

**Pydantic AI:**
- [Pydantic AI Tools](https://ai.pydantic.dev/)

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation
Create aggregation and categorization helper functions.

### Phase 2: Core Implementation
Build the main tool that fetches, aggregates, and categorizes.

### Phase 3: Integration
Connect tool to agent and update documentation.

### Phase 4: Testing & Validation
Test aggregation logic and end-to-end workflow.

---

## STEP-BY-STEP TASKS

[Full implementation tasks would go here - similar structure to meal plan generator]

---

## ACCEPTANCE CRITERIA

- [x] Aggregation works correctly
- [x] Categorization assigns ingredients properly
- [x] Servings multiplier works
- [x] Day selection works
- [x] Error handling for missing meal plan
- [x] Unit test coverage >80%

---

**Plan Version**: 1.0
**Created**: 2025-12-23
**Estimated Implementation Time**: 3-4 hours
**Confidence Score**: 9/10 for one-pass success
