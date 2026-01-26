"""
Pytest configuration for AI Nutrition Assistant tests.

This conftest.py file:
1. Adds the project root to Python path for imports
2. Configures pytest-asyncio
3. Provides shared fixtures
"""

import sys
from pathlib import Path

import pytest

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")


@pytest.fixture
def sample_profile():
    """Sample user profile for testing."""
    return {
        "id": "test-uuid-123",
        "name": "Test User",
        "age": 35,
        "gender": "male",
        "weight_kg": 87.0,
        "height_cm": 178,
        "activity_level": "moderate",
        "goals": {
            "muscle_gain": 7,
            "performance": 5,
            "weight_loss": 0,
            "maintenance": 3,
        },
        "allergies": ["arachides", "fruits à coque"],
        "diet_type": "omnivore",
        "disliked_foods": ["poisson"],
        "favorite_foods": ["poulet", "riz"],
        "max_prep_time": 45,
        "preferred_cuisines": ["méditerranéenne", "asiatique"],
        "target_calories": 2800,
        "target_protein_g": 180,
        "target_carbs_g": 350,
        "target_fat_g": 80,
    }


@pytest.fixture
def sample_meal_plan():
    """Sample meal plan for testing."""
    return {
        "days": [
            {
                "day": "Lundi",
                "date": "2025-01-20",
                "meals": [
                    {
                        "meal_type": "Petit-déjeuner",
                        "name": "Omelette aux épinards",
                        "ingredients": [
                            {"name": "oeufs", "quantity": 3, "unit": "pièces"},
                            {"name": "épinards", "quantity": 50, "unit": "g"},
                            {"name": "huile d'olive", "quantity": 10, "unit": "ml"},
                        ],
                        "instructions": "Battre les oeufs, ajouter les épinards, cuire.",
                        "prep_time_minutes": 10,
                        "nutrition": {
                            "calories": 450,
                            "protein_g": 28,
                            "carbs_g": 5,
                            "fat_g": 35,
                        },
                    },
                    {
                        "meal_type": "Déjeuner",
                        "name": "Poulet grillé et quinoa",
                        "ingredients": [
                            {"name": "poulet", "quantity": 150, "unit": "g"},
                            {"name": "quinoa", "quantity": 80, "unit": "g"},
                            {"name": "brocoli", "quantity": 100, "unit": "g"},
                        ],
                        "instructions": "Griller le poulet, cuire le quinoa, servir avec brocoli.",
                        "prep_time_minutes": 25,
                        "nutrition": {
                            "calories": 650,
                            "protein_g": 55,
                            "carbs_g": 60,
                            "fat_g": 18,
                        },
                    },
                    {
                        "meal_type": "Dîner",
                        "name": "Saumon au four",
                        "ingredients": [
                            {"name": "saumon", "quantity": 150, "unit": "g"},
                            {"name": "patate douce", "quantity": 200, "unit": "g"},
                            {"name": "haricots verts", "quantity": 100, "unit": "g"},
                        ],
                        "instructions": "Cuire le saumon au four, accompagner de patate douce et haricots.",
                        "prep_time_minutes": 30,
                        "nutrition": {
                            "calories": 580,
                            "protein_g": 45,
                            "carbs_g": 50,
                            "fat_g": 22,
                        },
                    },
                ],
            }
        ]
        * 7,  # Duplicate for 7 days
        "weekly_summary": {
            "average_calories": 1680,
            "average_protein_g": 128,
            "average_carbs_g": 115,
            "average_fat_g": 75,
        },
    }


@pytest.fixture
def sample_weekly_feedback():
    """Sample weekly feedback data for testing."""
    return {
        "weight_start_kg": 87.0,
        "weight_end_kg": 86.4,
        "adherence_percent": 85,
        "hunger_level": "medium",
        "energy_level": "high",
        "sleep_quality": "good",
        "cravings": ["sucré"],
        "notes": "Bonne semaine, bien récupéré après l'entraînement.",
    }
