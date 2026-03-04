"""UI component marker extraction for generative UI.

Extracts <!--UI:ComponentName:{json}--> markers from agent text responses
and returns cleaned text + structured component list for frontend rendering.
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

UI_MARKER_PATTERN = re.compile(r"<!--UI:(\w+):(\{.*?\})-->", re.DOTALL)

ZONE_MAP: dict[str, str] = {
    "NutritionSummaryCard": "hero",
    "MacroGauges": "macros",
    "MealCard": "meals",
    "DayPlanCard": "meals",
    "WeightTrendIndicator": "progress",
    "AdjustmentCard": "progress",
    "QuickReplyChips": "actions",
}


def _infer_zone(component_name: str) -> str:
    return ZONE_MAP.get(component_name, "content")


def extract_ui_components(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Extract <!--UI:ComponentName:{json}--> markers from text.

    Single-pass: builds cleaned text and component list simultaneously
    using match offsets. Returns (cleaned_text, components_list).
    """
    components: list[dict[str, Any]] = []
    counter: dict[str, int] = {}
    parts: list[str] = []
    last_end = 0

    for match in UI_MARKER_PATTERN.finditer(text):
        parts.append(text[last_end : match.start()])
        last_end = match.end()

        component_name = match.group(1)
        json_str = match.group(2)
        try:
            props = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning(
                f"Malformed JSON in UI marker for {component_name}, skipping"
            )
            continue

        count = counter.get(component_name, 0)
        counter[component_name] = count + 1
        component_id = f"{component_name.lower()}-{count}"

        components.append(
            {
                "id": component_id,
                "component": component_name,
                "props": props,
                "zone": _infer_zone(component_name),
            }
        )

    parts.append(text[last_end:])
    cleaned = "".join(parts).strip()
    return cleaned, components
