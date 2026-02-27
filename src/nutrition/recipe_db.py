"""Recipe database operations for meal planning.

Provides CRUD operations for the recipes table in Supabase.
All functions are async and return structured results.

Allergen filtering is done in Python after DB retrieval (not via Supabase array operators)
to match codebase patterns and avoid client compatibility risk.
"""

import logging
from datetime import datetime, timezone

from supabase import Client

from src.nutrition.openfoodfacts_client import normalize_ingredient_name

logger = logging.getLogger(__name__)

# Known compound foods where a substring means a different product
COMPOUND_FOOD_EXCEPTIONS: dict[str, list[str]] = {
    "fromage": ["fromage blanc", "fromage frais"],
}


def _contains_disliked(text: str, disliked: str) -> bool:
    """Check if text contains disliked food, respecting compound exceptions."""
    text_lower = text.lower()
    if disliked not in text_lower:
        return False
    # If the match is actually a different compound food, don't exclude
    for exception in COMPOUND_FOOD_EXCEPTIONS.get(disliked, []):
        if exception in text_lower:
            return False
    return True


async def search_recipes(
    supabase: Client,
    meal_type: str,
    exclude_allergens: list[str] | None = None,
    exclude_recipe_ids: list[str] | None = None,
    exclude_ingredients: list[str] | None = None,
    diet_type: str = "omnivore",
    cuisine_types: list[str] | None = None,
    max_prep_time: int | None = None,
    calorie_range: tuple[int, int] | None = None,
    limit: int = 10,
) -> list[dict]:
    """Search recipes with filtering constraints.

    Queries the recipes table with basic filters, then applies allergen,
    disliked-food, and variety filtering in Python.

    Args:
        supabase: Supabase client
        meal_type: "petit-dejeuner", "dejeuner", "diner", "collation"
        exclude_allergens: Allergen tags to exclude (zero tolerance)
        exclude_recipe_ids: Recipe IDs already used this week (variety)
        exclude_ingredients: Ingredient keywords to exclude (e.g. disliked foods).
            Matches against recipe name AND individual ingredient names.
        diet_type: Diet filter (e.g., "omnivore", "végétarien", "vegan")
        cuisine_types: Preferred cuisine types (None = no filter)
        max_prep_time: Maximum prep time in minutes (None = no filter)
        calorie_range: (min, max) calorie range for the meal slot (None = no filter)
        limit: Max results after Python filtering

    Returns:
        List of matching recipe dicts, ordered by created_at ASC (neutral;
        callers re-sort by variety score)

    Example:
        >>> recipes = await search_recipes(supabase, "dejeuner", exclude_ingredients=["fromage"])
        >>> all("fromage" not in r.get("name", "").lower() for r in recipes)
        True
    """
    logger.info(
        f"Searching recipes: meal_type={meal_type}, diet_type={diet_type}, "
        f"exclude_allergens={exclude_allergens}"
    )

    try:
        query = supabase.table("recipes").select("*").eq("meal_type", meal_type)

        # Apply diet_type filter (omnivore is a superset — also returns other diet types)
        if diet_type != "omnivore":
            query = query.eq("diet_type", diet_type)

        # Apply prep_time filter if specified
        if max_prep_time is not None:
            query = query.lte("prep_time_minutes", max_prep_time)

        # Apply calorie range filter if specified
        if calorie_range is not None:
            min_cal, max_cal = calorie_range
            query = query.gte("calories_per_serving", min_cal).lte(
                "calories_per_serving", max_cal
            )

        # Fetch more than needed to allow Python-side filtering
        fetch_limit = (limit * 3) + len(exclude_recipe_ids or []) + 10
        response = query.order("created_at", desc=False).limit(fetch_limit).execute()
        results = response.data or []

        # Python-side filtering: allergens (zero tolerance)
        if exclude_allergens:
            normalized_allergens = set(a.lower().strip() for a in exclude_allergens)
            results = [
                r
                for r in results
                if not set(tag.lower() for tag in r.get("allergen_tags", []))
                & normalized_allergens
            ]

        # Python-side filtering: disliked foods (check name + ingredient names)
        if exclude_ingredients:
            normalized_disliked = [d.lower().strip() for d in exclude_ingredients]
            filtered = []
            for r in results:
                recipe_name = r.get("name", "").lower()
                ingredient_names = [
                    ing.get("name", "").lower() for ing in r.get("ingredients", [])
                ]
                has_disliked = any(
                    _contains_disliked(recipe_name, disliked)
                    or any(
                        _contains_disliked(ing_name, disliked)
                        for ing_name in ingredient_names
                    )
                    for disliked in normalized_disliked
                )
                if not has_disliked:
                    filtered.append(r)
            excluded_count = len(results) - len(filtered)
            if excluded_count > 0:
                logger.info(
                    f"Excluded {excluded_count} recipes containing disliked ingredients"
                )
            results = filtered

        # Python-side filtering: variety (exclude already-used recipe IDs)
        if exclude_recipe_ids:
            excluded_set = set(exclude_recipe_ids)
            results = [r for r in results if r.get("id") not in excluded_set]

        final = results[:limit]
        logger.info(f"Found {len(final)} recipes for meal_type={meal_type}")
        return final

    except Exception as e:
        logger.error(f"Error searching recipes: {e}", exc_info=True)
        return []


async def get_recipe_by_id(supabase: Client, recipe_id: str) -> dict | None:
    """Fetch a single recipe by its UUID.

    Args:
        supabase: Supabase client
        recipe_id: Recipe UUID

    Returns:
        Recipe dict or None if not found

    Example:
        >>> recipe = await get_recipe_by_id(supabase, "some-uuid")
        >>> recipe["name"] if recipe else None
        "Omelette protéinée"
    """
    try:
        response = (
            supabase.table("recipes").select("*").eq("id", recipe_id).limit(1).execute()
        )
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching recipe {recipe_id}: {e}", exc_info=True)
        return None


async def save_recipe(supabase: Client, recipe: dict) -> dict:
    """Save a new recipe to the database.

    Normalizes the name before saving for deduplication.

    Args:
        supabase: Supabase client
        recipe: Recipe dict. Must have at minimum: name, meal_type,
                ingredients, instructions, calories_per_serving,
                protein_g_per_serving, carbs_g_per_serving, fat_g_per_serving

    Returns:
        Saved recipe dict with generated UUID and timestamps

    Raises:
        ValueError: If required fields are missing
        Exception: If database insert fails

    Example:
        >>> saved = await save_recipe(supabase, {"name": "Test", "meal_type": "dejeuner", ...})
        >>> "id" in saved
        True
    """
    required_fields = [
        "name",
        "meal_type",
        "ingredients",
        "instructions",
        "calories_per_serving",
        "protein_g_per_serving",
        "carbs_g_per_serving",
        "fat_g_per_serving",
    ]
    for field in required_fields:
        if field not in recipe:
            raise ValueError(f"Missing required field: {field}")

    # Normalize name for deduplication
    recipe_to_save = dict(recipe)
    recipe_to_save["name_normalized"] = normalize_ingredient_name(recipe["name"])

    logger.info(f"Saving recipe: {recipe['name']} (meal_type={recipe['meal_type']})")

    response = supabase.table("recipes").insert(recipe_to_save).execute()

    if not response.data:
        raise Exception(f"Failed to insert recipe: {recipe['name']}")

    saved = response.data[0]
    logger.info(f"Recipe saved with ID: {saved.get('id')}")
    return saved


async def increment_usage(supabase: Client, recipe_id: str) -> None:
    """Increment usage_count for a recipe.

    Args:
        supabase: Supabase client
        recipe_id: Recipe UUID

    Example:
        >>> await increment_usage(supabase, "some-uuid")
    """
    try:
        # Fetch current count first (Supabase SDK doesn't support raw SQL increment)
        current = await get_recipe_by_id(supabase, recipe_id)
        if current is None:
            logger.warning(f"Recipe {recipe_id} not found for usage increment")
            return

        new_count = current.get("usage_count", 0) + 1
        supabase.table("recipes").update(
            {
                "usage_count": new_count,
                "last_used_date": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", recipe_id).execute()
        logger.debug(f"Recipe {recipe_id} usage_count → {new_count}")
    except Exception as e:
        logger.error(f"Error incrementing usage for {recipe_id}: {e}", exc_info=True)


async def count_recipes_by_meal_type(supabase: Client) -> dict:
    """Return count of recipes per meal_type for coverage check.

    Uses a single DB query and groups in Python — avoids 4 round-trips.

    Args:
        supabase: Supabase client

    Returns:
        Dict mapping meal_type → count. Example:
        {"petit-dejeuner": 30, "dejeuner": 28, "diner": 32, "collation": 15}

    Example:
        >>> counts = await count_recipes_by_meal_type(supabase)
        >>> counts.get("dejeuner", 0) >= 10  # Minimum for system to work well
        True
    """
    meal_types = ["petit-dejeuner", "dejeuner", "diner", "collation"]
    counts = {mt: 0 for mt in meal_types}

    try:
        response = supabase.table("recipes").select("meal_type").execute()
        for row in response.data or []:
            mt = row.get("meal_type", "")
            if mt in counts:
                counts[mt] += 1
    except Exception as e:
        logger.error(f"Error counting recipes by meal_type: {e}", exc_info=True)

    logger.info(f"Recipe DB coverage: {counts}")
    return counts


# ---------------------------------------------------------------------------
# Scoring functions for recipe variety
# ---------------------------------------------------------------------------

# Freshness decay caps at this many days (30+ days = same as never used)
FRESHNESS_CAP_DAYS = 30.0


def score_macro_fit(recipe: dict, target: dict) -> float:
    """Score how well recipe's macro RATIOS match target ratios.

    Compares protein/cal, carbs/cal, fat/cal ratios of recipe vs target.
    Lower score = better fit. Protein match is weighted 2x.

    Uses Mifflin-St Jeor-aligned macro ratio comparison.

    Args:
        recipe: Recipe dict with calories_per_serving, protein_g_per_serving, etc.
        target: Meal slot target dict with target_calories, target_protein_g, etc.

    Returns:
        Float score >= 0. Lower is better.
    """
    recipe_cal = recipe.get("calories_per_serving", 1) or 1
    recipe_prot_ratio = recipe.get("protein_g_per_serving", 0) * 4 / recipe_cal
    recipe_carb_ratio = recipe.get("carbs_g_per_serving", 0) * 4 / recipe_cal
    recipe_fat_ratio = recipe.get("fat_g_per_serving", 0) * 9 / recipe_cal

    target_cal = target.get("target_calories", 1) or 1
    target_prot_ratio = target.get("target_protein_g", 0) * 4 / target_cal
    target_carb_ratio = target.get("target_carbs_g", 0) * 4 / target_cal
    target_fat_ratio = target.get("target_fat_g", 0) * 9 / target_cal

    score = (
        2 * abs(recipe_prot_ratio - target_prot_ratio)
        + abs(recipe_carb_ratio - target_carb_ratio)
        + abs(recipe_fat_ratio - target_fat_ratio)
    )
    return score


def score_recipe_variety(
    recipe: dict,
    meal_target: dict,
    preferred_cuisines: list[str] | None = None,
    now: datetime | None = None,
) -> float:
    """Multi-factor recipe score — higher is better (range 0.0–1.0).

    Combines macro fit, temporal freshness, cuisine preference, and usage count
    into a single score for ranking recipe candidates.

    Args:
        recipe: Recipe dict from DB
        meal_target: Meal slot target dict with target_calories, target_protein_g, etc.
        preferred_cuisines: User's preferred cuisine types (None = no bonus)
        now: Current datetime (injectable for tests). Defaults to UTC now.

    Returns:
        Float score in [0.0, 1.0]. Higher is better.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Factor 1: Macro fit (weight 0.40) — invert so higher = better
    macro_raw = score_macro_fit(recipe, meal_target)
    macro_score = 1.0 / (1.0 + macro_raw)

    # Factor 2: Freshness (weight 0.30)
    last_used = recipe.get("last_used_date")
    if last_used is None:
        freshness_score = 1.0
    else:
        if isinstance(last_used, str):
            # Parse ISO datetime string
            last_used_dt = datetime.fromisoformat(last_used.replace("Z", "+00:00"))
        else:
            last_used_dt = last_used
        # Ensure both are offset-aware for subtraction
        if last_used_dt.tzinfo is None:
            last_used_dt = last_used_dt.replace(tzinfo=timezone.utc)
        days_since = (now - last_used_dt).total_seconds() / 86400.0
        freshness_score = min(days_since / FRESHNESS_CAP_DAYS, 1.0)

    # Factor 3: Cuisine preference (weight 0.20)
    if preferred_cuisines and recipe.get("cuisine_type") in preferred_cuisines:
        cuisine_score = 1.0
    else:
        cuisine_score = 0.0

    # Factor 4: Usage count (weight 0.10) — less used = better
    usage_count = recipe.get("usage_count", 0) or 0
    usage_score = 1.0 / (1.0 + usage_count)

    return (
        0.40 * macro_score
        + 0.30 * freshness_score
        + 0.20 * cuisine_score
        + 0.10 * usage_score
    )
