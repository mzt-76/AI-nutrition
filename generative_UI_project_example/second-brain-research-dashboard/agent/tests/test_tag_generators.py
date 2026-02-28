"""
Tests for A2UI Tag Generator Module.

Comprehensive test suite for tag and badge component generators covering:
- Tag component generation with various styles
- Badge component generation with count indicators
- Category tag generation with colors and icons
- Status indicator generation
- Priority badge generation
- Parameter validation and edge cases
"""

import pytest
from a2ui_generator import (
    reset_id_counter,
    generate_tag,
    generate_badge,
    generate_category_tag,
    generate_status_indicator,
    generate_priority_badge,
)


class TestTagGenerators:
    """Test suite for tag and badge component generators."""

    # ========================================================================
    # Tag Generator Tests
    # ========================================================================

    def test_generate_tag_basic(self):
        """Test basic tag generation with default type."""
        reset_id_counter()

        tag = generate_tag(label="JavaScript")

        assert tag.type == "a2ui.Tag"
        assert tag.props["label"] == "JavaScript"
        assert tag.props["type"] == "default"
        assert "icon" not in tag.props
        assert "removable" not in tag.props

    def test_generate_tag_with_type_variants(self):
        """Test tag generation with all valid type variants."""
        reset_id_counter()

        valid_types = ["default", "primary", "success", "warning", "error", "info"]
        for tag_type in valid_types:
            tag = generate_tag(label="Test", type=tag_type)
            assert tag.props["type"] == tag_type

    def test_generate_tag_with_icon(self):
        """Test tag with icon."""
        reset_id_counter()

        tag = generate_tag(
            label="Featured",
            type="primary",
            icon="star"
        )

        assert tag.props["icon"] == "star"
        assert tag.props["label"] == "Featured"
        assert tag.props["type"] == "primary"

    def test_generate_tag_removable(self):
        """Test removable tag."""
        reset_id_counter()

        tag = generate_tag(
            label="Filter: Python",
            type="info",
            removable=True
        )

        assert tag.props["removable"] is True
        assert tag.props["label"] == "Filter: Python"

    def test_generate_tag_non_removable_by_default(self):
        """Test that tags are not removable by default."""
        reset_id_counter()

        tag = generate_tag(label="Test")

        assert "removable" not in tag.props

    def test_generate_tag_empty_label(self):
        """Test tag with empty label raises error."""
        with pytest.raises(ValueError, match="Tag label cannot be empty"):
            generate_tag(label="")

        with pytest.raises(ValueError, match="Tag label cannot be empty"):
            generate_tag(label="   ")

    def test_generate_tag_invalid_type(self):
        """Test tag with invalid type raises error."""
        with pytest.raises(ValueError, match="Tag type must be one of"):
            generate_tag(label="Test", type="invalid")

    def test_generate_tag_label_whitespace_trimmed(self):
        """Test that tag label whitespace is trimmed."""
        reset_id_counter()

        tag = generate_tag(label="  Python  ")

        assert tag.props["label"] == "Python"

    # ========================================================================
    # Badge Generator Tests
    # ========================================================================

    def test_generate_badge_basic(self):
        """Test basic badge generation."""
        reset_id_counter()

        badge = generate_badge(label="Notifications", count=5)

        assert badge.type == "a2ui.Badge"
        assert badge.props["label"] == "Notifications"
        assert badge.props["count"] == 5
        assert badge.props["style"] == "default"
        assert badge.props["size"] == "medium"

    def test_generate_badge_with_style_variants(self):
        """Test badge generation with all valid style variants."""
        reset_id_counter()

        valid_styles = ["default", "primary", "success", "warning", "error"]
        for style in valid_styles:
            badge = generate_badge(label="Test", count=1, style=style)
            assert badge.props["style"] == style

    def test_generate_badge_with_size_variants(self):
        """Test badge generation with all valid size variants."""
        reset_id_counter()

        valid_sizes = ["small", "medium", "large"]
        for size in valid_sizes:
            badge = generate_badge(label="Test", count=1, size=size)
            assert badge.props["size"] == size

    def test_generate_badge_zero_count(self):
        """Test badge with zero count."""
        reset_id_counter()

        badge = generate_badge(label="Done", count=0)

        assert badge.props["count"] == 0

    def test_generate_badge_large_count(self):
        """Test badge with large count."""
        reset_id_counter()

        badge = generate_badge(label="Stars", count=99999)

        assert badge.props["count"] == 99999

    def test_generate_badge_negative_count(self):
        """Test badge with negative count raises error."""
        with pytest.raises(ValueError, match="Badge count must be non-negative"):
            generate_badge(label="Test", count=-1)

    def test_generate_badge_empty_label(self):
        """Test badge with empty label raises error."""
        with pytest.raises(ValueError, match="Badge label cannot be empty"):
            generate_badge(label="", count=5)

        with pytest.raises(ValueError, match="Badge label cannot be empty"):
            generate_badge(label="   ", count=5)

    def test_generate_badge_invalid_style(self):
        """Test badge with invalid style raises error."""
        with pytest.raises(ValueError, match="Badge style must be one of"):
            generate_badge(label="Test", count=5, style="invalid")

    def test_generate_badge_invalid_size(self):
        """Test badge with invalid size raises error."""
        with pytest.raises(ValueError, match="Badge size must be one of"):
            generate_badge(label="Test", count=5, size="extra-large")

    def test_generate_badge_label_whitespace_trimmed(self):
        """Test that badge label whitespace is trimmed."""
        reset_id_counter()

        badge = generate_badge(label="  Unread  ", count=10)

        assert badge.props["label"] == "Unread"

    # ========================================================================
    # CategoryTag Generator Tests
    # ========================================================================

    def test_generate_category_tag_basic(self):
        """Test basic category tag generation."""
        reset_id_counter()

        tag = generate_category_tag(name="Technology")

        assert tag.type == "a2ui.CategoryTag"
        assert tag.props["name"] == "Technology"
        assert "color" not in tag.props
        assert "icon" not in tag.props

    def test_generate_category_tag_with_semantic_color(self):
        """Test category tag with semantic color name."""
        reset_id_counter()

        tag = generate_category_tag(name="AI & ML", color="blue")

        assert tag.props["color"] == "blue"
        assert tag.props["name"] == "AI & ML"

    def test_generate_category_tag_with_hex_color(self):
        """Test category tag with hex color code."""
        reset_id_counter()

        tag = generate_category_tag(name="Science", color="#3B82F6")

        assert tag.props["color"] == "#3B82F6"

    def test_generate_category_tag_with_short_hex_color(self):
        """Test category tag with 3-digit hex color."""
        reset_id_counter()

        tag = generate_category_tag(name="Design", color="#F00")

        assert tag.props["color"] == "#F00"

    def test_generate_category_tag_with_icon(self):
        """Test category tag with icon."""
        reset_id_counter()

        tag = generate_category_tag(
            name="Education",
            icon="book"
        )

        assert tag.props["icon"] == "book"
        assert "color" not in tag.props

    def test_generate_category_tag_with_color_and_icon(self):
        """Test category tag with both color and icon."""
        reset_id_counter()

        tag = generate_category_tag(
            name="Science",
            color="purple",
            icon="flask"
        )

        assert tag.props["color"] == "purple"
        assert tag.props["icon"] == "flask"

    def test_generate_category_tag_empty_name(self):
        """Test category tag with empty name raises error."""
        with pytest.raises(ValueError, match="CategoryTag name cannot be empty"):
            generate_category_tag(name="")

        with pytest.raises(ValueError, match="CategoryTag name cannot be empty"):
            generate_category_tag(name="   ")

    def test_generate_category_tag_invalid_hex_color(self):
        """Test category tag with invalid hex color raises error."""
        with pytest.raises(ValueError, match="Invalid hex color format"):
            generate_category_tag(name="Test", color="#GGG")

        with pytest.raises(ValueError, match="Invalid hex color format"):
            generate_category_tag(name="Test", color="#12345")

        with pytest.raises(ValueError, match="Invalid hex color format"):
            generate_category_tag(name="Test", color="#1234567")

    def test_generate_category_tag_name_whitespace_trimmed(self):
        """Test that category tag name whitespace is trimmed."""
        reset_id_counter()

        tag = generate_category_tag(name="  Business  ")

        assert tag.props["name"] == "Business"

    # ========================================================================
    # StatusIndicator Generator Tests
    # ========================================================================

    def test_generate_status_indicator_basic(self):
        """Test basic status indicator generation."""
        reset_id_counter()

        indicator = generate_status_indicator(status="success")

        assert indicator.type == "a2ui.StatusIndicator"
        assert indicator.props["status"] == "success"
        assert "label" not in indicator.props

    def test_generate_status_indicator_all_statuses(self):
        """Test status indicator with all valid status types."""
        reset_id_counter()

        valid_statuses = ["success", "warning", "error", "info", "loading"]
        for status in valid_statuses:
            indicator = generate_status_indicator(status=status)
            assert indicator.props["status"] == status

    def test_generate_status_indicator_with_custom_label(self):
        """Test status indicator with custom label."""
        reset_id_counter()

        indicator = generate_status_indicator(
            status="success",
            label="Deployment Complete"
        )

        assert indicator.props["label"] == "Deployment Complete"
        assert indicator.props["status"] == "success"

    def test_generate_status_indicator_warning_with_label(self):
        """Test warning status with custom label."""
        reset_id_counter()

        indicator = generate_status_indicator(
            status="warning",
            label="Maintenance Mode"
        )

        assert indicator.props["status"] == "warning"
        assert indicator.props["label"] == "Maintenance Mode"

    def test_generate_status_indicator_error_with_label(self):
        """Test error status with custom label."""
        reset_id_counter()

        indicator = generate_status_indicator(
            status="error",
            label="Connection Failed"
        )

        assert indicator.props["status"] == "error"
        assert indicator.props["label"] == "Connection Failed"

    def test_generate_status_indicator_loading_with_label(self):
        """Test loading status with custom label."""
        reset_id_counter()

        indicator = generate_status_indicator(
            status="loading",
            label="Fetching data..."
        )

        assert indicator.props["status"] == "loading"
        assert indicator.props["label"] == "Fetching data..."

    def test_generate_status_indicator_invalid_status(self):
        """Test status indicator with invalid status raises error."""
        with pytest.raises(ValueError, match="StatusIndicator status must be one of"):
            generate_status_indicator(status="invalid")

    def test_generate_status_indicator_empty_label(self):
        """Test status indicator with empty label raises error."""
        with pytest.raises(ValueError, match="StatusIndicator label cannot be empty"):
            generate_status_indicator(status="success", label="")

        with pytest.raises(ValueError, match="StatusIndicator label cannot be empty"):
            generate_status_indicator(status="success", label="   ")

    def test_generate_status_indicator_label_whitespace_trimmed(self):
        """Test that status indicator label whitespace is trimmed."""
        reset_id_counter()

        indicator = generate_status_indicator(
            status="info",
            label="  Processing  "
        )

        assert indicator.props["label"] == "Processing"

    # ========================================================================
    # PriorityBadge Generator Tests
    # ========================================================================

    def test_generate_priority_badge_basic(self):
        """Test basic priority badge generation."""
        reset_id_counter()

        badge = generate_priority_badge(level="medium")

        assert badge.type == "a2ui.PriorityBadge"
        assert badge.props["level"] == "medium"
        assert "label" not in badge.props

    def test_generate_priority_badge_all_levels(self):
        """Test priority badge with all valid levels."""
        reset_id_counter()

        valid_levels = ["low", "medium", "high", "critical"]
        for level in valid_levels:
            badge = generate_priority_badge(level=level)
            assert badge.props["level"] == level

    def test_generate_priority_badge_with_custom_label(self):
        """Test priority badge with custom label."""
        reset_id_counter()

        badge = generate_priority_badge(
            level="high",
            label="Urgent"
        )

        assert badge.props["label"] == "Urgent"
        assert badge.props["level"] == "high"

    def test_generate_priority_badge_critical_with_label(self):
        """Test critical priority with custom label."""
        reset_id_counter()

        badge = generate_priority_badge(
            level="critical",
            label="Critical - Act Now"
        )

        assert badge.props["level"] == "critical"
        assert badge.props["label"] == "Critical - Act Now"

    def test_generate_priority_badge_low_with_label(self):
        """Test low priority with custom label."""
        reset_id_counter()

        badge = generate_priority_badge(
            level="low",
            label="Nice to Have"
        )

        assert badge.props["level"] == "low"
        assert badge.props["label"] == "Nice to Have"

    def test_generate_priority_badge_medium_with_label(self):
        """Test medium priority with custom label."""
        reset_id_counter()

        badge = generate_priority_badge(
            level="medium",
            label="Normal Priority"
        )

        assert badge.props["level"] == "medium"
        assert badge.props["label"] == "Normal Priority"

    def test_generate_priority_badge_invalid_level(self):
        """Test priority badge with invalid level raises error."""
        with pytest.raises(ValueError, match="PriorityBadge level must be one of"):
            generate_priority_badge(level="invalid")

        with pytest.raises(ValueError, match="PriorityBadge level must be one of"):
            generate_priority_badge(level="urgent")

    def test_generate_priority_badge_empty_label(self):
        """Test priority badge with empty label raises error."""
        with pytest.raises(ValueError, match="PriorityBadge label cannot be empty"):
            generate_priority_badge(level="high", label="")

        with pytest.raises(ValueError, match="PriorityBadge label cannot be empty"):
            generate_priority_badge(level="high", label="   ")

    def test_generate_priority_badge_label_whitespace_trimmed(self):
        """Test that priority badge label whitespace is trimmed."""
        reset_id_counter()

        badge = generate_priority_badge(
            level="medium",
            label="  Standard  "
        )

        assert badge.props["label"] == "Standard"
