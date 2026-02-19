"""Search the web using Brave Search API.

Utility script — can be imported by agent tool wrapper or run standalone.
Uses Brave Search API for recent nutritional information.

Source: Extracted from src/tools.py web_search_tool
"""

import logging

logger = logging.getLogger(__name__)


async def execute(**kwargs) -> str:
    """Search the web using Brave Search API.

    Args:
        query: Search query.
        http_client: Async HTTP client.
        brave_api_key: Brave API key (required).
        searxng_base_url: Alternative SearXNG URL (optional).

    Returns:
        Summary of search results.
    """
    query = kwargs["query"]
    http_client = kwargs["http_client"]
    brave_api_key = kwargs.get("brave_api_key")
    # searxng_base_url accepted but not yet implemented
    kwargs.get("searxng_base_url")

    try:
        logger.info(f"Web search: {query}")

        if not brave_api_key:
            return "Web search unavailable: BRAVE_API_KEY not configured"

        # Brave Search API
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": brave_api_key,
        }
        params = {"q": query, "count": 5}

        response = await http_client.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        results = data.get("web", {}).get("results", [])

        if not results:
            return "No search results found."

        # Format top 5 results
        formatted = []
        for i, result in enumerate(results[:5], 1):
            title = result.get("title", "No title")
            description = result.get("description", "")
            result_url = result.get("url", "")
            formatted.append(f"{i}. **{title}**\n   {description}\n   {result_url}")

        logger.info(f"Found {len(results)} search results")

        return "\n\n".join(formatted)

    except Exception as e:
        logger.error(f"Web search error: {e}", exc_info=True)
        return f"Web search error: {str(e)}"
