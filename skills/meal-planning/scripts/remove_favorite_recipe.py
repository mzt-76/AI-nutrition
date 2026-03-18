"""Remove a recipe from user's favorites."""

import json
import logging
import re

logger = logging.getLogger(__name__)


async def execute(**kwargs) -> str:
    """Remove a favorite by favorite_id or by recipe_name (fuzzy match).

    Args (via kwargs):
        supabase: Supabase async client
        user_id: User UUID
        favorite_id: Direct UUID of the favorite row
        recipe_name: Recipe name for fuzzy lookup
    """
    supabase = kwargs["supabase"]
    user_id = kwargs["user_id"]
    favorite_id = kwargs.get("favorite_id")
    recipe_name = kwargs.get("recipe_name")

    if not user_id:
        return json.dumps({"error": "No user_id provided", "code": "NO_USER"})
    if not favorite_id and not recipe_name:
        return json.dumps(
            {
                "error": "Provide favorite_id or recipe_name",
                "code": "NO_IDENTIFIER",
            }
        )

    # Resolve favorite_id from recipe_name if needed
    if not favorite_id:
        fav_result = await (
            supabase.table("favorite_recipes")
            .select("id, recipe_id, recipes(name)")
            .eq("user_id", user_id)
            .execute()
        )
        query_words = set(re.sub(r"[^\w\s]", "", recipe_name.lower()).split())
        matches = []
        for fav in fav_result.data or []:
            recipe_data = fav.get("recipes")
            if not recipe_data:
                continue
            name_words = set(
                re.sub(r"[^\w\s]", "", recipe_data.get("name", "").lower()).split()
            )
            if query_words and query_words.issubset(name_words):
                matches.append(
                    {
                        "favorite_id": fav["id"],
                        "recipe_name": recipe_data["name"],
                    }
                )

        if not matches:
            return json.dumps(
                {
                    "error": f"No favorite matching '{recipe_name}'",
                    "code": "NOT_FOUND",
                },
                ensure_ascii=False,
            )
        if len(matches) > 1:
            return json.dumps(
                {"status": "ambiguous", "matches": matches}, ensure_ascii=False
            )

        favorite_id = matches[0]["favorite_id"]
        resolved_name = matches[0]["recipe_name"]
    else:
        resolved_name = None

    # Verify ownership
    existing = await (
        supabase.table("favorite_recipes")
        .select("id, user_id, recipe_id, recipes(name)")
        .eq("id", favorite_id)
        .execute()
    )
    if not existing.data:
        return json.dumps({"error": "Favorite not found", "code": "NOT_FOUND"})
    fav_row = existing.data[0]
    if fav_row.get("user_id") != user_id:
        return json.dumps({"error": "Not your favorite", "code": "NOT_OWNER"})

    recipe_display_name = resolved_name or (fav_row.get("recipes", {}) or {}).get(
        "name", "unknown"
    )

    # Delete
    await supabase.table("favorite_recipes").delete().eq("id", favorite_id).execute()

    logger.info(
        f"Removed favorite '{recipe_display_name}' ({favorite_id}) for user {user_id}"
    )
    return json.dumps(
        {"status": "removed", "recipe_name": recipe_display_name},
        ensure_ascii=False,
    )
