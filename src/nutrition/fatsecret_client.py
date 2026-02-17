"""FatSecret Platform API Client with OAuth 2.0 Authentication.

This module provides:
1. OAuth 2.0 authentication with token caching
2. Food search and nutrition lookup
3. Fuzzy string matching for ingredient mapping
4. Cache-aware ingredient matching with Supabase

References:
    - FatSecret OAuth 2.0: https://platform.fatsecret.com/docs/guides/authentication/oauth2
    - FatSecret REST API: https://platform.fatsecret.com/api/Default.aspx?screen=rapiref2
"""

import asyncio
import base64
import logging
import unicodedata
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

import httpx
from supabase import Client

logger = logging.getLogger(__name__)

# API Endpoints
FATSECRET_TOKEN_URL = "https://oauth.fatsecret.com/connect/token"
FATSECRET_API_URL = "https://platform.fatsecret.com/rest/server.api"

# Token expiry buffer (refresh 60s before actual expiry)
TOKEN_EXPIRY_BUFFER_SECONDS = 60

# Fuzzy matching thresholds
MIN_CONFIDENCE_SCORE = 0.5  # Minimum similarity score to accept a match
KEYWORD_BONUS_PER_MATCH = 0.1  # Bonus for each matching keyword


class FatSecretAuthManager:
    """Manages OAuth 2.0 authentication for FatSecret Platform API.

    Implements token caching with automatic refresh before expiry.
    Thread-safe with asyncio.Lock().

    Attributes:
        client_id: FatSecret API client ID
        client_secret: FatSecret API client secret
    """

    def __init__(self, client_id: str, client_secret: str) -> None:
        """Initialize auth manager with credentials.

        Args:
            client_id: FatSecret Platform API client ID
            client_secret: FatSecret Platform API client secret
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._token_expiry: datetime | None = None
        self._lock = asyncio.Lock()

    async def get_token(self, http_client: httpx.AsyncClient) -> str:
        """Get cached or request new access token.

        Args:
            http_client: Async HTTP client for API requests

        Returns:
            Valid access token string

        Raises:
            httpx.HTTPStatusError: If token request fails

        Example:
            >>> auth = FatSecretAuthManager(client_id, client_secret)
            >>> async with httpx.AsyncClient() as client:
            ...     token = await auth.get_token(client)
        """
        async with self._lock:
            now = datetime.now()

            # Check if token is valid (exists and not expired)
            if self._token and self._token_expiry:
                if now < self._token_expiry - timedelta(
                    seconds=TOKEN_EXPIRY_BUFFER_SECONDS
                ):
                    logger.info("Using cached FatSecret token")
                    return self._token

            # Request new token
            logger.info("Requesting new FatSecret token")
            self._token = await self._request_new_token(http_client)
            # FatSecret tokens are valid for 24 hours (86400 seconds)
            self._token_expiry = now + timedelta(seconds=86400)
            return self._token

    async def _request_new_token(self, http_client: httpx.AsyncClient) -> str:
        """Request new OAuth 2.0 token from FatSecret.

        Args:
            http_client: Async HTTP client for API requests

        Returns:
            Access token string

        Raises:
            httpx.HTTPStatusError: If request fails (401, 403, etc.)

        References:
            - OAuth 2.0 Client Credentials Grant
            - Basic Authentication with base64 encoded client_id:client_secret
        """
        # Encode credentials for Basic auth
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        try:
            response = await http_client.post(
                FATSECRET_TOKEN_URL,
                headers={
                    "Authorization": f"Basic {encoded_credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "client_credentials",
                    "scope": "basic",
                },
                timeout=10.0,
            )
            response.raise_for_status()

            data = response.json()
            token = data["access_token"]
            logger.info("✅ FatSecret token obtained successfully")
            return token

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error(
                    "❌ FatSecret OAuth failed: Invalid credentials", exc_info=True
                )
            elif e.response.status_code == 403:
                logger.error(
                    "❌ FatSecret OAuth failed: IP not whitelisted", exc_info=True
                )
            else:
                logger.error(f"❌ FatSecret OAuth failed: {e}", exc_info=True)
            raise


async def search_food(
    query: str,
    token: str,
    http_client: httpx.AsyncClient,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Search FatSecret food database.

    Args:
        query: Search query (e.g., "chicken breast")
        token: Valid FatSecret access token
        http_client: Async HTTP client for API requests
        max_results: Maximum number of results to return

    Returns:
        List of food items with food_id, food_name, food_description

    Raises:
        httpx.HTTPStatusError: If API request fails

    Example:
        >>> results = await search_food("chicken breast", token, client)
        >>> print(results[0]["food_name"])
        "Chicken Breast, Skinless"

    References:
        - FatSecret foods.search method
        - Response can be dict (1 result) or list (2+ results)
    """
    try:
        response = await http_client.get(
            FATSECRET_API_URL,
            params={
                "method": "foods.search",
                "search_expression": query,
                "format": "json",
                "max_results": max_results,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        response.raise_for_status()

        data = response.json()

        # Handle API quirk: dict if 1 result, list if 2+
        if "foods" not in data or "food" not in data["foods"]:
            logger.warning(f"No results found for query: {query}")
            return []

        foods = data["foods"]["food"]

        # Normalize to list
        if isinstance(foods, dict):
            foods = [foods]

        logger.info(f"Found {len(foods)} results for query: {query}")
        return foods[:max_results]

    except httpx.HTTPStatusError as e:
        logger.error(
            f"❌ FatSecret search failed for query '{query}': {e}", exc_info=True
        )
        raise


async def get_food_nutrition(
    food_id: str,
    token: str,
    http_client: httpx.AsyncClient,
) -> dict[str, Any]:
    """Get detailed nutrition data for a specific food.

    Args:
        food_id: FatSecret food ID
        token: Valid FatSecret access token
        http_client: Async HTTP client for API requests

    Returns:
        Dict with food_id, food_name, and per-100g nutrition data

    Raises:
        httpx.HTTPStatusError: If API request fails
        ValueError: If no 100g serving found and conversion fails

    Example:
        >>> nutrition = await get_food_nutrition("12345", token, client)
        >>> print(nutrition["calories_per_100g"])
        165.0

    References:
        - FatSecret food.get method
        - Servings array contains various serving sizes
        - We prioritize 100g serving, convert others if needed
    """
    try:
        response = await http_client.get(
            FATSECRET_API_URL,
            params={
                "method": "food.get",
                "food_id": food_id,
                "format": "json",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        response.raise_for_status()

        data = response.json()
        food = data["food"]

        # Extract servings array
        servings = food["servings"]["serving"]
        if isinstance(servings, dict):
            servings = [servings]

        # Find 100g serving or convert first serving
        per_100g_serving = None
        for serving in servings:
            if (
                serving.get("metric_serving_unit") == "g"
                and float(serving.get("metric_serving_amount", 0)) == 100
            ):
                per_100g_serving = serving
                break

        if not per_100g_serving:
            # Convert first serving to per 100g
            first_serving = servings[0]
            serving_amount = float(first_serving.get("metric_serving_amount", 100))

            if serving_amount == 0:
                raise ValueError(f"Invalid serving amount for food_id {food_id}")

            conversion_factor = 100 / serving_amount

            per_100g_serving = {
                "calories": float(first_serving.get("calories", 0)) * conversion_factor,
                "protein": float(first_serving.get("protein", 0)) * conversion_factor,
                "carbohydrate": float(first_serving.get("carbohydrate", 0))
                * conversion_factor,
                "fat": float(first_serving.get("fat", 0)) * conversion_factor,
            }
            logger.info(
                f"Converted {serving_amount}g serving to per 100g for food_id {food_id}"
            )
        else:
            per_100g_serving = {
                "calories": float(per_100g_serving.get("calories", 0)),
                "protein": float(per_100g_serving.get("protein", 0)),
                "carbohydrate": float(per_100g_serving.get("carbohydrate", 0)),
                "fat": float(per_100g_serving.get("fat", 0)),
            }

        result = {
            "food_id": food_id,
            "food_name": food["food_name"],
            "calories_per_100g": round(per_100g_serving["calories"], 2),
            "protein_g_per_100g": round(per_100g_serving["protein"], 2),
            "carbs_g_per_100g": round(per_100g_serving["carbohydrate"], 2),
            "fat_g_per_100g": round(per_100g_serving["fat"], 2),
        }

        logger.info(f"✅ Retrieved nutrition for {food['food_name']} (ID: {food_id})")
        return result

    except httpx.HTTPStatusError as e:
        logger.error(
            f"❌ FatSecret get nutrition failed for food_id '{food_id}': {e}",
            exc_info=True,
        )
        raise


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate string similarity ratio.

    Args:
        text1: First string
        text2: Second string

    Returns:
        Similarity score 0.0-1.0 (1.0 = exact match)

    Example:
        >>> calculate_similarity("chicken breast", "Chicken Breast, Skinless")
        0.76
    """
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def normalize_ingredient_name(name: str) -> str:
    """Normalize ingredient name for fuzzy matching.

    Args:
        name: Original ingredient name

    Returns:
        Normalized name: lowercase, no accents, trimmed spaces

    Example:
        >>> normalize_ingredient_name("Poulet Rôti  ")
        "poulet roti"
    """
    # Remove accents
    nfd = unicodedata.normalize("NFD", name)
    without_accents = "".join(
        char for char in nfd if unicodedata.category(char) != "Mn"
    )

    # Lowercase and collapse spaces
    normalized = " ".join(without_accents.lower().split())

    return normalized


async def match_ingredient(
    ingredient_name: str,
    quantity: float,
    unit: str,
    supabase: Client,
    token: str,
    http_client: httpx.AsyncClient,
) -> dict[str, Any]:
    """Match ingredient to FatSecret database with caching.

    Workflow:
    1. Normalize ingredient name
    2. Check Supabase cache
    3. If cache hit: increment usage_count, calculate macros
    4. If cache miss: search FatSecret, score matches, store best match
    5. Return macros for given quantity

    Args:
        ingredient_name: Original ingredient name
        quantity: Amount (e.g., 200)
        unit: Unit (e.g., "g", "kg", "ml", "pièce")
        supabase: Supabase client
        token: Valid FatSecret access token
        http_client: Async HTTP client

    Returns:
        Dict with ingredient data, macros for quantity, cache_hit flag

    Raises:
        ValueError: If ingredient not found or confidence too low

    Example:
        >>> result = await match_ingredient("poulet rôti", 200, "g", supabase, token, client)
        >>> print(result["protein_g"])
        52.4
    """
    normalized_name = normalize_ingredient_name(ingredient_name)
    logger.info(f"Matching ingredient: {ingredient_name} ({quantity}{unit})")

    # Step 1: Check cache
    cache_result = (
        supabase.table("ingredient_mapping")
        .select("*")
        .eq("ingredient_name_normalized", normalized_name)
        .execute()
    )

    if cache_result.data:
        # Cache hit!
        cached = cache_result.data[0]
        logger.info(f"✅ Cache HIT for {ingredient_name}")

        # Increment usage count
        supabase.table("ingredient_mapping").update(
            {"usage_count": cached["usage_count"] + 1}
        ).eq("id", cached["id"]).execute()

        # Calculate macros for given quantity
        multiplier = _calculate_multiplier(quantity, unit)
        macros = {
            "ingredient_name": ingredient_name,
            "fatsecret_food_id": cached["fatsecret_food_id"],
            "fatsecret_food_name": cached["fatsecret_food_name"],
            "quantity": quantity,
            "unit": unit,
            "calories": round(cached["calories_per_100g"] * multiplier, 2),
            "protein_g": round(cached["protein_g_per_100g"] * multiplier, 2),
            "carbs_g": round(cached["carbs_g_per_100g"] * multiplier, 2),
            "fat_g": round(cached["fat_g_per_100g"] * multiplier, 2),
            "confidence_score": cached["confidence_score"],
            "cache_hit": True,
        }
        return macros

    # Step 2: Cache miss - search FatSecret
    logger.info(f"Cache MISS for {ingredient_name}, searching FatSecret...")

    search_results = await search_food(
        normalized_name, token, http_client, max_results=5
    )

    if not search_results:
        logger.warning(f"❌ No FatSecret results for {ingredient_name}")
        raise ValueError(
            f"Ingredient not found in FatSecret database: {ingredient_name}"
        )

    # Step 3: Score matches
    best_match = None
    best_score = 0.0

    for result in search_results:
        food_name = result["food_name"]
        base_similarity = calculate_similarity(normalized_name, food_name)

        # Add keyword bonus
        keywords = normalized_name.split()
        keyword_matches = sum(1 for kw in keywords if kw in food_name.lower())
        bonus = keyword_matches * KEYWORD_BONUS_PER_MATCH

        total_score = min(base_similarity + bonus, 1.0)

        logger.info(
            f"  - {food_name}: {total_score:.2f} (base: {base_similarity:.2f}, bonus: {bonus:.2f})"
        )

        if total_score > best_score:
            best_score = total_score
            best_match = result

    # Step 4: Validate confidence
    if best_score < MIN_CONFIDENCE_SCORE:
        logger.warning(
            f"❌ Low confidence match for {ingredient_name}: {best_score:.2f}"
        )
        raise ValueError(
            f"No confident match found for {ingredient_name} (best score: {best_score:.2f})"
        )

    # Step 5: Get detailed nutrition
    food_id = best_match["food_id"]
    nutrition = await get_food_nutrition(food_id, token, http_client)

    # Step 6: Store in cache
    cache_entry = {
        "ingredient_name": ingredient_name,
        "ingredient_name_normalized": normalized_name,
        "fatsecret_food_id": food_id,
        "fatsecret_food_name": nutrition["food_name"],
        "calories_per_100g": nutrition["calories_per_100g"],
        "protein_g_per_100g": nutrition["protein_g_per_100g"],
        "carbs_g_per_100g": nutrition["carbs_g_per_100g"],
        "fat_g_per_100g": nutrition["fat_g_per_100g"],
        "confidence_score": round(best_score, 2),
        "verified": False,
        "usage_count": 1,
    }

    supabase.table("ingredient_mapping").insert(cache_entry).execute()
    logger.info(
        f"✅ Cached new mapping: {ingredient_name} → {nutrition['food_name']} (score: {best_score:.2f})"
    )

    # Step 7: Calculate macros for quantity
    multiplier = _calculate_multiplier(quantity, unit)
    macros = {
        "ingredient_name": ingredient_name,
        "fatsecret_food_id": food_id,
        "fatsecret_food_name": nutrition["food_name"],
        "quantity": quantity,
        "unit": unit,
        "calories": round(nutrition["calories_per_100g"] * multiplier, 2),
        "protein_g": round(nutrition["protein_g_per_100g"] * multiplier, 2),
        "carbs_g": round(nutrition["carbs_g_per_100g"] * multiplier, 2),
        "fat_g": round(nutrition["fat_g_per_100g"] * multiplier, 2),
        "confidence_score": round(best_score, 2),
        "cache_hit": False,
    }
    return macros


def _calculate_multiplier(quantity: float, unit: str) -> float:
    """Calculate multiplier for converting per-100g nutrition to given quantity.

    Args:
        quantity: Amount
        unit: Unit (g, kg, ml, pièce)

    Returns:
        Multiplier for per-100g values

    Example:
        >>> _calculate_multiplier(200, "g")
        2.0
        >>> _calculate_multiplier(1.5, "kg")
        15.0
    """
    unit_lower = unit.lower()

    if unit_lower == "g":
        return quantity / 100
    elif unit_lower == "kg":
        return (quantity * 1000) / 100
    elif unit_lower in ["ml", "cl", "l"]:
        # Approximate: 1ml = 1g for liquids
        if unit_lower == "ml":
            return quantity / 100
        elif unit_lower == "cl":
            return (quantity * 10) / 100
        elif unit_lower == "l":
            return (quantity * 1000) / 100
    elif unit_lower in ["pièce", "piece", "unité", "unit"]:
        # Assume default serving size (will be improved with per-ingredient defaults)
        logger.warning(f"Using default 100g for unit: {unit}")
        return 1.0
    else:
        logger.warning(f"Unknown unit '{unit}', assuming 100g")
        return 1.0

    return 1.0
