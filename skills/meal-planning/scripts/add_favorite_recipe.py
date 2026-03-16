"""Add a recipe to user's favorites for priority selection in meal plans."""

import json
import logging

logger = logging.getLogger(__name__)


async def execute(**kwargs) -> str:
    """Add a recipe to favorite_recipes.

    Args (via kwargs):
        supabase: Supabase async client
        user_id: User UUID
        recipe_id: Recipe UUID to favorite
        notes: Optional notes about the recipe
    """
    supabase = kwargs["supabase"]
    user_id = kwargs["user_id"]
    recipe_id = kwargs.get("recipe_id")
    notes = kwargs.get("notes")

    if not user_id:
        return json.dumps({"error": "No user_id provided", "code": "NO_USER"})
    if not recipe_id:
        return json.dumps({"error": "No recipe_id provided", "code": "NO_RECIPE_ID"})

    # Verify recipe exists
    recipe = await (
        supabase.table("recipes")
        .select("id, name")
        .eq("id", recipe_id)
        .limit(1)
        .execute()
    )
    if not recipe.data:
        return json.dumps({"error": "Recipe not found", "code": "RECIPE_NOT_FOUND"})

    recipe_name = recipe.data[0]["name"]

    # Check if already favorited (unique constraint user_id + recipe_id)
    existing = await (
        supabase.table("favorite_recipes")
        .select("id")
        .eq("user_id", user_id)
        .eq("recipe_id", recipe_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        return json.dumps(
            {
                "status": "already_exists",
                "recipe_name": recipe_name,
                "recipe_id": recipe_id,
            },
            ensure_ascii=False,
        )

    # Insert favorite
    row: dict = {"user_id": user_id, "recipe_id": recipe_id}
    if notes:
        row["notes"] = notes

    await supabase.table("favorite_recipes").insert(row).execute()

    logger.info(
        f"Added favorite recipe '{recipe_name}' ({recipe_id}) for user {user_id}"
    )
    return json.dumps(
        {"status": "added", "recipe_name": recipe_name, "recipe_id": recipe_id},
        ensure_ascii=False,
    )
