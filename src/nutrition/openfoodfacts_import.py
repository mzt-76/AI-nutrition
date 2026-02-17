"""
Import OpenFoodFacts data from JSONL into Supabase.

This script reads the compressed JSONL file, filters for French products
with complete nutrition data, and imports them in batches.
"""

import gzip
import json
import logging
from pathlib import Path

from src.clients import get_supabase_client

logger = logging.getLogger(__name__)

# Configuration
JSONL_PATH = Path(__file__).parent / "openfood" / "openfoodfacts-products.jsonl.gz"
BATCH_SIZE = 1000


def filter_product(product: dict) -> dict | None:
    """
    Filter product for France with complete nutrition data.

    Args:
        product: Raw product dict from JSONL

    Returns:
        Filtered product dict or None if invalid

    Example:
        >>> product = {"code": "123", "product_name": "Poulet", ...}
        >>> filtered = filter_product(product)
        >>> filtered["code"]
        "123"
    """
    # Must be available in France
    if "en:france" not in product.get("countries_tags", []):
        return None

    # Must have a name
    if not product.get("product_name"):
        return None

    # Extract nutrition data
    nutrients = product.get("nutriments", {})
    try:
        cals = float(nutrients.get("energy-kcal_100g", 0))
        prot = float(nutrients.get("proteins_100g", 0))
        carbs = float(nutrients.get("carbohydrates_100g", 0))
        fat = float(nutrients.get("fat_100g", 0))
    except (ValueError, TypeError):
        return None

    # Validate nutrition makes sense
    if not (cals > 0 and prot >= 0 and carbs >= 0 and fat >= 0):
        return None

    return {
        "code": product.get("code", product.get("_id")),
        "product_name": product["product_name"],
        "product_name_fr": product.get("product_name_fr"),
        "countries_tags": product["countries_tags"],
        "calories_per_100g": round(cals, 2),
        "protein_g_per_100g": round(prot, 2),
        "carbs_g_per_100g": round(carbs, 2),
        "fat_g_per_100g": round(fat, 2),
    }


def import_openfoodfacts_data() -> None:
    """
    Import OpenFoodFacts data from JSONL into Supabase.

    Reads compressed JSONL, filters for French products, and imports in batches.

    Raises:
        FileNotFoundError: If JSONL file doesn't exist
    """
    if not JSONL_PATH.exists():
        raise FileNotFoundError(f"JSONL file not found: {JSONL_PATH}")

    logger.info(f"Starting import from {JSONL_PATH}")

    supabase = get_supabase_client()
    batch = []
    total_processed = 0
    total_imported = 0

    with gzip.open(JSONL_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            total_processed += 1

            try:
                product = json.loads(line)
                filtered = filter_product(product)

                if filtered:
                    batch.append(filtered)

                    # Import batch when full
                    if len(batch) >= BATCH_SIZE:
                        supabase.table("openfoodfacts_products").insert(batch).execute()
                        total_imported += len(batch)
                        logger.info(
                            f"Imported batch: {total_imported} products ({total_processed} processed)"
                        )
                        batch = []

            except Exception as e:
                logger.warning(f"Skipping product: {e}")
                continue

    # Import remaining products
    if batch:
        supabase.table("openfoodfacts_products").insert(batch).execute()
        total_imported += len(batch)

    logger.info(
        f"Import complete: {total_imported} products imported from {total_processed} processed"
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    import_openfoodfacts_data()
