"""Unit tests for ingredient role tagging.

Tests get_ingredient_role(), is_discrete_unit(), get_role_bounds() — deterministic logic.
"""

import pytest

from src.nutrition.ingredient_roles import (
    DISCRETE_UNITS,
    ROLE_BOUNDS,
    get_ingredient_role,
    get_role_bounds,
    is_discrete_unit,
)


# ---------------------------------------------------------------------------
# TestGetIngredientRole
# ---------------------------------------------------------------------------


class TestGetIngredientRole:
    @pytest.mark.parametrize(
        "name",
        ["poulet", "saumon", "tofu", "oeuf", "lentille", "blanc de poulet", "crevette"],
    )
    def test_protein_keywords(self, name: str):
        assert get_ingredient_role(name) == "protein"

    @pytest.mark.parametrize(
        "name",
        ["riz", "pâtes", "quinoa", "pomme de terre", "pain", "avoine", "semoule"],
    )
    def test_starch_keywords(self, name: str):
        assert get_ingredient_role(name) == "starch"

    @pytest.mark.parametrize(
        "name",
        ["brocoli", "tomate", "courgette", "épinard", "carotte", "champignon"],
    )
    def test_vegetable_keywords(self, name: str):
        assert get_ingredient_role(name) == "vegetable"

    @pytest.mark.parametrize(
        "name",
        ["huile d'olive", "beurre", "fromage", "avocat", "noix", "crème fraîche"],
    )
    def test_fat_source_keywords(self, name: str):
        assert get_ingredient_role(name) == "fat_source"

    @pytest.mark.parametrize(
        "name",
        ["sel", "poivre", "sauce soja", "ail", "basilic", "miel", "bouillon"],
    )
    def test_fixed_keywords(self, name: str):
        assert get_ingredient_role(name) == "fixed"

    def test_unknown_fallback(self):
        assert get_ingredient_role("gochujang") == "unknown"
        assert get_ingredient_role("spiruline") == "unknown"

    def test_longest_first_matching(self):
        """haricot vert → vegetable, not protein (from 'haricot')."""
        assert get_ingredient_role("haricot vert") == "vegetable"
        assert get_ingredient_role("haricot rouge") == "protein"
        assert get_ingredient_role("haricot noir") == "protein"

    def test_exceptions_override(self):
        """fromage blanc → protein (not fat_source from 'fromage')."""
        assert get_ingredient_role("fromage blanc") == "protein"
        assert get_ingredient_role("fromage frais") == "protein"
        assert get_ingredient_role("yaourt") == "protein"
        assert get_ingredient_role("skyr") == "protein"

    def test_lait_de_coco_is_fat(self):
        """lait de coco → fat_source (not fixed from 'lait')."""
        assert get_ingredient_role("lait de coco") == "fat_source"

    def test_lait_alone_is_fixed(self):
        assert get_ingredient_role("lait") == "fixed"

    def test_accent_normalization(self):
        """épinard and epinard should give the same result."""
        assert get_ingredient_role("épinard") == get_ingredient_role("epinard")

    def test_case_insensitive(self):
        assert get_ingredient_role("Poulet") == "protein"
        assert get_ingredient_role("HUILE D'OLIVE") == "fat_source"

    def test_beurre_de_cacahuete_is_fat(self):
        """beurre de cacahuète → fat_source (not protein)."""
        assert get_ingredient_role("beurre de cacahuète") == "fat_source"

    def test_pomme_de_terre_is_starch(self):
        """pomme de terre → starch (not something else)."""
        assert get_ingredient_role("pomme de terre") == "starch"

    def test_concentre_de_tomate_is_fixed(self):
        """concentré de tomate → fixed (not vegetable)."""
        assert get_ingredient_role("concentré de tomate") == "fixed"


# ---------------------------------------------------------------------------
# TestIsDiscreteUnit
# ---------------------------------------------------------------------------


class TestIsDiscreteUnit:
    def test_pieces(self):
        assert is_discrete_unit("pièces") is True

    def test_oeufs(self):
        assert is_discrete_unit("oeufs") is True

    def test_tranches(self):
        assert is_discrete_unit("tranches") is True

    def test_grams(self):
        assert is_discrete_unit("g") is False

    def test_ml(self):
        assert is_discrete_unit("ml") is False

    def test_case_insensitive(self):
        assert is_discrete_unit("Pièces") is True


# ---------------------------------------------------------------------------
# TestRoleBounds
# ---------------------------------------------------------------------------


class TestRoleBounds:
    def test_all_roles_have_bounds(self):
        for role in (
            "protein",
            "starch",
            "vegetable",
            "fat_source",
            "unknown",
            "fixed",
        ):
            lb, ub = get_role_bounds(role)
            assert lb <= ub

    def test_unknown_bounds_symmetric(self):
        assert get_role_bounds("unknown") == (0.75, 1.25)

    def test_fixed_bounds_locked(self):
        assert get_role_bounds("fixed") == (1.0, 1.0)

    def test_nonexistent_role_returns_unknown_bounds(self):
        assert get_role_bounds("nonexistent") == ROLE_BOUNDS["unknown"]

    def test_discrete_units_set_not_empty(self):
        assert len(DISCRETE_UNITS) > 0
