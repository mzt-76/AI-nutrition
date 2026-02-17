"""Unit tests for feedback extraction and validation.

Tests cover metric validation, range checking, implicit feedback extraction
from conversational text, and completeness assessment.
"""

import pytest
from src.nutrition.feedback_extraction import (
    validate_feedback_metrics,
    extract_feedback_from_text,
    check_feedback_completeness,
)


class TestValidateFeedbackMetrics:
    """Tests for feedback metric validation."""

    def test_complete_valid_feedback(self):
        """Test valid complete feedback passes validation."""
        feedback = {
            "weight_start_kg": 87.0,
            "weight_end_kg": 86.4,
            "adherence_percent": 85,
            "hunger_level": "medium",
            "energy_level": "high",
            "sleep_quality": "good",
            "cravings": [],
        }
        result = validate_feedback_metrics(feedback)
        assert result["weight_start_kg"] == 87.0
        assert result["adherence_percent"] == 85

    def test_missing_required_weight_start(self):
        """Test missing required field raises ValueError."""
        feedback = {
            "weight_end_kg": 86.4,
            "adherence_percent": 85,
        }
        with pytest.raises(ValueError, match="weight_start_kg"):
            validate_feedback_metrics(feedback)

    def test_missing_required_weight_end(self):
        """Test missing weight_end_kg raises ValueError."""
        feedback = {
            "weight_start_kg": 87.0,
            "adherence_percent": 85,
        }
        with pytest.raises(ValueError, match="weight_end_kg"):
            validate_feedback_metrics(feedback)

    def test_missing_required_adherence(self):
        """Test missing adherence_percent raises ValueError."""
        feedback = {
            "weight_start_kg": 87.0,
            "weight_end_kg": 86.4,
        }
        with pytest.raises(ValueError, match="adherence_percent"):
            validate_feedback_metrics(feedback)

    def test_weight_below_minimum(self):
        """Test weight below 40kg raises ValueError."""
        feedback = {
            "weight_start_kg": 39.9,
            "weight_end_kg": 40.0,
            "adherence_percent": 50,
        }
        with pytest.raises(ValueError, match="40-300"):
            validate_feedback_metrics(feedback)

    def test_weight_above_maximum(self):
        """Test weight above 300kg raises ValueError."""
        feedback = {
            "weight_start_kg": 87.0,
            "weight_end_kg": 301.0,
            "adherence_percent": 50,
        }
        with pytest.raises(ValueError, match="40-300"):
            validate_feedback_metrics(feedback)

    def test_weight_at_minimum_boundary(self):
        """Test weight at 40kg (minimum boundary) is valid."""
        feedback = {
            "weight_start_kg": 40.0,
            "weight_end_kg": 40.5,
            "adherence_percent": 50,
        }
        result = validate_feedback_metrics(feedback)
        assert result["weight_start_kg"] == 40.0

    def test_weight_at_maximum_boundary(self):
        """Test weight at 300kg (maximum boundary) is valid."""
        feedback = {
            "weight_start_kg": 87.0,
            "weight_end_kg": 300.0,
            "adherence_percent": 50,
        }
        result = validate_feedback_metrics(feedback)
        assert result["weight_end_kg"] == 300.0

    def test_adherence_below_zero(self):
        """Test adherence below 0% raises ValueError."""
        feedback = {
            "weight_start_kg": 87.0,
            "weight_end_kg": 86.4,
            "adherence_percent": -10,
        }
        with pytest.raises(ValueError, match="0-100"):
            validate_feedback_metrics(feedback)

    def test_adherence_above_100(self):
        """Test adherence above 100% raises ValueError."""
        feedback = {
            "weight_start_kg": 87.0,
            "weight_end_kg": 86.4,
            "adherence_percent": 110,
        }
        with pytest.raises(ValueError, match="0-100"):
            validate_feedback_metrics(feedback)

    def test_adherence_at_boundaries(self):
        """Test adherence at 0% and 100% are valid."""
        for adherence in [0, 100]:
            feedback = {
                "weight_start_kg": 87.0,
                "weight_end_kg": 86.4,
                "adherence_percent": adherence,
            }
            result = validate_feedback_metrics(feedback)
            assert result["adherence_percent"] == adherence

    def test_invalid_hunger_level(self):
        """Test invalid hunger_level raises ValueError."""
        feedback = {
            "weight_start_kg": 87.0,
            "weight_end_kg": 86.4,
            "adherence_percent": 50,
            "hunger_level": "ravenous",  # Invalid
        }
        with pytest.raises(ValueError, match="hunger_level"):
            validate_feedback_metrics(feedback)

    def test_invalid_energy_level(self):
        """Test invalid energy_level raises ValueError."""
        feedback = {
            "weight_start_kg": 87.0,
            "weight_end_kg": 86.4,
            "adherence_percent": 50,
            "energy_level": "amazing",  # Invalid
        }
        with pytest.raises(ValueError, match="energy_level"):
            validate_feedback_metrics(feedback)

    def test_invalid_sleep_quality(self):
        """Test invalid sleep_quality raises ValueError."""
        feedback = {
            "weight_start_kg": 87.0,
            "weight_end_kg": 86.4,
            "adherence_percent": 50,
            "sleep_quality": "blabla",  # Truly invalid (not in SLEEP_QUALITY_MAPPING)
        }
        with pytest.raises(ValueError, match="sleep_quality"):
            validate_feedback_metrics(feedback)

    def test_defaults_applied_for_optional_fields(self):
        """Test that defaults are applied for missing optional fields."""
        feedback = {
            "weight_start_kg": 87.0,
            "weight_end_kg": 86.4,
            "adherence_percent": 85,
        }
        result = validate_feedback_metrics(feedback)
        assert result["hunger_level"] == "medium"
        assert result["energy_level"] == "medium"
        assert result["sleep_quality"] == "good"
        assert result["cravings"] == []
        assert result["notes"] == ""

    @pytest.mark.parametrize(
        "weight,should_raise",
        [
            (87.0, False),
            (40.0, False),  # Min valid
            (299.5, False),  # Max valid (slightly below 300)
            (39.9, True),  # Below min
            (301.0, True),  # Above max
            (150.0, False),  # Mid-range
        ],
    )
    def test_weight_bounds_parametrized(self, weight, should_raise):
        """Parametrized test for weight boundary validation."""
        feedback = {
            "weight_start_kg": weight,
            "weight_end_kg": weight + 0.5,
            "adherence_percent": 50,
        }

        if should_raise:
            with pytest.raises(ValueError):
                validate_feedback_metrics(feedback)
        else:
            result = validate_feedback_metrics(feedback)
            assert result["weight_start_kg"] == weight


class TestExtractFeedbackFromText:
    """Tests for implicit feedback extraction from conversational text."""

    def test_high_energy_detection(self):
        """Test detection of high energy signals."""
        text = "This week I felt energetic and strong, great progress!"
        result = extract_feedback_from_text(text)
        energy_level, confidence = result["energy_level"]
        assert energy_level == "high"
        assert confidence > 0.6

    def test_low_energy_detection(self):
        """Test detection of low energy signals."""
        text = "This week I felt exhausted and fatigued, struggling with workouts"
        result = extract_feedback_from_text(text)
        energy_level, confidence = result["energy_level"]
        assert energy_level == "low"
        assert confidence > 0.6

    def test_medium_energy_default(self):
        """Test medium energy assigned when no specific signals."""
        text = "This week went okay, nothing special"
        result = extract_feedback_from_text(text)
        energy_level, confidence = result["energy_level"]
        assert energy_level == "medium"
        assert confidence <= 0.6

    def test_high_hunger_detection(self):
        """Test detection of high hunger signals."""
        text = "I was constantly hungry this week, had a hard time with cravings"
        result = extract_feedback_from_text(text)
        hunger_level, confidence = result["hunger_level"]
        assert hunger_level == "high"
        assert confidence > 0.6

    def test_low_hunger_detection(self):
        """Test detection of low hunger signals."""
        text = "Felt very satisfied with my meals, good satiety"
        result = extract_feedback_from_text(text)
        hunger_level, confidence = result["hunger_level"]
        assert hunger_level == "low"
        assert confidence > 0.6

    def test_medium_hunger_default(self):
        """Test medium hunger assigned when no specific signals."""
        text = "Hunger was normal this week"
        result = extract_feedback_from_text(text)
        hunger_level, confidence = result["hunger_level"]
        assert hunger_level == "medium"

    def test_mood_indicators_positive(self):
        """Test detection of positive mood indicators."""
        text = "Great week! I felt happy and motivated the whole time"
        result = extract_feedback_from_text(text)
        assert "happy" in result["mood_indicators"]
        assert "motivated" in result["mood_indicators"]

    def test_mood_indicators_negative(self):
        """Test detection of negative mood indicators."""
        text = "This week I felt sad and depressed, hard to stay focused"
        result = extract_feedback_from_text(text)
        assert "sad" in result["mood_indicators"]
        assert "depressed" in result["mood_indicators"]

    def test_stress_indicators(self):
        """Test detection of stress indicators."""
        text = "Work was very stressful this week, felt overwhelmed"
        result = extract_feedback_from_text(text)
        assert "stress" in result["stress_indicators"]
        assert "overwhelm" in result["stress_indicators"]

    def test_mixed_signals(self):
        """Test handling of mixed signals (both high and low energy)."""
        text = "Started week strong and energetic, but felt tired by Friday"
        result = extract_feedback_from_text(text)
        # Should lean toward multiple keywords
        assert result["energy_level"] is not None

    def test_case_insensitivity(self):
        """Test that extraction is case-insensitive."""
        text_lower = "i felt ENERGETIC and POWERFUL"
        text_upper = "I FELT energetic AND powerful"
        result_lower = extract_feedback_from_text(text_lower)
        result_upper = extract_feedback_from_text(text_upper)
        assert result_lower["energy_level"][0] == result_upper["energy_level"][0]


class TestCheckFeedbackCompleteness:
    """Tests for feedback completeness assessment."""

    def test_comprehensive_feedback(self):
        """Test assessment of comprehensive feedback (all fields)."""
        feedback = {
            "weight_start_kg": 87.0,
            "weight_end_kg": 86.4,
            "adherence_percent": 85,
            "hunger_level": "medium",
            "energy_level": "high",
            "sleep_quality": "good",
            "cravings": ["carbs"],
            "notes": "Great week overall",
        }
        result = check_feedback_completeness(feedback)
        assert result["quality"] == "comprehensive"
        assert result["completeness_percent"] == 100
        assert result["confidence_impact"] == 0.0

    def test_adequate_feedback(self):
        """Test assessment of adequate feedback (most fields)."""
        feedback = {
            "weight_start_kg": 87.0,
            "weight_end_kg": 86.4,
            "adherence_percent": 85,
            "hunger_level": "medium",
            "energy_level": "high",
            "sleep_quality": "good",
            # Missing cravings, notes
        }
        result = check_feedback_completeness(feedback)
        assert result["quality"] == "adequate"
        assert 50 <= result["completeness_percent"] <= 100
        assert result["confidence_impact"] == 0.1

    def test_incomplete_feedback(self):
        """Test assessment of incomplete feedback (few optional fields)."""
        feedback = {
            "weight_start_kg": 87.0,
            "weight_end_kg": 86.4,
            "adherence_percent": 85,
            # Only required fields, no optional fields
        }
        result = check_feedback_completeness(feedback)
        assert result["quality"] == "incomplete"
        assert result["completeness_percent"] < 50
        assert result["confidence_impact"] == 0.25

    def test_missing_fields_identified(self):
        """Test that missing fields are correctly identified."""
        feedback = {
            "weight_start_kg": 87.0,
            "weight_end_kg": 86.4,
            "adherence_percent": 85,
            "hunger_level": "medium",
            # Missing energy_level, sleep_quality, cravings, notes
        }
        result = check_feedback_completeness(feedback)
        assert "energy_level" in result["missing_fields"]
        assert "sleep_quality" in result["missing_fields"]
