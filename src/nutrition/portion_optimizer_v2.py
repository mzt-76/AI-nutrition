"""Day-level MILP per-ingredient portion optimization.

Replaces the v1 LP (1 scale factor per recipe) with a MILP that has 1 variable
per ingredient. Each ingredient is tagged with a culinary role (protein, starch,
vegetable, fat_source, fixed) that determines its scaling bounds. Discrete items
(eggs, slices) use integer variables.

Divergence constraints ensure that within a recipe, structural ingredient groups
(protein ↔ starch ↔ vegetable) don't diverge beyond 2×. fat_source is exempt —
the solver can freely reduce oil while keeping chicken high.

Solved in <10ms for ~20 variables via scipy.optimize.milp.

References:
    Helms et al. (2014): Portion scaling maintains adherence better than supplements
"""

import logging
import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import LinearConstraint, milp
from src.nutrition.constants import (
    DIVERGENCE_PAIRS,
    MAX_GROUP_DIVERGENCE,
    WEIGHT_CALORIES,
    WEIGHT_CARBS,
    WEIGHT_FAT,
    WEIGHT_MEAL_BALANCE,
    WEIGHT_PROTEIN,
)
from src.nutrition.ingredient_roles import (
    get_ingredient_role,
    get_role_bounds,
    is_discrete_unit,
)
from src.nutrition.openfoodfacts_client import _PIECE_WEIGHTS, _unit_to_multiplier
from src.nutrition.quantity_rounding import round_quantity_smart

logger = logging.getLogger(__name__)


@dataclass
class IngredientVar:
    """An ingredient that gets a MILP variable."""

    recipe_idx: int
    ing_idx: int
    name: str
    role: str
    base_qty: float
    unit: str
    base_multiplier: float  # _unit_to_multiplier(base_qty, unit, name)
    nutrition_per_100g: dict  # {calories, protein_g, fat_g, carbs_g}
    is_discrete: bool
    lb: float  # lower bound for the variable
    ub: float  # upper bound for the variable
    piece_weight: float  # grams per piece (0 if not discrete)


def _get_piece_weight(name: str) -> float:
    """Look up weight per piece for discrete items."""
    name_lower = name.lower().strip()
    for key, weight_g in _PIECE_WEIGHTS.items():
        if key in name_lower:
            return weight_g
    return 0.0


def _prepare_ingredients(
    recipes: list[dict],
) -> tuple[list[IngredientVar], list[tuple[int, int, dict]]]:
    """Prepare ingredient variables and fixed ingredients from recipes.

    Returns:
        (scalable_vars, fixed_ingredients) where fixed_ingredients is a list of
        (recipe_idx, ing_idx, ingredient_dict) tuples.
    """
    scalable: list[IngredientVar] = []
    fixed: list[tuple[int, int, dict]] = []

    for r_idx, recipe in enumerate(recipes):
        for i_idx, ing in enumerate(recipe.get("ingredients", [])):
            n = ing.get("nutrition_per_100g")
            if not n:
                continue

            name = ing.get("name", "")
            qty = float(ing.get("quantity", 0) or 0)
            unit = ing.get("unit", "g")
            role = get_ingredient_role(name)

            if role == "fixed":
                fixed.append((r_idx, i_idx, ing))
                continue

            role_min, role_max = get_role_bounds(role)
            discrete = is_discrete_unit(unit)
            piece_weight = _get_piece_weight(name) if discrete else 0.0

            if discrete and piece_weight > 0:
                # Variable = final quantity in pieces (integer)
                int_lb = max(1, math.floor(qty * role_min))
                int_ub = math.ceil(qty * role_max)
                base_mult = piece_weight / 100.0  # per-piece multiplier
                scalable.append(
                    IngredientVar(
                        recipe_idx=r_idx,
                        ing_idx=i_idx,
                        name=name,
                        role=role,
                        base_qty=qty,
                        unit=unit,
                        base_multiplier=base_mult,
                        nutrition_per_100g=dict(n),
                        is_discrete=True,
                        lb=float(int_lb),
                        ub=float(int_ub),
                        piece_weight=piece_weight,
                    )
                )
            else:
                # Variable = scale factor (continuous)
                base_mult = _unit_to_multiplier(qty, unit, name)
                scalable.append(
                    IngredientVar(
                        recipe_idx=r_idx,
                        ing_idx=i_idx,
                        name=name,
                        role=role,
                        base_qty=qty,
                        unit=unit,
                        base_multiplier=base_mult,
                        nutrition_per_100g=dict(n),
                        is_discrete=False,
                        lb=role_min,
                        ub=role_max,
                        piece_weight=0.0,
                    )
                )

    return scalable, fixed


def _macro_contribution(var: IngredientVar, macro: str) -> float:
    """Coefficient of var's MILP variable for a given macro.

    For continuous vars: scale_factor * base_multiplier * nutrition_per_100g[macro]
        → coefficient = base_multiplier * nutrition_per_100g[macro]
    For discrete vars: qty_pieces * piece_weight/100 * nutrition_per_100g[macro]
        → coefficient = piece_weight/100 * nutrition_per_100g[macro]
    """
    n_val = float(var.nutrition_per_100g.get(macro, 0) or 0)
    return var.base_multiplier * n_val


def _fixed_contribution(ing: dict) -> dict[str, float]:
    """Compute macro contribution of a fixed ingredient."""
    n = ing.get("nutrition_per_100g", {})
    qty = float(ing.get("quantity", 0) or 0)
    unit = ing.get("unit", "g")
    name = ing.get("name", "")
    mult = _unit_to_multiplier(qty, unit, name)
    return {
        "calories": float(n.get("calories", 0) or 0) * mult,
        "protein_g": float(n.get("protein_g", 0) or 0) * mult,
        "fat_g": float(n.get("fat_g", 0) or 0) * mult,
        "carbs_g": float(n.get("carbs_g", 0) or 0) * mult,
    }


def optimize_day_portions_v2(
    recipes: list[dict],
    daily_targets: dict,
    per_meal_targets: list[float] | None = None,
) -> list[dict[int, float]]:
    """Find optimal per-ingredient scale factors using MILP.

    Args:
        recipes: List of recipe dicts with ingredients (each having nutrition_per_100g).
        daily_targets: Dict with calories, protein_g, fat_g, carbs_g targets.
        per_meal_targets: Optional list of target calories per recipe.

    Returns:
        List of dicts (one per recipe). Each dict maps ing_idx → scale_factor.
        For discrete items, the "scale_factor" IS the final quantity in pieces.

    Raises:
        ValueError: If recipes is empty or targets are invalid.
    """
    n_recipes = len(recipes)
    if n_recipes == 0:
        raise ValueError("recipes list cannot be empty")

    target_cal = float(daily_targets.get("calories", 0) or 0)
    target_prot = float(daily_targets.get("protein_g", 0) or 0)
    target_fat = float(daily_targets.get("fat_g", 0) or 0)
    target_carbs = float(daily_targets.get("carbs_g", 0) or 0)

    if target_cal <= 0:
        raise ValueError(f"daily_targets calories must be positive, got {target_cal}")

    scalable, fixed_ings = _prepare_ingredients(recipes)

    # If no scalable ingredients, return empty scale factors
    if not scalable:
        return [{} for _ in recipes]

    # Compute fixed contribution (subtract from targets)
    fixed_total = {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0}
    # Also track per-recipe fixed calories for meal balance
    fixed_cal_per_recipe: dict[int, float] = {}
    for r_idx, _, ing in fixed_ings:
        contrib = _fixed_contribution(ing)
        for k in fixed_total:
            fixed_total[k] += contrib[k]
        fixed_cal_per_recipe[r_idx] = (
            fixed_cal_per_recipe.get(r_idx, 0.0) + contrib["calories"]
        )

    adjusted_targets = {
        "calories": target_cal - fixed_total["calories"],
        "protein_g": target_prot - fixed_total["protein_g"],
        "fat_g": target_fat - fixed_total["fat_g"],
        "carbs_g": target_carbs - fixed_total["carbs_g"],
    }

    n_scalable = len(scalable)
    use_meal_balance = (
        per_meal_targets is not None and len(per_meal_targets) == n_recipes
    )
    n_meal_dev = 2 * n_recipes if use_meal_balance else 0
    # Variables: [x_0..x_{n_scalable-1}, d_cal+, d_cal-, d_prot+, d_prot-,
    #             d_fat+, d_fat-, d_carbs+, d_carbs-, (dm_0+, dm_0-, ...)]
    n_vars = n_scalable + 8 + n_meal_dev

    # --- Objective ---
    c = np.zeros(n_vars)
    dev_start = n_scalable
    c[dev_start + 0] = WEIGHT_CALORIES  # d_cal+
    c[dev_start + 1] = WEIGHT_CALORIES  # d_cal-
    c[dev_start + 2] = WEIGHT_PROTEIN  # d_prot+
    c[dev_start + 3] = WEIGHT_PROTEIN  # d_prot-
    c[dev_start + 4] = WEIGHT_FAT  # d_fat+
    c[dev_start + 5] = WEIGHT_FAT  # d_fat-
    c[dev_start + 6] = WEIGHT_CARBS  # d_carbs+
    c[dev_start + 7] = WEIGHT_CARBS  # d_carbs-

    meal_dev_start = n_scalable + 8
    if use_meal_balance:
        for i in range(n_recipes):
            c[meal_dev_start + 2 * i] = WEIGHT_MEAL_BALANCE
            c[meal_dev_start + 2 * i + 1] = WEIGHT_MEAL_BALANCE

    # --- Build constraint matrix ---
    macros_keys = ["calories", "protein_g", "fat_g", "carbs_g"]
    targets_list = [
        adjusted_targets["calories"],
        adjusted_targets["protein_g"],
        adjusted_targets["fat_g"],
        adjusted_targets["carbs_g"],
    ]

    # Equality constraints: macro balance
    eq_rows: list[np.ndarray] = []
    eq_rhs: list[float] = []

    for m_idx, (macro, target_val) in enumerate(zip(macros_keys, targets_list)):
        row = np.zeros(n_vars)
        for v_idx, var in enumerate(scalable):
            row[v_idx] = _macro_contribution(var, macro)
        d_plus = dev_start + 2 * m_idx
        d_minus = dev_start + 2 * m_idx + 1
        row[d_plus] = -1.0
        row[d_minus] = 1.0
        eq_rows.append(row)
        eq_rhs.append(target_val)

    # Per-meal calorie balance constraints
    if use_meal_balance:
        assert per_meal_targets is not None
        for r_idx in range(n_recipes):
            row = np.zeros(n_vars)
            for v_idx, var in enumerate(scalable):
                if var.recipe_idx == r_idx:
                    row[v_idx] = _macro_contribution(var, "calories")
            dm_plus = meal_dev_start + 2 * r_idx
            dm_minus = meal_dev_start + 2 * r_idx + 1
            row[dm_plus] = -1.0
            row[dm_minus] = 1.0
            # Subtract fixed calories for this recipe from the target
            adj_target = per_meal_targets[r_idx] - fixed_cal_per_recipe.get(r_idx, 0.0)
            eq_rows.append(row)
            eq_rhs.append(adj_target)

    # Inequality constraints: divergence between groups within each recipe
    ineq_rows: list[np.ndarray] = []
    ineq_ub: list[float] = []

    for r_idx in range(n_recipes):
        # Collect scalable vars per role for this recipe
        role_vars: dict[str, list[int]] = {}
        for v_idx, var in enumerate(scalable):
            if var.recipe_idx == r_idx and var.role not in ("fixed", "unknown"):
                role_vars.setdefault(var.role, []).append(v_idx)

        for g1_role, g2_role in DIVERGENCE_PAIRS:
            g1_indices = role_vars.get(g1_role, [])
            g2_indices = role_vars.get(g2_role, [])
            if not g1_indices or not g2_indices:
                continue

            n_g1 = len(g1_indices)
            n_g2 = len(g2_indices)

            # sum(x_i ∈ g1) * |g2| ≤ MAX_DIVERGENCE * sum(x_j ∈ g2) * |g1|
            # Rearranged: sum(x_i ∈ g1) * |g2| - MAX_DIVERGENCE * sum(x_j ∈ g2) * |g1| ≤ 0
            row1 = np.zeros(n_vars)
            for v_idx in g1_indices:
                row1[v_idx] = n_g2
            for v_idx in g2_indices:
                row1[v_idx] = -MAX_GROUP_DIVERGENCE * n_g1
            ineq_rows.append(row1)
            ineq_ub.append(0.0)

            # Symmetric: sum(x_j ∈ g2) * |g1| ≤ MAX_DIVERGENCE * sum(x_i ∈ g1) * |g2|
            row2 = np.zeros(n_vars)
            for v_idx in g2_indices:
                row2[v_idx] = n_g1
            for v_idx in g1_indices:
                row2[v_idx] = -MAX_GROUP_DIVERGENCE * n_g2
            ineq_rows.append(row2)
            ineq_ub.append(0.0)

    # --- Assemble constraints ---
    constraints = []

    if eq_rows:
        A_eq = np.array(eq_rows)
        b_eq = np.array(eq_rhs)
        constraints.append(LinearConstraint(A_eq, b_eq, b_eq))

    if ineq_rows:
        A_ineq = np.array(ineq_rows)
        ub_ineq = np.array(ineq_ub)
        constraints.append(LinearConstraint(A_ineq, -np.inf, ub_ineq))

    # --- Bounds ---
    lb_arr = np.zeros(n_vars)
    ub_arr = np.full(n_vars, np.inf)

    for v_idx, var in enumerate(scalable):
        lb_arr[v_idx] = var.lb
        ub_arr[v_idx] = var.ub

    # Deviation variables: >= 0
    for i in range(n_scalable, n_vars):
        lb_arr[i] = 0.0
        ub_arr[i] = np.inf

    from scipy.optimize import Bounds

    bounds = Bounds(lb=lb_arr, ub=ub_arr)

    # --- Integrality ---
    integrality = np.zeros(n_vars, dtype=int)
    for v_idx, var in enumerate(scalable):
        if var.is_discrete:
            integrality[v_idx] = 1

    # --- Solve ---
    result = milp(
        c=c,
        constraints=constraints,
        integrality=integrality,
        bounds=bounds,
        options={"time_limit": 5.0},
    )

    if not result.success:
        logger.warning(
            f"MILP infeasible ({result.message}): falling back to uniform scaling"
        )
        return _fallback_uniform(recipes, daily_targets)

    # --- Extract results ---
    solution = result.x
    factors_per_recipe: list[dict[int, float]] = [{} for _ in range(n_recipes)]

    for v_idx, var in enumerate(scalable):
        val = solution[v_idx]
        if var.is_discrete:
            # Variable IS the final quantity in pieces
            factors_per_recipe[var.recipe_idx][var.ing_idx] = round(val)
        else:
            factors_per_recipe[var.recipe_idx][var.ing_idx] = round(val, 4)

    # Log results
    actual = {k: fixed_total[k] for k in macros_keys}
    for v_idx, var in enumerate(scalable):
        val = solution[v_idx]
        for macro in macros_keys:
            actual[macro] += _macro_contribution(var, macro) * val

    logger.info(
        f"MILP optimizer: {n_recipes} recipes, {n_scalable} ingredient vars, "
        f"result={actual['calories']:.0f}/{actual['protein_g']:.0f}p/"
        f"{actual['fat_g']:.0f}f/{actual['carbs_g']:.0f}c "
        f"(targets={target_cal:.0f}/{target_prot:.0f}p/{target_fat:.0f}f/{target_carbs:.0f}c)"
    )

    return factors_per_recipe


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
        unit = ing.get("unit", "g")
        name = ing.get("name", "")
        factor = _unit_to_multiplier(qty, unit, name)
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


def _fallback_uniform(
    recipes: list[dict], daily_targets: dict
) -> list[dict[int, float]]:
    """Fallback: compute uniform calorie-based scale factor per recipe."""
    target_cal = float(daily_targets.get("calories", 0) or 0)
    recipe_macros = [_extract_recipe_macros(r) for r in recipes]
    total_cal = sum(rm["calories"] for rm in recipe_macros)

    if total_cal > 0:
        uniform = max(0.5, min(3.0, target_cal / total_cal))
    else:
        uniform = 1.0

    result: list[dict[int, float]] = []
    for r_idx, recipe in enumerate(recipes):
        factors = {}
        for i_idx, ing in enumerate(recipe.get("ingredients", [])):
            if ing.get("nutrition_per_100g"):
                role = get_ingredient_role(ing.get("name", ""))
                if role != "fixed":
                    factors[i_idx] = round(uniform, 4)
        result.append(factors)

    return result


def apply_ingredient_scale_factors(
    recipe: dict, scale_factors: dict[int, float]
) -> dict:
    """Apply per-ingredient scale factors and recompute nutrition.

    For continuous items: new_qty = base_qty * scale_factor.
    For discrete items: scale_factor IS the final quantity in pieces.

    Args:
        recipe: Recipe dict with ingredients list.
        scale_factors: Dict mapping ing_idx → scale_factor (or final qty for discrete).

    Returns:
        New recipe dict with scaled ingredients, "scaled_nutrition", and
        "ingredient_scale_factors" keys. Output format matches v1's apply_scale_factor().
    """
    scaled_recipe = dict(recipe)
    ingredients = recipe.get("ingredients", [])
    scaled_ingredients = []

    total_nutrition = {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0}

    for i_idx, ing in enumerate(ingredients):
        new_ing = dict(ing)
        qty = float(ing.get("quantity", 0) or 0)
        unit = ing.get("unit", "g")
        name = ing.get("name", "")
        n = ing.get("nutrition_per_100g")

        if i_idx in scale_factors:
            sf = scale_factors[i_idx]
            discrete = is_discrete_unit(unit)

            if discrete:
                # sf IS the final quantity in pieces
                new_ing["quantity"] = round_quantity_smart(sf, unit, name)
                # Compute nutrition from final quantity
                piece_w = _get_piece_weight(name)
                if piece_w > 0 and n:
                    mult = sf * piece_w / 100.0
                    for macro in total_nutrition:
                        total_nutrition[macro] += float(n.get(macro, 0) or 0) * mult
                elif n:
                    # Unknown piece weight — treat sf as scale factor
                    mult = _unit_to_multiplier(sf, unit, name)
                    for macro in total_nutrition:
                        total_nutrition[macro] += float(n.get(macro, 0) or 0) * mult
            else:
                # sf is a scale factor
                new_qty = qty * sf
                new_ing["quantity"] = round_quantity_smart(new_qty, unit, name)
                if n:
                    mult = _unit_to_multiplier(new_qty, unit, name)
                    for macro in total_nutrition:
                        total_nutrition[macro] += float(n.get(macro, 0) or 0) * mult
        else:
            # Fixed ingredient — unchanged quantity
            new_ing["quantity"] = qty
            if n:
                mult = _unit_to_multiplier(qty, unit, name)
                for macro in total_nutrition:
                    total_nutrition[macro] += float(n.get(macro, 0) or 0) * mult

        scaled_ingredients.append(new_ing)

    scaled_recipe["ingredients"] = scaled_ingredients
    scaled_recipe["scaled_nutrition"] = {
        k: round(v, 2) for k, v in total_nutrition.items()
    }
    scaled_recipe["ingredient_scale_factors"] = scale_factors

    logger.info(
        f"Scaled '{recipe.get('name', '?')}': "
        f"{len(scale_factors)} ingredients adjusted, "
        f"{scaled_recipe['scaled_nutrition']['calories']:.0f} kcal, "
        f"{scaled_recipe['scaled_nutrition']['protein_g']:.0f}g prot, "
        f"{scaled_recipe['scaled_nutrition']['fat_g']:.0f}g fat, "
        f"{scaled_recipe['scaled_nutrition']['carbs_g']:.0f}g carbs"
    )

    return scaled_recipe
