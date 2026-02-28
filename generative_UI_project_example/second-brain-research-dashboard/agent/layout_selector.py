"""
Layout Selector Module - Select optimal layouts based on content analysis.

This module provides rule-based and LLM-powered layout selection for
transforming analyzed Markdown content into appropriate dashboard layouts.
"""

from pydantic import BaseModel, Field
from content_analyzer import ContentAnalysis


class LayoutDecision(BaseModel):
    """
    Pydantic model representing a layout selection decision.

    Contains the selected layout type, confidence score, reasoning,
    alternative layouts, and suggested A2UI components.
    """

    layout_type: str = Field(
        description="The selected layout type (e.g., 'instructional_layout', 'data_layout', 'news_layout')"
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for this layout selection (0.0-1.0)"
    )

    reasoning: str = Field(
        description="Explanation of why this layout was chosen"
    )

    alternative_layouts: list[str] = Field(
        default_factory=list,
        description="Fallback layout options if the primary choice doesn't fit"
    )

    component_suggestions: list[str] = Field(
        default_factory=list,
        description="Suggested A2UI components for this layout"
    )


# Content type to layout mappings
LAYOUT_MAPPINGS = {
    'tutorial': {
        'layout': 'instructional_layout',
        'components': ['CodeBlock', 'StepList', 'ProgressTracker', 'Highlight', 'CollapsibleSection']
    },
    'research': {
        'layout': 'data_layout',
        'components': ['DataTable', 'StatCard', 'ComparisonChart', 'Citation', 'Graph']
    },
    'article': {
        'layout': 'news_layout',
        'components': ['Hero', 'ImageGallery', 'Quote', 'RelatedLinks', 'ShareButtons']
    },
    'guide': {
        'layout': 'list_layout',
        'components': ['OrderedList', 'Checklist', 'Accordion', 'SideNav', 'CalloutBox']
    },
    'notes': {
        'layout': 'summary_layout',
        'components': ['KeyPoints', 'TagCloud', 'QuickReference', 'Highlight', 'MiniCard']
    },
    'technical_doc': {
        'layout': 'reference_layout',
        'components': ['CodeBlock', 'ApiTable', 'TabbedContent', 'SideNav', 'SearchBar']
    },
    'overview': {
        'layout': 'media_layout',
        'components': ['Hero', 'MediaEmbed', 'Highlight', 'Card', 'Timeline']
    }
}


def _apply_rule_based_selection(content_analysis: ContentAnalysis) -> LayoutDecision | None:
    """
    Apply rule-based logic to select a layout based on content metrics.

    Fast, deterministic selection using structural analysis:
    - Code block count (>5 → instructional)
    - Table count (>2 → data)
    - Media links (>3 → media)
    - Section count (>10 → reference)
    - Default → summary

    Args:
        content_analysis: ContentAnalysis model with parsed content

    Returns:
        LayoutDecision if a rule matches, None otherwise
    """
    code_block_count = len(content_analysis.code_blocks)
    table_count = len(content_analysis.tables)
    media_count = len(content_analysis.youtube_links) + len(content_analysis.github_links)
    section_count = len(content_analysis.sections)

    # Rule 1: Code-heavy content → instructional layout
    if code_block_count > 5:
        return LayoutDecision(
            layout_type='instructional_layout',
            confidence=0.9,
            reasoning=f'High code block count ({code_block_count}) indicates tutorial/instructional content',
            alternative_layouts=['reference_layout', 'list_layout'],
            component_suggestions=['CodeBlock', 'StepList', 'ProgressTracker', 'Highlight', 'CollapsibleSection']
        )

    # Rule 2: Table-heavy content → data layout
    if table_count > 2:
        return LayoutDecision(
            layout_type='data_layout',
            confidence=0.85,
            reasoning=f'High table count ({table_count}) indicates data/research content',
            alternative_layouts=['reference_layout', 'summary_layout'],
            component_suggestions=['DataTable', 'StatCard', 'ComparisonChart', 'Citation', 'Graph']
        )

    # Rule 3: Media-rich content → media layout
    if media_count > 3:
        return LayoutDecision(
            layout_type='media_layout',
            confidence=0.88,
            reasoning=f'High media link count ({media_count}) indicates visual/overview content',
            alternative_layouts=['news_layout', 'summary_layout'],
            component_suggestions=['Hero', 'MediaEmbed', 'Highlight', 'Card', 'Timeline']
        )

    # Rule 4: Many sections → reference layout
    if section_count > 10:
        return LayoutDecision(
            layout_type='reference_layout',
            confidence=0.82,
            reasoning=f'High section count ({section_count}) indicates technical documentation',
            alternative_layouts=['list_layout', 'instructional_layout'],
            component_suggestions=['CodeBlock', 'ApiTable', 'TabbedContent', 'SideNav', 'SearchBar']
        )

    # No rule matched
    return None


def _get_layout_from_document_type(content_analysis: ContentAnalysis) -> LayoutDecision:
    """
    Get layout based on document type classification.

    Uses the document_type from ContentAnalysis to map to the appropriate
    layout using LAYOUT_MAPPINGS.

    Args:
        content_analysis: ContentAnalysis model with document_type

    Returns:
        LayoutDecision based on document type
    """
    doc_type = content_analysis.document_type
    mapping = LAYOUT_MAPPINGS.get(doc_type)

    if mapping:
        # Find alternative layouts (exclude the selected one)
        alternatives = [
            layout_info['layout']
            for dt, layout_info in LAYOUT_MAPPINGS.items()
            if dt != doc_type
        ][:3]  # Top 3 alternatives

        return LayoutDecision(
            layout_type=mapping['layout'],
            confidence=0.75,
            reasoning=f"Document classified as '{doc_type}', mapped to {mapping['layout']}",
            alternative_layouts=alternatives,
            component_suggestions=mapping['components']
        )

    # Fallback to summary layout
    return LayoutDecision(
        layout_type='summary_layout',
        confidence=0.6,
        reasoning=f"Unknown document type '{doc_type}', using default summary layout",
        alternative_layouts=['news_layout', 'list_layout', 'media_layout'],
        component_suggestions=['KeyPoints', 'TagCloud', 'QuickReference', 'Highlight', 'MiniCard']
    )


async def _select_layout_with_llm(content_analysis: ContentAnalysis, agent) -> LayoutDecision:
    """
    Use LLM to select layout for ambiguous cases.

    Falls back to LLM-based reasoning when rule-based selection is uncertain
    or when content characteristics don't clearly match a layout pattern.

    Args:
        content_analysis: ContentAnalysis model with parsed content
        agent: Pydantic AI agent instance

    Returns:
        LayoutDecision from LLM analysis
    """
    from agent import AgentState

    # Build a prompt with content characteristics
    prompt = f"""
    Analyze this content and select the best layout type for a dashboard.

    Content characteristics:
    - Document type: {content_analysis.document_type}
    - Title: {content_analysis.title}
    - Sections: {len(content_analysis.sections)} ({', '.join(content_analysis.sections[:5])})
    - Code blocks: {len(content_analysis.code_blocks)}
    - Tables: {len(content_analysis.tables)}
    - Links: {len(content_analysis.links)}
    - YouTube links: {len(content_analysis.youtube_links)}
    - GitHub links: {len(content_analysis.github_links)}

    Available layout types:
    1. instructional_layout - for tutorials with code blocks and step-by-step instructions
    2. data_layout - for research with tables, statistics, and comparisons
    3. news_layout - for articles with headlines and media
    4. list_layout - for guides with ordered steps
    5. summary_layout - for notes with key points
    6. reference_layout - for technical docs with many sections
    7. media_layout - for overviews with visual content

    Select the BEST layout type and explain why. Format your response as:
    LAYOUT: [layout_type]
    CONFIDENCE: [0.0-1.0]
    REASONING: [explanation]
    ALTERNATIVES: [layout1, layout2, layout3]
    """

    try:
        # Run agent with prompt
        state = AgentState(document_content=content_analysis.title)
        result = await agent.run(prompt, deps=state)
        response_text = result.data

        # Parse response
        layout_type = 'summary_layout'
        confidence = 0.7
        reasoning = 'LLM-based selection'
        alternatives = []

        # Extract layout type
        if 'LAYOUT:' in response_text:
            layout_line = [line for line in response_text.split('\n') if 'LAYOUT:' in line][0]
            layout_type = layout_line.split('LAYOUT:')[1].strip()

        # Extract confidence
        if 'CONFIDENCE:' in response_text:
            conf_line = [line for line in response_text.split('\n') if 'CONFIDENCE:' in line][0]
            try:
                confidence = float(conf_line.split('CONFIDENCE:')[1].strip())
            except ValueError:
                confidence = 0.7

        # Extract reasoning
        if 'REASONING:' in response_text:
            reasoning_line = [line for line in response_text.split('\n') if 'REASONING:' in line][0]
            reasoning = reasoning_line.split('REASONING:')[1].strip()

        # Extract alternatives
        if 'ALTERNATIVES:' in response_text:
            alt_line = [line for line in response_text.split('\n') if 'ALTERNATIVES:' in line][0]
            alt_text = alt_line.split('ALTERNATIVES:')[1].strip()
            alternatives = [alt.strip() for alt in alt_text.split(',')]

        # Get component suggestions from mapping
        components = []
        for doc_type, mapping in LAYOUT_MAPPINGS.items():
            if mapping['layout'] == layout_type:
                components = mapping['components']
                break

        return LayoutDecision(
            layout_type=layout_type,
            confidence=confidence,
            reasoning=f"LLM analysis: {reasoning}",
            alternative_layouts=alternatives[:3],
            component_suggestions=components or ['Card', 'Text', 'Highlight']
        )

    except Exception as e:
        print(f"LLM layout selection failed: {e}")
        # Fallback to document type mapping
        return _get_layout_from_document_type(content_analysis)


async def select_layout(content_analysis: ContentAnalysis, agent=None) -> LayoutDecision:
    """
    Select the optimal layout for content using rule-based and LLM logic.

    Selection strategy:
    1. Try rule-based selection first (fast, deterministic)
    2. If no clear rule matches, use document type mapping
    3. For ambiguous cases with agent available, use LLM
    4. Return LayoutDecision with reasoning and suggestions

    Args:
        content_analysis: ContentAnalysis model with parsed content
        agent: Optional Pydantic AI agent for LLM-based selection

    Returns:
        LayoutDecision with selected layout and metadata
    """
    # Step 1: Try rule-based selection
    rule_decision = _apply_rule_based_selection(content_analysis)

    if rule_decision and rule_decision.confidence >= 0.85:
        # High-confidence rule match, use it
        return rule_decision

    # Step 2: Try document type mapping
    type_decision = _get_layout_from_document_type(content_analysis)

    # Step 3: If we have a rule decision with decent confidence, use it
    if rule_decision and rule_decision.confidence >= 0.8:
        return rule_decision

    # Step 4: If agent available and confidence is low, use LLM
    if agent is not None and type_decision.confidence < 0.75:
        llm_decision = await _select_layout_with_llm(content_analysis, agent)
        return llm_decision

    # Step 5: Use the best available decision
    if rule_decision and rule_decision.confidence > type_decision.confidence:
        return rule_decision

    return type_decision
