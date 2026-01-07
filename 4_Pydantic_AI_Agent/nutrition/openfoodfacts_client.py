"""
OpenFoodFacts client for local database ingredient matching.

Replaces FatSecret API with PostgreSQL full-text search on local OFF data.
Uses cache-first strategy for performance.
"""

import logging
import unicodedata
from difflib import SequenceMatcher

from supabase import Client

logger = logging.getLogger(__name__)

# Configuration
MIN_CONFIDENCE_THRESHOLD = 0.5


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

            # Update usage count
            supabase.table("ingredient_mapping").update(
                {"usage_count": match["usage_count"] + 1}
            ).eq("id", match["id"]).execute()

            # Calculate nutrition based on quantity
            multiplier = quantity / 100.0 if unit == "g" else 1.0

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
                "confidence_score": best["confidence"],
                "verified": False,
                "usage_count": 1,
            }
        ).execute()
        logger.info(f"Cached match for: {ingredient_name}")
    except Exception as e:
        logger.warning(f"Failed to cache '{ingredient_name}': {e}")

    # Calculate nutrition based on quantity
    multiplier = quantity / 100.0 if unit == "g" else 1.0

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
        "confidence": best["confidence"],
        "cache_hit": False,
    }
