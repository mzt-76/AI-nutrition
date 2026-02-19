"""Analyze images via GPT-4 Vision for body composition estimation.

Utility script — can be imported by agent tool wrapper or run standalone.
Uses GPT-4o-mini (or configurable model) for visual analysis.

Source: Extracted from src/tools.py image_analysis_tool
"""

import os
import logging

logger = logging.getLogger(__name__)


async def execute(**kwargs) -> str:
    """Analyze image using GPT-4 Vision.

    Args:
        image_url: URL to the image (Google Drive or direct URL).
        analysis_prompt: What to analyze (e.g., "Estimate body fat percentage").
        openai_client: AsyncOpenAI client.

    Returns:
        Analysis result text.
    """
    image_url = kwargs["image_url"]
    analysis_prompt = kwargs["analysis_prompt"]
    openai_client = kwargs["openai_client"]

    try:
        logger.info(f"Image analysis: {analysis_prompt[:50]}...")

        response = await openai_client.chat.completions.create(
            model=os.getenv("VISION_LLM_CHOICE", "gpt-4o-mini"),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": analysis_prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            max_tokens=1500,
        )

        result = response.choices[0].message.content

        logger.info("Image analysis complete")

        return result

    except Exception as e:
        logger.error(f"Image analysis error: {e}", exc_info=True)
        return f"Image analysis error: {str(e)}"
