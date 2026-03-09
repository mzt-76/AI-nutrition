"""Day-level portion optimization using linear programming.

Finds optimal scale factors for ALL recipes in a day simultaneously,
minimizing total weighted macro deviation. Unlike the old 3-pass macro_scaler
which optimized each recipe independently (causing corrections to fight each
other), this solver optimizes globally.

The problem is a continuous LP (no binary variables — recipes are already chosen):
    Variables: s_1, s_2, ..., s_n (scale factors per recipe)
    Objective: minimize weighted sum of |actual_macro - target_macro| for each macro
    Constraints: 0.5 <= s_i <= 3.0 for each recipe

Solved in <1ms for 3-4 recipes via scipy.optimize.linprog.

References:
    Helms et al. (2014): Portion scaling maintains adherence better than supplements
"""

import logging

from scipy.optimize import linprog

from src.nutrition.meal_plan_optimizer import MIN_SCALE_FACTOR, MAX_SCALE_FACTOR
from src.nutrition.quantity_rounding import round_quantity_smart

logger = logging.getLogger(__name__)

# Macro weights in objective — protein is highest priority
WEIGHT_PROTEIN = 2.0
WEIGHT_FAT = 1.5
WEIGHT_CALORIES = 1.0
WEIGHT_CARBS = 0.5  # carbs are the adjustment variable
WEIGHT_MEAL_BALANCE = 1.5  # per-meal calorie balance


def _extract_recipe_macros(recipe: dict) -> dict:
    """Extract per-serving macros from a recipe dict.

    Tries nutrition_per_100g-based calculation from ingredients first,
    then falls back to per_serving fields.

    Returns:
        Dict with calories, protein_g, fat_g, carbs_g.
    """
    ingredients = recipe.get("ingredients", [])
    totals = {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0}

    has_per_100g = False
    for ing in ingredients:
        n = ing.get("nutrition_per_100g")
        if not n:
            continue
        has_per_100g = True
        qty = ing.get("quantity", 0) or 0
        factor = qty / 100.0
        totals["calories"] += (n.get("calories", 0) or 0) * factor
        totals["protein_g"] += (n.get("protein_g", 0) or 0) * factor
        totals["fat_g"] += (n.get("fat_g", 0) or 0) * factor
        totals["carbs_g"] += (n.get("carbs_g", 0) or 0) * factor

    if has_per_100g and totals["calories"] > 0:
        return totals

    # Fallback to per_serving fields
    return {
        "calories": float(recipe.get("calories_per_serving", 0) or 0),
        "protein_g": float(recipe.get("protein_g_per_serving", 0) or 0),
        "fat_g": float(recipe.get("fat_g_per_serving", 0) or 0),
        "carbs_g": float(recipe.get("carbs_g_per_serving", 0) or 0),
    }


def optimize_day_portions(
    recipes: list[dict],
    daily_targets: dict,
    per_meal_targets: list[float] | None = None,
) -> list[float]:
    """Find optimal scale factors for all recipes to minimize macro deviation.

    Uses LP with absolute-value linearization:
        For each macro m: d_m+ - d_m- = sum(s_i * recipe_i_macro_m) - target_m
        Minimize: sum(w_m * (d_m+ + d_m-))

    When per_meal_targets is provided, adds soft per-meal calorie balance constraints:
        For each recipe i: s_i * cal_i - dm_i+ + dm_i- = per_meal_target_i
        Adds WEIGHT_MEAL_BALANCE * sum(dm_i+ + dm_i-) to the objective.

    Args:
        recipes: List of recipe dicts (each with ingredients or per_serving macros).
        daily_targets: Dict with calories, protein_g, fat_g, carbs_g targets.
        per_meal_targets: Optional list of target calories per recipe (same length
            as recipes). Each entry is the calorie target for that recipe's meal slot.

    Returns:
        List of scale factors [s_1, s_2, ..., s_n], one per recipe.

    Raises:
        ValueError: If recipes is empty or daily_targets has no positive calories.
    """
    n = len(recipes)
    if n == 0:
        raise ValueError("recipes list cannot be empty")

    target_cal = float(daily_targets.get("calories", 0) or 0)
    target_prot = float(daily_targets.get("protein_g", 0) or 0)
    target_fat = float(daily_targets.get("fat_g", 0) or 0)
    target_carbs = float(daily_targets.get("carbs_g", 0) or 0)

    if target_cal <= 0:
        raise ValueError(f"daily_targets calories must be positive, got {target_cal}")

    # Extract macros for each recipe
    recipe_macros = [_extract_recipe_macros(r) for r in recipes]

    # --- LP formulation ---
    # Variables: [s_1..s_n, d_cal+, d_cal-, d_prot+, d_prot-, d_fat+, d_fat-,
    #             d_carbs+, d_carbs-, (dm_1+, dm_1-, ..., dm_n+, dm_n-)]
    # Base: n + 8. With per_meal_targets: n + 8 + 2n = 3n + 8.
    use_meal_balance = per_meal_targets is not None and len(per_meal_targets) == n
    num_meal_dev = 2 * n if use_meal_balance else 0
    num_vars = n + 8 + num_meal_dev

    # Objective: minimize w_cal*(d_cal+ + d_cal-) + w_prot*(d_prot+ + d_prot-) + ...
    c = [0.0] * num_vars
    # Deviation variable indices
    idx_cal_plus, idx_cal_minus = n, n + 1
    idx_prot_plus, idx_prot_minus = n + 2, n + 3
    idx_fat_plus, idx_fat_minus = n + 4, n + 5
    idx_carbs_plus, idx_carbs_minus = n + 6, n + 7

    c[idx_cal_plus] = WEIGHT_CALORIES
    c[idx_cal_minus] = WEIGHT_CALORIES
    c[idx_prot_plus] = WEIGHT_PROTEIN
    c[idx_prot_minus] = WEIGHT_PROTEIN
    c[idx_fat_plus] = WEIGHT_FAT
    c[idx_fat_minus] = WEIGHT_FAT
    c[idx_carbs_plus] = WEIGHT_CARBS
    c[idx_carbs_minus] = WEIGHT_CARBS

    # Per-meal balance deviation weights
    if use_meal_balance:
        for i in range(n):
            dm_plus_idx = n + 8 + 2 * i
            dm_minus_idx = n + 8 + 2 * i + 1
            c[dm_plus_idx] = WEIGHT_MEAL_BALANCE
            c[dm_minus_idx] = WEIGHT_MEAL_BALANCE

    # Equality constraints: for each macro,
    #   sum(s_i * macro_i) - d+ + d- = target
    A_eq: list[list[float]] = []
    b_eq: list[float] = []

    macros_keys = ["calories", "protein_g", "fat_g", "carbs_g"]
    targets = [target_cal, target_prot, target_fat, target_carbs]
    dev_indices = [
        (idx_cal_plus, idx_cal_minus),
        (idx_prot_plus, idx_prot_minus),
        (idx_fat_plus, idx_fat_minus),
        (idx_carbs_plus, idx_carbs_minus),
    ]

    for macro_idx, (macro_key, target_val, (d_plus, d_minus)) in enumerate(
        zip(macros_keys, targets, dev_indices)
    ):
        row = [0.0] * num_vars
        for i in range(n):
            row[i] = recipe_macros[i][macro_key]
        row[d_plus] = -1.0
        row[d_minus] = 1.0
        A_eq.append(row)
        b_eq.append(target_val)

    # Per-meal calorie balance constraints:
    #   s_i * recipe_cal_i - dm_i+ + dm_i- = per_meal_target_i
    if use_meal_balance:
        assert per_meal_targets is not None  # for type checker
        for i in range(n):
            row = [0.0] * num_vars
            row[i] = recipe_macros[i]["calories"]
            dm_plus_idx = n + 8 + 2 * i
            dm_minus_idx = n + 8 + 2 * i + 1
            row[dm_plus_idx] = -1.0
            row[dm_minus_idx] = 1.0
            A_eq.append(row)
            b_eq.append(float(per_meal_targets[i]))

    # Bounds: scale factors in [MIN, MAX], deviations >= 0
    bounds: list[tuple[float, float | None]] = []
    for i in range(n):
        bounds.append((MIN_SCALE_FACTOR, MAX_SCALE_FACTOR))
    for _ in range(8 + num_meal_dev):
        bounds.append((0.0, None))  # type: ignore[arg-type]  # scipy accepts None as upper bound

    result = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")

    if not result.success:
        # Fallback: uniform calorie scaling
        total_cal = sum(rm["calories"] for rm in recipe_macros)
        if total_cal > 0:
            uniform = max(
                MIN_SCALE_FACTOR, min(MAX_SCALE_FACTOR, target_cal / total_cal)
            )
        else:
            uniform = 1.0
        logger.warning(
            f"LP solver infeasible ({result.message}): uniform factor={uniform:.2f}, "
            f"macro targets NOT optimized — validation will catch deviations"
        )
        return [uniform] * n

    scale_factors = [round(result.x[i], 4) for i in range(n)]

    # Log results
    actual = {k: 0.0 for k in macros_keys}
    for i, rm in enumerate(recipe_macros):
        for k in macros_keys:
            actual[k] += rm[k] * scale_factors[i]

    logger.info(
        f"LP optimizer: {n} recipes, factors={[f'{s:.2f}' for s in scale_factors]}, "
        f"result={actual['calories']:.0f}/{actual['protein_g']:.0f}p/"
        f"{actual['fat_g']:.0f}f/{actual['carbs_g']:.0f}c "
        f"(targets={target_cal:.0f}/{target_prot:.0f}p/{target_fat:.0f}f/{target_carbs:.0f}c)"
    )

    return scale_factors


def apply_scale_factor(recipe: dict, scale_factor: float) -> dict:
    """Apply a uniform scale factor to a recipe's ingredients and compute nutrition.

    Args:
        recipe: Recipe dict with ingredients list.
        scale_factor: Multiplier for all ingredient quantities.

    Returns:
        New recipe dict with scaled ingredients and a "scaled_nutrition" key.
    """
    scaled_recipe = dict(recipe)
    ingredients = recipe.get("ingredients", [])
    scaled_ingredients = []

    for ing in ingredients:
        new_ing = dict(ing)
        raw_qty = (ing.get("quantity", 0) or 0) * scale_factor
        new_ing["quantity"] = round_quantity_smart(
            raw_qty, ing.get("unit", "g"), ing.get("name", "")
        )
        scaled_ingredients.append(new_ing)

    scaled_recipe["ingredients"] = scaled_ingredients

    # Compute nutrition from scaled ingredients if they have per-100g data
    has_per_100g = any(ing.get("nutrition_per_100g") for ing in scaled_ingredients)
    if has_per_100g:
        macros = _extract_recipe_macros(scaled_recipe)
        scaled_recipe["scaled_nutrition"] = {k: round(v, 2) for k, v in macros.items()}
    else:
        # Fallback: scale per_serving values by factor
        scaled_recipe["scaled_nutrition"] = {
            "calories": round(
                float(recipe.get("calories_per_serving", 0) or 0) * scale_factor, 2
            ),
            "protein_g": round(
                float(recipe.get("protein_g_per_serving", 0) or 0) * scale_factor, 2
            ),
            "fat_g": round(
                float(recipe.get("fat_g_per_serving", 0) or 0) * scale_factor, 2
            ),
            "carbs_g": round(
                float(recipe.get("carbs_g_per_serving", 0) or 0) * scale_factor, 2
            ),
        }

    scaled_recipe["scale_factor"] = round(scale_factor, 4)

    logger.info(
        f"Scaled '{recipe.get('name', '?')}': factor={scale_factor:.2f}, "
        f"{scaled_recipe['scaled_nutrition']['calories']:.0f} kcal, "
        f"{scaled_recipe['scaled_nutrition']['protein_g']:.0f}g prot, "
        f"{scaled_recipe['scaled_nutrition']['fat_g']:.0f}g fat, "
        f"{scaled_recipe['scaled_nutrition']['carbs_g']:.0f}g carbs"
    )

    return scaled_recipe
