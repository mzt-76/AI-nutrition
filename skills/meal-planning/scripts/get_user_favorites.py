"""List and search user's favorite recipes."""

import json
import logging
import re

logger = logging.getLogger(__name__)


async def execute(**kwargs) -> str:
    """List user favorites, with optional fuzzy name filter.

    Args (via kwargs):
        supabase: Supabase async client
        user_id: User UUID
        name: Optional name filter (fuzzy word-based matching)
    """
    supabase = kwargs["supabase"]
    user_id = kwargs["user_id"]
    name = kwargs.get("name")

    if not user_id:
        return json.dumps({"error": "No user_id provided", "code": "NO_USER"})

    result = await (
        supabase.table("favorite_recipes")
        .select("*, recipes(*)")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    favorites = []
    for fav in result.data or []:
        recipe_data = fav.get("recipes")
        if not recipe_data:
            continue
        favorites.append(
            {
                "favorite_id": fav["id"],
                "recipe_id": fav["recipe_id"],
                "notes": fav.get("notes"),
                "created_at": fav.get("created_at"),
                "recipe_name": recipe_data.get("name"),
                "meal_type": recipe_data.get("meal_type"),
                "calories": recipe_data.get("calories"),
                "protein_g": recipe_data.get("protein_g"),
                "carbs_g": recipe_data.get("carbs_g"),
                "fat_g": recipe_data.get("fat_g"),
            }
        )

    # Apply fuzzy name filter if provided
    if name:
        query_words = set(re.sub(r"[^\w\s]", "", name.lower()).split())
        favorites = [
            f
            for f in favorites
            if query_words
            and query_words.issubset(
                set(
                    re.sub(r"[^\w\s]", "", (f.get("recipe_name") or "").lower()).split()
                )
            )
        ]

    logger.info(
        f"User {user_id}: {len(favorites)} favorites"
        + (f" matching '{name}'" if name else "")
    )
    return json.dumps(
        {"favorites": favorites, "count": len(favorites)}, ensure_ascii=False
    )
