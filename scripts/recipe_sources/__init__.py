"""Recipe source adapters for the multi-source import pipeline.

LLM-free (rule 10). Each adapter implements RecipeSource ABC.
"""

from scripts.recipe_sources.allrecipes import AllRecipesSource
from scripts.recipe_sources.base import RawRecipe, RecipeSource
from scripts.recipe_sources.bbc_good_food import BBCGoodFoodSource
from scripts.recipe_sources.cuisine_az import CuisineAZSource
from scripts.recipe_sources.edamam import EdamamSource
from scripts.recipe_sources.marmiton import MarmitonSource
from scripts.recipe_sources.sept_cinquante_g import SeptCinquanteGSource
from scripts.recipe_sources.spoonacular import SpoonacularSource
from scripts.recipe_sources.themealdb_adapter import TheMealDBSource

__all__ = [
    "AllRecipesSource",
    "BBCGoodFoodSource",
    "CuisineAZSource",
    "EdamamSource",
    "MarmitonSource",
    "RawRecipe",
    "RecipeSource",
    "SeptCinquanteGSource",
    "SpoonacularSource",
    "TheMealDBSource",
]
