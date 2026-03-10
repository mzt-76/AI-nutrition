"""Tunable parameters for the nutrition pipeline.

Single source of truth for all configurable constants used across the meal-planning
and nutrition calculation pipeline. Organized by domain.

Each constant documents:
- What it controls
- Where it's used (file -> function)
- Why it has that value (scientific reference or design rationale)

To tune the pipeline, modify values here -- all dependent modules import from this file.
"""

# =============================================================================
# RECIPE SCORING -- used by recipe_db.py -> score_recipe_variety()
# =============================================================================
# These weights control how recipes are ranked when building a meal plan.
# They must sum to 1.0. Higher weight = more influence on recipe selection.

# How closely recipe macros match the target (protein/carb/fat ratios)
VARIETY_WEIGHT_MACRO_FIT = 0.40

# How recently the recipe was used (older = higher score, promotes variety)
VARIETY_WEIGHT_FRESHNESS = 0.30

# Whether the recipe matches user's preferred cuisine types
VARIETY_WEIGHT_CUISINE = 0.20

# How many times the recipe has been used overall (less used = higher score)
VARIETY_WEIGHT_USAGE = 0.10

# Additive bonus when recipe is in user's favorites (promotes recipes the user explicitly saved).
# Added on top of the 4-factor score (not weighted against them), so score can exceed 1.0.
VARIETY_WEIGHT_FAVORITE = 0.15

# =============================================================================
# MACRO FIT SCORING -- used by recipe_db.py -> score_macro_fit()
# =============================================================================
# Protein deviation is weighted higher than carbs/fat because hitting protein
# targets is the #1 priority for all goals (muscle gain, weight loss, etc.)

# Multiplier for protein ratio deviation in macro fit score (1.0 = same as carbs/fat)
MACRO_FIT_PROTEIN_WEIGHT = 2.0

# =============================================================================
# RECIPE SEARCH -- used by recipe_db.py -> search_recipes()
# =============================================================================
# When searching for recipes, we fetch more than needed because Python-side
# filtering (allergens, disliked foods, variety scoring) reduces the pool.

# Default tolerance for macro ratio deviation (0.25 = +/-25% from target ratios)
DEFAULT_MACRO_RATIO_TOLERANCE = 0.25

# fetch_limit = (limit * MULTIPLIER) + len(exclude_ids) + PADDING
FETCH_LIMIT_MULTIPLIER = 3
FETCH_LIMIT_PADDING = 10

# =============================================================================
# CALORIE GOAL ADJUSTMENTS -- used by:
#   - skills/nutrition-calculating/scripts/calculate_nutritional_needs.py
#   - src/api.py -> calculate endpoint
# =============================================================================
# Applied to TDEE to get target daily calories based on the user's goal.
# Conservative values chosen for sustainability and adherence.

# Caloric surplus for muscle gain (kcal/day above TDEE)
# 300 kcal = moderate surplus for lean gains without excessive fat
MUSCLE_GAIN_SURPLUS_KCAL = 300

# Caloric deficit for weight loss (kcal/day below TDEE)
# 500 kcal ~ ~0.45 kg/week loss -- sustainable without muscle wasting
WEIGHT_LOSS_DEFICIT_KCAL = 500

# Caloric surplus for performance goals (kcal/day above TDEE)
# 200 kcal = mild surplus to fuel training without weight gain focus
PERFORMANCE_SURPLUS_KCAL = 200

# Full mapping used by api.py for quick lookup
GOAL_CALORIE_ADJUSTMENTS: dict[str, int] = {
    "weight_loss": -WEIGHT_LOSS_DEFICIT_KCAL,
    "muscle_gain": MUSCLE_GAIN_SURPLUS_KCAL,
    "maintenance": 0,
    "performance": PERFORMANCE_SURPLUS_KCAL,
}

# =============================================================================
# PROTEIN TARGETS -- used by calculations.py -> calculate_protein_target()
# =============================================================================
# "Intermediate" starting values within the ISSN ranges. Used by default
# instead of the range maximum for more realistic initial recommendations.

# Weight loss: middle of 2.3-3.1 range -- better adherence than jumping to 3.1
PROTEIN_INTERMEDIATE_WEIGHT_LOSS = 2.5  # g/kg body weight

# Muscle gain: high-middle of 1.6-2.2 range -- evidence shows diminishing returns above 2.0
PROTEIN_INTERMEDIATE_MUSCLE_GAIN = 2.0  # g/kg body weight

# =============================================================================
# FAT FLOOR -- used by calculations.py -> calculate_macros()
# =============================================================================
# Minimum fat intake regardless of calorie target. Below this threshold,
# hormonal function is impaired (testosterone, estrogen synthesis).

# ISSN guideline: minimum 0.6 g/kg body weight for hormonal health
MIN_FAT_G_PER_KG = 0.6

# =============================================================================
# LLM RECIPE GENERATION -- used by generate_custom_recipe.py
# =============================================================================
# Parameters for the Anthropic API call that generates custom recipes
# when no existing recipe matches the user's request.

# Max tokens for recipe generation response (typical recipe = ~800 tokens)
RECIPE_MAX_TOKENS = 2000

# Temperature controls creativity vs consistency (0.0 = deterministic, 1.0 = creative)
# 0.7 = balanced: enough variation for diverse recipes, enough consistency for valid JSON
RECIPE_TEMPERATURE = 0.7

# =============================================================================
# DEFAULT PREP TIME -- used by:
#   - skills/meal-planning/scripts/generate_custom_recipe.py
#   - skills/meal-planning/scripts/generate_day_plan.py -> _build_meal_from_scaled_recipe()
# =============================================================================
# Fallback when a recipe has no prep_time_minutes field.
# 30 min = reasonable average for a home-cooked meal.

DEFAULT_PREP_TIME_MINUTES = 30

# =============================================================================
# MILP OBJECTIVE WEIGHTS -- used by portion_optimizer_v2.py
# =============================================================================
# Macro weights in the MILP objective function. Higher weight = macro deviation
# is penalized more heavily. Protein and fat are highest priority.

WEIGHT_PROTEIN = 2.0
WEIGHT_FAT = 2.0  # equal to protein -- critical for hormonal health
WEIGHT_CALORIES = 1.0
WEIGHT_CARBS = 0.5  # carbs are the adjustment variable
WEIGHT_MEAL_BALANCE = 1.5  # per-meal calorie balance

# =============================================================================
# MILP ROLE BOUNDS -- used by ingredient_roles.py -> get_role_bounds()
# =============================================================================
# Scaling limits per culinary role. Each role has (min_scale, max_scale).

ROLE_BOUNDS: dict[str, tuple[float, float]] = {
    "protein": (0.5, 2.0),
    "starch": (0.3, 2.5),
    "vegetable": (0.7, 1.5),
    "fat_source": (0.2, 1.5),
    "unknown": (0.75, 1.25),
    "fixed": (1.0, 1.0),
}

# =============================================================================
# MILP DIVERGENCE CONSTRAINTS -- used by portion_optimizer_v2.py
# =============================================================================
# Inter-group coherence: structural ingredient groups (protein <-> starch <-> vegetable)
# can't diverge beyond MAX_GROUP_DIVERGENCE. fat_source is exempt.

MAX_GROUP_DIVERGENCE: float = 2.0

# fat_source is EXEMPT from divergence -- oils/butter are independent adjustments
DIVERGENCE_PAIRS: list[tuple[str, str]] = [
    ("protein", "starch"),
    ("protein", "vegetable"),
    ("starch", "vegetable"),
]

# =============================================================================
# MILP DISCRETE UNITS -- used by ingredient_roles.py -> is_discrete_unit()
# =============================================================================
# Items counted in pieces (MILP integer variables)

DISCRETE_UNITS: set[str] = {
    "pièces",
    "pièce",
    "piece",
    "pieces",
    "tranche",
    "tranches",
    "oeuf",
    "oeufs",
    "œuf",
    "œufs",
}

# =============================================================================
# SAFETY CONSTRAINTS -- hardcoded, never bypass (CLAUDE.md rule 3)
# =============================================================================
# Absolute minimum daily calorie intake to prevent metabolic harm.
# Below these thresholds, hormonal function, muscle preservation, and
# cognitive performance are significantly impaired.

# Women: 1200 kcal/day minimum (WHO guideline for supervised weight loss)
MIN_CALORIES_WOMEN = 1200

# Men: 1500 kcal/day minimum (WHO guideline for supervised weight loss)
MIN_CALORIES_MEN = 1500

# Zero tolerance: if a recipe contains ANY user allergen, it must be excluded
ALLERGEN_ZERO_TOLERANCE = True

# Always filter out disliked foods from recipe search results
DISLIKED_FOODS_FILTERED = True
