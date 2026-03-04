"""Tests for UI component marker extraction."""

from src.ui_components import ZONE_MAP, extract_ui_components


class TestExtractUIComponents:
    """Tests for extract_ui_components()."""

    def test_single_valid_marker(self):
        text = 'Some text <!--UI:MacroGauges:{"protein_g":120,"carbs_g":200,"fat_g":60,"target_calories":1800}--> more text'
        cleaned, components = extract_ui_components(text)
        assert cleaned == "Some text  more text"
        assert len(components) == 1
        assert components[0]["component"] == "MacroGauges"
        assert components[0]["props"]["protein_g"] == 120
        assert components[0]["id"] == "macrogauges-0"
        assert components[0]["zone"] == "macros"

    def test_multiple_markers(self):
        text = (
            '<!--UI:NutritionSummaryCard:{"bmr":1600,"tdee":2200,"target_calories":1800,"primary_goal":"perte"}-->'
            " Texte entre "
            '<!--UI:MacroGauges:{"protein_g":120,"carbs_g":200,"fat_g":60,"target_calories":1800}-->'
        )
        cleaned, components = extract_ui_components(text)
        assert cleaned == "Texte entre"
        assert len(components) == 2
        assert components[0]["component"] == "NutritionSummaryCard"
        assert components[1]["component"] == "MacroGauges"

    def test_no_markers(self):
        text = "Just plain text with no markers at all."
        cleaned, components = extract_ui_components(text)
        assert cleaned == text
        assert components == []

    def test_malformed_json_skipped(self):
        text = '<!--UI:BadComponent:{not valid json}--> <!--UI:MacroGauges:{"protein_g":100,"carbs_g":200,"fat_g":60,"target_calories":1800}-->'
        cleaned, components = extract_ui_components(text)
        assert len(components) == 1
        assert components[0]["component"] == "MacroGauges"

    def test_zone_inference_all_known_components(self):
        for component_name, expected_zone in ZONE_MAP.items():
            text = f'<!--UI:{component_name}:{{"key":"value"}}-->'
            _, components = extract_ui_components(text)
            assert len(components) == 1
            assert components[0]["zone"] == expected_zone

    def test_unknown_component_defaults_to_content_zone(self):
        text = '<!--UI:UnknownWidget:{"data":"test"}-->'
        _, components = extract_ui_components(text)
        assert len(components) == 1
        assert components[0]["zone"] == "content"

    def test_unique_id_generation_increments_per_type(self):
        text = (
            '<!--UI:MealCard:{"meal_type":"petit-dejeuner","recipe_name":"Omelette","calories":350,"macros":{"protein_g":25,"carbs_g":10,"fat_g":20}}-->'
            '<!--UI:MealCard:{"meal_type":"dejeuner","recipe_name":"Salade","calories":450,"macros":{"protein_g":30,"carbs_g":40,"fat_g":15}}-->'
            '<!--UI:MacroGauges:{"protein_g":120,"carbs_g":200,"fat_g":60,"target_calories":1800}-->'
        )
        _, components = extract_ui_components(text)
        assert components[0]["id"] == "mealcard-0"
        assert components[1]["id"] == "mealcard-1"
        assert components[2]["id"] == "macrogauges-0"

    def test_empty_text(self):
        cleaned, components = extract_ui_components("")
        assert cleaned == ""
        assert components == []

    def test_multiline_json_in_markers(self):
        text = '<!--UI:NutritionSummaryCard:{"bmr":1600,\n"tdee":2200,\n"target_calories":1800,\n"primary_goal":"maintenance"}-->'
        cleaned, components = extract_ui_components(text)
        assert cleaned == ""
        assert len(components) == 1
        assert components[0]["props"]["bmr"] == 1600
        assert components[0]["props"]["tdee"] == 2200

    def test_mixed_text_and_markers_preserves_text(self):
        text = (
            "Voici tes resultats:\n\n"
            '<!--UI:NutritionSummaryCard:{"bmr":1600,"tdee":2200,"target_calories":1800,"primary_goal":"perte"}-->'
            "\n\nTu devrais viser 1800 kcal par jour."
        )
        cleaned, components = extract_ui_components(text)
        assert "Voici tes resultats:" in cleaned
        assert "Tu devrais viser 1800 kcal par jour." in cleaned
        assert "<!--UI:" not in cleaned
        assert len(components) == 1
