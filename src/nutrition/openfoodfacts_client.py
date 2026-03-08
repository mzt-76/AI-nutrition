"""
OpenFoodFacts client for local database ingredient matching.

Replaces FatSecret API with PostgreSQL full-text search on local OFF data.
Uses cache-first strategy for performance.
"""

import asyncio
import logging
import unicodedata
from difflib import SequenceMatcher

from supabase import Client

logger = logging.getLogger(__name__)

# Configuration
MIN_CONFIDENCE_THRESHOLD = 0.5

# Densities for ml → g conversion
_ML_TO_G_DENSITY: dict[str, float] = {
    "huile d'olive": 0.92,
    "huile": 0.92,
    "lait": 1.03,
    "lait de coco": 0.97,
    "crème": 1.01,
    "miel": 1.42,
    "eau": 1.0,
}
_DEFAULT_ML_DENSITY = 1.0


def _ml_to_g(quantity_ml: float, ingredient_name: str) -> float:
    """Convert ml to grams using ingredient-specific density."""
    name_lower = ingredient_name.lower()
    for key, density in _ML_TO_G_DENSITY.items():
        if key in name_lower:
            return quantity_ml * density
    return quantity_ml * _DEFAULT_ML_DENSITY


# Average weights per piece (grams) for common discrete-unit ingredients
_PIECE_WEIGHTS: dict[str, float] = {
    "oeuf": 60, "oeufs": 60, "œuf": 60, "œufs": 60,
    "oeuf fermier": 60, "oeufs fermiers": 60, "œufs fermiers": 60,
    "banane": 120, "pomme": 180, "orange": 200, "kiwi": 75,
    "tomate": 150, "avocat": 150, "oignon": 150, "gousse d'ail": 5,
    "carotte": 120, "courgette": 200, "poivron": 150,
    "tranche de pain": 30, "tranche de pain complet": 35,
    "tortilla": 60, "muffin anglais": 57,
    "filet de poulet": 150, "escalope de dinde": 130,
    "pavé de saumon": 150, "filet de cabillaud": 130,
}


def _unit_to_multiplier(quantity: float, unit: str, ingredient_name: str) -> float:
    """Convert quantity+unit to a per-100g multiplier for nutrition calculation."""
    if unit == "g":
        return quantity / 100.0
    if unit == "ml":
        return _ml_to_g(quantity, ingredient_name) / 100.0
    if unit == "kg":
        return (quantity * 1000.0) / 100.0
    if unit == "l":
        return _ml_to_g(quantity * 1000.0, ingredient_name) / 100.0
    # Discrete units — look up weight per piece
    name_lower = ingredient_name.lower().strip()
    for key, weight_g in _PIECE_WEIGHTS.items():
        if key in name_lower:
            return (quantity * weight_g) / 100.0
    # Unknown piece — assume quantity IS in grams (safest fallback)
    return quantity / 100.0


def normalize_ingredient_name(name: str) -> str:
    """
    Normalize ingredient name for matching.

    Args:
        name: Raw ingredient name

    Returns:
        Normalized name (lowercase, no accents)

    Example:
        >>> normalize_ingredient_name("Yaourt Grec")
        "yaourt grec"
        >>> normalize_ingredient_name("Café")
        "cafe"
    """
    # Remove accents
    normalized = unicodedata.normalize("NFD", name)
    without_accents = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return without_accents.lower().strip()


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two strings.

    Args:
        text1: First string
        text2: Second string

    Returns:
        Similarity score (0.0 to 1.0)

    Example:
        >>> calculate_similarity("poulet", "poulet rôti")
        0.75
    """
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


async def search_food_local(
    query: str, supabase: Client, max_results: int = 5
) -> list[dict]:
    """
    Search OpenFoodFacts database using RPC function.

    Args:
        query: Search query (ingredient name)
        supabase: Supabase client
        max_results: Maximum results to return

    Returns:
        List of matching products with nutrition data

    Example:
        >>> results = await search_food_local("poulet", supabase)
        >>> len(results) > 0
        True
        >>> results[0]["confidence"] > 0.5
        True

    References:
        Uses PostgreSQL full-text search with trigram similarity
    """
    try:
        result = supabase.rpc(
            "search_openfoodfacts",
            {"search_query": query, "max_results": max_results},
        ).execute()

        if not result.data:
            logger.info(f"No results for query: {query}")
            return []

        # Transform to standard format
        products = []
        for row in result.data:
            products.append(
                {
                    "code": row["code"],
                    "name": row["product_name_fr"] or row["product_name"],
                    "calories_per_100g": float(row["calories_per_100g"]),
                    "protein_g_per_100g": float(row["protein_g_per_100g"]),
                    "carbs_g_per_100g": float(row["carbs_g_per_100g"]),
                    "fat_g_per_100g": float(row["fat_g_per_100g"]),
                    "confidence": float(row["similarity_score"]),
                }
            )

        logger.info(f"Found {len(products)} results for: {query}")
        return products

    except Exception as e:
        logger.error(f"Search failed for '{query}': {e}", exc_info=True)
        return []


async def match_ingredient(
    ingredient_name: str, quantity: float, unit: str, supabase: Client
) -> dict:
    """
    Match ingredient with cache-first strategy.

    Args:
        ingredient_name: Ingredient to match
        quantity: Amount
        unit: Unit of measurement (e.g., "g", "ml")
        supabase: Supabase client

    Returns:
        Dict with matched nutrition data and metadata

    Example:
        >>> result = await match_ingredient("poulet", 150, "g", supabase)
        >>> result["calories"] > 0
        True
        >>> result["confidence"] > 0.5
        True

    References:
        Cache pattern from fatsecret_client.py (lines 86-100)
    """
    normalized = normalize_ingredient_name(ingredient_name)

    # Step 1: Check cache
    try:
        cached = (
            supabase.table("ingredient_mapping")
            .select("*")
            .eq("ingredient_name_normalized", normalized)
            .execute()
        )

        if cached.data:
            match = cached.data[0]
            logger.info(f"Cache hit for: {ingredient_name}")

            # Calculate nutrition based on quantity
            multiplier = _unit_to_multiplier(quantity, unit, ingredient_name)

            return {
                "ingredient_name": ingredient_name,
                "matched_name": match["openfoodfacts_name"],
                "openfoodfacts_code": match["openfoodfacts_code"],
                "quantity": quantity,
                "unit": unit,
                "calories": round(match["calories_per_100g"] * multiplier, 1),
                "protein_g": round(match["protein_g_per_100g"] * multiplier, 1),
                "carbs_g": round(match["carbs_g_per_100g"] * multiplier, 1),
                "fat_g": round(match["fat_g_per_100g"] * multiplier, 1),
                "nutrition_per_100g": {
                    "calories": match["calories_per_100g"],
                    "protein_g": match["protein_g_per_100g"],
                    "carbs_g": match["carbs_g_per_100g"],
                    "fat_g": match["fat_g_per_100g"],
                },
                "confidence": match["confidence_score"],
                "cache_hit": True,
            }

    except Exception as e:
        logger.warning(f"Cache check failed for '{ingredient_name}': {e}")

    # Step 2: Search database
    results = await search_food_local(ingredient_name, supabase)

    if not results or results[0]["confidence"] < MIN_CONFIDENCE_THRESHOLD:
        logger.warning(
            f"No confident match for '{ingredient_name}' "
            f"(best score: {results[0]['confidence'] if results else 0:.2f})"
        )
        return {
            "ingredient_name": ingredient_name,
            "matched_name": None,
            "openfoodfacts_code": None,
            "quantity": quantity,
            "unit": unit,
            "calories": 0,
            "protein_g": 0,
            "carbs_g": 0,
            "fat_g": 0,
            "confidence": 0,
            "cache_hit": False,
            "error": "No confident match found",
        }

    best = results[0]
    logger.info(
        f"Matched '{ingredient_name}' -> '{best['name']}' (confidence: {best['confidence']:.2f})"
    )

    # Step 3: Cache the result
    try:
        supabase.table("ingredient_mapping").insert(
            {
                "ingredient_name": ingredient_name,
                "ingredient_name_normalized": normalized,
                "openfoodfacts_code": best["code"],
                "openfoodfacts_name": best["name"],
                "calories_per_100g": best["calories_per_100g"],
                "protein_g_per_100g": best["protein_g_per_100g"],
                "carbs_g_per_100g": best["carbs_g_per_100g"],
                "fat_g_per_100g": best["fat_g_per_100g"],
                "confidence_score": min(best["confidence"], 1.0),
                "verified": False,
                "usage_count": 1,
            }
        ).execute()
        logger.info(f"Cached match for: {ingredient_name}")
    except Exception as e:
        logger.warning(f"Failed to cache '{ingredient_name}': {e}")

    # Calculate nutrition based on quantity
    multiplier = _unit_to_multiplier(quantity, unit, ingredient_name)

    return {
        "ingredient_name": ingredient_name,
        "matched_name": best["name"],
        "openfoodfacts_code": best["code"],
        "quantity": quantity,
        "unit": unit,
        "calories": round(best["calories_per_100g"] * multiplier, 1),
        "protein_g": round(best["protein_g_per_100g"] * multiplier, 1),
        "carbs_g": round(best["carbs_g_per_100g"] * multiplier, 1),
        "fat_g": round(best["fat_g_per_100g"] * multiplier, 1),
        "nutrition_per_100g": {
            "calories": best["calories_per_100g"],
            "protein_g": best["protein_g_per_100g"],
            "carbs_g": best["carbs_g_per_100g"],
            "fat_g": best["fat_g_per_100g"],
        },
        "confidence": best["confidence"],
        "cache_hit": False,
    }


async def off_validate_recipe(recipe: dict, supabase: Client) -> dict:
    """Validate and enrich a recipe with real OFF nutrition data.

    Matches all ingredients in parallel via OpenFoodFacts, stores per-ingredient
    nutrition_per_100g, and recalculates recipe-level macros from the real data.

    Args:
        recipe: Recipe dict with ingredients [{name, quantity, unit}]
        supabase: Supabase client

    Returns:
        Enriched recipe dict with:
        - Each ingredient gets nutrition_per_100g + off_code + confidence
        - Recipe-level calories/protein/carbs/fat_per_serving updated from OFF
        - off_validated = True if ALL ingredients matched

    References:
        Uses match_ingredient() with cache-first strategy
    """
    ingredients = recipe.get("ingredients", [])
    if not ingredients:
        recipe["off_validated"] = False
        return recipe

    valid_ingredients = [
        ing for ing in ingredients
        if ing.get("name") and ing.get("quantity")
    ]

    if not valid_ingredients:
        recipe["off_validated"] = False
        return recipe

    # Match all ingredients in parallel
    async def _match_one(ing: dict) -> dict | None:
        try:
            return await match_ingredient(
                ingredient_name=ing["name"],
                quantity=ing.get("quantity", 0),
                unit=ing.get("unit", "g"),
                supabase=supabase,
            )
        except Exception as e:
            logger.warning(f"OFF match failed for '{ing.get('name')}': {e}")
            return None

    results = await asyncio.gather(*[_match_one(ing) for ing in valid_ingredients])

    # Enrich ingredients and sum macros
    totals = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    all_matched = True

    for ing, result in zip(valid_ingredients, results):
        if result is None or result.get("matched_name") is None:
            all_matched = False
            continue

        # Store per-100g nutrition for future scaling (avoids re-querying OFF)
        quantity = ing.get("quantity", 0)
        unit = ing.get("unit", "g")
        multiplier = _unit_to_multiplier(quantity, unit, ing["name"])
        if multiplier > 0:
            # Back-calculate per-100g from the matched result
            ing["nutrition_per_100g"] = {
                "calories": round(result["calories"] / multiplier, 1) if multiplier else 0,
                "protein_g": round(result["protein_g"] / multiplier, 1) if multiplier else 0,
                "carbs_g": round(result["carbs_g"] / multiplier, 1) if multiplier else 0,
                "fat_g": round(result["fat_g"] / multiplier, 1) if multiplier else 0,
            }
        ing["off_code"] = result.get("openfoodfacts_code")
        ing["confidence"] = result.get("confidence", 0)

        totals["calories"] += result.get("calories", 0)
        totals["protein_g"] += result.get("protein_g", 0)
        totals["carbs_g"] += result.get("carbs_g", 0)
        totals["fat_g"] += result.get("fat_g", 0)

    # Update recipe-level macros from real OFF data
    if totals["calories"] > 0:
        recipe["calories_per_serving"] = round(totals["calories"], 1)
        recipe["protein_g_per_serving"] = round(totals["protein_g"], 1)
        recipe["carbs_g_per_serving"] = round(totals["carbs_g"], 1)
        recipe["fat_g_per_serving"] = round(totals["fat_g"], 1)

    recipe["off_validated"] = all_matched
    logger.info(
        f"OFF validate '{recipe.get('name', '?')}': "
        f"{totals['calories']:.0f} kcal, validated={all_matched}"
    )
    return recipe
