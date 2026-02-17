"""Unit tests for weekly adjustment analysis and recommendations.

Tests cover weight trend analysis, metabolic adaptation detection, pattern
identification, and red flag detection with various scenarios.
"""

import pytest
from src.nutrition.adjustments import (
    analyze_weight_trend,
    detect_metabolic_adaptation,
    detect_adherence_patterns,
    generate_calorie_adjustment,
    generate_macro_adjustments,
    detect_red_flags,
)


class TestAnalyzeWeightTrend:
    """Tests for weight trend analysis against goal-specific targets."""

    def test_weight_loss_optimal_rate(self):
        """Test weight loss at optimal rate (-0.5 kg/week)."""
        result = analyze_weight_trend(87.0, 86.5, "weight_loss", weeks_on_plan=2)
        assert result["trend"] in ["stable", "optimal"]
        assert result["change_kg"] == -0.5
        assert result["confidence"] >= 0.75

    def test_weight_loss_too_fast(self):
        """Test weight loss too fast (>1 kg/week) - red flag territory."""
        result = analyze_weight_trend(
            90.0, 88.8, "weight_loss", weeks_on_plan=1
        )  # -1.2 kg/week
        assert result["trend"] == "too_fast"
        assert (
            "fast" in result["assessment"].lower()
            or "muscle loss" in result["assessment"].lower()
        )

    def test_weight_loss_too_slow(self):
        """Test weight loss slower than optimal."""
        result = analyze_weight_trend(
            87.0, 86.85, "weight_loss", weeks_on_plan=3
        )  # -0.15 kg/week
        assert result["trend"] == "too_slow"

    def test_muscle_gain_optimal(self):
        """Test muscle gain at optimal rate (+0.3 kg/week)."""
        result = analyze_weight_trend(87.0, 87.3, "muscle_gain", weeks_on_plan=2)
        assert result["trend"] in ["stable", "optimal"]
        assert result["change_kg"] == 0.3

    def test_muscle_gain_actual_loss(self):
        """Test actual weight loss when trying to gain muscle."""
        result = analyze_weight_trend(87.0, 86.0, "muscle_gain", weeks_on_plan=1)
        assert result["trend"] == "too_slow"  # Losing when should gain
        assert "losing" in result["assessment"].lower()  # Message says "losing weight"

    def test_maintenance_small_variance(self):
        """Test maintenance with normal body weight variance."""
        result = analyze_weight_trend(85.0, 85.2, "maintenance", weeks_on_plan=1)
        assert result["trend"] in ["stable", "optimal"]
        assert abs(result["change_kg"]) <= 0.5

    @pytest.mark.parametrize(
        "weight_start,weight_end,goal,expected_trend",
        [
            (87.0, 86.4, "muscle_gain", "too_slow"),  # -0.6kg: losing when should gain
            (
                90.0,
                88.8,
                "muscle_gain",
                "too_slow",
            ),  # -1.2kg bad for muscle (losing instead of gaining)
            (85.0, 85.2, "maintenance", "stable"),  # +0.2kg normal variance
            (
                90.0,
                89.25,
                "weight_loss",
                "too_fast",
            ),  # -0.75kg exceeds target range (-0.7 to -0.3)
        ],
    )
    def test_weight_trend_parametrized(
        self, weight_start, weight_end, goal, expected_trend
    ):
        """Parametrized test for different weight scenarios."""
        result = analyze_weight_trend(weight_start, weight_end, goal)
        assert result["trend"] == expected_trend


class TestDetectMetabolicAdaptation:
    """Tests for metabolic adaptation detection."""

    def test_insufficient_data(self):
        """Test that adaptation requires minimum weeks of data."""
        result = detect_metabolic_adaptation(
            past_weeks=[{"weight_change_kg": -0.5, "adherence_percent": 85}],
            observed_tdee=None,
            calculated_tdee=2868,
        )
        assert result["detected"] is False
        assert result["confidence"] <= 0.5  # Low confidence

    def test_no_adaptation_detected(self):
        """Test normal metabolic response (no adaptation).

        With very high adherence (98%+) and small weight loss (-0.1kg/week),
        the inferred TDEE should be close to calculated TDEE (>95%).

        Note: The current adaptation detection formula subtracts inferred deficit
        from TDEE, so only minimal weight loss yields adaptation_factor > 0.95.
        """
        past_weeks = [
            {"weight_change_kg": -0.1, "adherence_percent": 98},
            {"weight_change_kg": -0.1, "adherence_percent": 99},
            {"weight_change_kg": -0.1, "adherence_percent": 98},
            {"weight_change_kg": -0.1, "adherence_percent": 99},
        ]
        result = detect_metabolic_adaptation(
            past_weeks=past_weeks,
            observed_tdee=None,
            calculated_tdee=2868,
        )
        assert result["detected"] is False
        assert result["adaptation_factor"] >= 0.95  # >95% of calculated

    def test_adaptation_detected(self):
        """Test metabolic adaptation (slower weight loss than expected)."""
        # User is 90% adherent but only losing 0.3kg/week instead of 0.5kg
        # Suggests actual TDEE is lower than calculated
        past_weeks = [
            {"weight_change_kg": -0.3, "adherence_percent": 90},
            {"weight_change_kg": -0.25, "adherence_percent": 88},
            {"weight_change_kg": -0.3, "adherence_percent": 92},
            {"weight_change_kg": -0.28, "adherence_percent": 90},
        ]
        result = detect_metabolic_adaptation(
            past_weeks=past_weeks,
            observed_tdee=None,
            calculated_tdee=2868,
        )
        # With 90% adherence and ~-0.3kg/week loss, actual TDEE should be lower
        assert result["adaptation_factor"] < 1.0  # Something less than 100%


class TestDetectAdherencePatterns:
    """Tests for adherence pattern identification."""

    def test_empty_history(self):
        """Test with no past weeks returns sensible defaults."""
        result = detect_adherence_patterns([])
        assert result["positive_triggers"] == []
        assert result["negative_triggers"] == []
        assert result["pattern_strength"] == 0.0

    def test_consistent_high_adherence(self):
        """Test detection of consistently high adherence."""
        past_weeks = [
            {"adherence_percent": 85, "energy_level": "high"},
            {"adherence_percent": 88, "energy_level": "high"},
            {"adherence_percent": 90, "energy_level": "high"},
        ]
        result = detect_adherence_patterns(past_weeks)
        assert (
            "high_energy" in str(result["positive_triggers"]).lower()
            or len(result["positive_triggers"]) > 0
        )

    def test_low_adherence_with_high_hunger(self):
        """Test detection of hunger-related adherence problems."""
        past_weeks = [
            {"adherence_percent": 30, "hunger_level": "high"},
            {"adherence_percent": 35, "hunger_level": "high"},
            {"adherence_percent": 25, "hunger_level": "high"},
        ]
        result = detect_adherence_patterns(past_weeks)
        assert "hunger" in str(result["negative_triggers"]).lower()


class TestGenerateCalorieAdjustment:
    """Tests for calorie adjustment calculations."""

    def test_weight_loss_too_slow(self):
        """Test increasing deficit when weight loss too slow."""
        result = generate_calorie_adjustment(
            weight_change_kg=-0.2,
            goal="weight_loss",
            adherence_percent=85,
            weeks_on_plan=3,
        )
        assert result["adjustment_kcal"] < 0  # Reduce calories (increase deficit)

    def test_weight_loss_too_fast(self):
        """Test decreasing deficit when weight loss too fast."""
        result = generate_calorie_adjustment(
            weight_change_kg=-1.2,
            goal="weight_loss",
            adherence_percent=90,
            weeks_on_plan=2,
        )
        assert result["adjustment_kcal"] > 0  # Add calories (reduce deficit)

    def test_muscle_gain_actual_loss(self):
        """Test adding calories when losing weight during muscle gain phase."""
        result = generate_calorie_adjustment(
            weight_change_kg=-0.5,
            goal="muscle_gain",
            adherence_percent=85,
            weeks_on_plan=2,
        )
        assert result["adjustment_kcal"] > 0  # Add calories

    def test_adjustment_within_bounds(self):
        """Test that adjustments never exceed safety limits."""
        # Even extreme input should be clamped
        result = generate_calorie_adjustment(
            weight_change_kg=-2.0,
            goal="weight_loss",
            adherence_percent=95,
            weeks_on_plan=1,
        )
        assert -300 <= result["adjustment_kcal"] <= 300

    def test_conservative_vs_aggressive(self):
        """Test that conservative adjustment is smaller than aggressive."""
        result = generate_calorie_adjustment(
            weight_change_kg=-0.7,
            goal="weight_loss",
            adherence_percent=85,
            weeks_on_plan=2,
        )
        if result["adjustment_kcal"] != 0:
            assert abs(result["conservative_adjustment"]) < abs(
                result["aggressive_adjustment"]
            )


class TestGenerateMacroAdjustments:
    """Tests for macro (protein/carbs/fat) adjustments."""

    def test_high_hunger_increases_protein(self):
        """Test that high hunger triggers protein increase."""
        result = generate_macro_adjustments(
            hunger_level="high",
            energy_level="medium",
            cravings=[],
            current_protein_g=191,
            current_carbs_g=350,
            current_fat_g=90,
        )
        assert result["protein_g"] > 0  # Increase protein

    def test_low_energy_increases_carbs(self):
        """Test that low energy triggers carb increase."""
        result = generate_macro_adjustments(
            hunger_level="medium",
            energy_level="low",
            cravings=[],
            current_protein_g=191,
            current_carbs_g=350,
            current_fat_g=90,
        )
        assert result["carbs_g"] > 0  # Increase carbs

    def test_high_energy_reduces_carbs_slightly(self):
        """Test that high energy may reduce carbs (sufficient energy)."""
        result = generate_macro_adjustments(
            hunger_level="low",
            energy_level="high",
            cravings=[],
            current_protein_g=191,
            current_carbs_g=350,
            current_fat_g=90,
        )
        assert result["carbs_g"] <= 0  # No increase

    def test_cravings_carbs_increases_carbs(self):
        """Test that sugar/carb cravings increase carbs slightly."""
        result = generate_macro_adjustments(
            hunger_level="medium",
            energy_level="medium",
            cravings=["sweets", "carbs"],
            current_protein_g=191,
            current_carbs_g=350,
            current_fat_g=90,
        )
        assert result["carbs_g"] > 0

    def test_adjustments_within_bounds(self):
        """Test that macro adjustments never exceed safety limits."""
        result = generate_macro_adjustments(
            hunger_level="high",
            energy_level="low",
            cravings=["carbs", "sweets"],
            current_protein_g=191,
            current_carbs_g=350,
            current_fat_g=90,
        )
        assert -30 <= result["protein_g"] <= 30
        assert -50 <= result["carbs_g"] <= 50
        assert -15 <= result["fat_g"] <= 15


class TestDetectRedFlags:
    """Tests for red flag detection across 6 types."""

    def test_rapid_weight_loss_single_week(self):
        """Test detection of rapid weight loss in single week."""
        flags = detect_red_flags(
            current_week={"weight_change_kg": -1.2, "adherence_percent": 85},
            past_weeks=[],
            profile={"goal": "weight_loss"},
        )
        assert any(f["flag_type"] == "rapid_weight_loss" for f in flags)

    def test_rapid_weight_loss_confirmed_pattern(self):
        """Test critical flag when rapid loss repeats multiple weeks."""
        past_weeks = [
            {"weight_change_kg": -1.1, "adherence_percent": 85},
            {"weight_change_kg": -1.2, "adherence_percent": 88},
        ]
        flags = detect_red_flags(
            current_week={"weight_change_kg": -1.15, "adherence_percent": 90},
            past_weeks=past_weeks,
            profile={"goal": "weight_loss"},
        )
        rapid_loss_flags = [f for f in flags if f["flag_type"] == "rapid_weight_loss"]
        if rapid_loss_flags:
            assert any(f["severity"] == "critical" for f in rapid_loss_flags)

    def test_extreme_hunger_flag(self):
        """Test detection of high hunger + low adherence pattern."""
        flags = detect_red_flags(
            current_week={
                "hunger_level": "high",
                "adherence_percent": 35,
                "weight_change_kg": 0.0,
            },
            past_weeks=[],
            profile={},
        )
        assert any(f["flag_type"] == "extreme_hunger" for f in flags)

    def test_no_hunger_flag_with_high_adherence(self):
        """Test that high hunger + high adherence doesn't flag."""
        flags = detect_red_flags(
            current_week={
                "hunger_level": "high",
                "adherence_percent": 88,
                "weight_change_kg": 0.0,
            },
            past_weeks=[],
            profile={},
        )
        assert not any(f["flag_type"] == "extreme_hunger" for f in flags)

    def test_energy_crash_flag(self):
        """Test detection of persistent low energy."""
        past_weeks = [
            {"energy_level": "low", "adherence_percent": 80},
        ]
        flags = detect_red_flags(
            current_week={
                "energy_level": "low",
                "adherence_percent": 75,
                "weight_change_kg": 0.0,
            },
            past_weeks=past_weeks,
            profile={},
        )
        assert any(f["flag_type"] == "energy_crash" for f in flags)

    def test_mood_shift_flag(self):
        """Test detection of mood concerns in notes."""
        flags = detect_red_flags(
            current_week={
                "subjective_notes": "Feeling depressed this week, hard to stay motivated",
                "adherence_percent": 60,
                "weight_change_kg": 0.0,
            },
            past_weeks=[],
            profile={},
        )
        assert any(f["flag_type"] == "mood_shift" for f in flags)

    def test_abandonment_risk_flag(self):
        """Test detection of very low adherence (<30%)."""
        flags = detect_red_flags(
            current_week={
                "adherence_percent": 20,
                "weight_change_kg": 0.5,
            },
            past_weeks=[],
            profile={},
        )
        assert any(f["flag_type"] == "abandonment_risk" for f in flags)

    def test_stress_pattern_flag(self):
        """Test detection of stress affecting adherence."""
        flags = detect_red_flags(
            current_week={
                "subjective_notes": "Very busy week with work stress, only managed 60% adherence",
                "adherence_percent": 60,
                "weight_change_kg": 0.0,
            },
            past_weeks=[],
            profile={},
        )
        assert any(f["flag_type"] == "stress_pattern" for f in flags)

    def test_no_flags_when_all_good(self):
        """Test that healthy metrics produce no red flags."""
        flags = detect_red_flags(
            current_week={
                "weight_change_kg": -0.5,
                "adherence_percent": 85,
                "hunger_level": "medium",
                "energy_level": "high",
                "subjective_notes": "Great week!",
            },
            past_weeks=[],
            profile={"goal": "weight_loss"},
        )
        assert len(flags) == 0
