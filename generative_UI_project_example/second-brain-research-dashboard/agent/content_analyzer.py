"""
Content Analyzer Module - Markdown content analysis with classification and entity extraction.

This module provides comprehensive parsing and analysis of Markdown documents,
extracting structured information, links, code blocks, tables, and entities.
"""

import re
from typing import Any
from pydantic import BaseModel, Field


class ContentAnalysis(BaseModel):
    """
    Pydantic model representing the complete analysis of a Markdown document.

    Contains extracted sections, links, code blocks, tables, and classification
    information for use in dashboard generation.
    """

    title: str = Field(
        description="The main title of the document (extracted from first H1 or inferred)"
    )

    document_type: str = Field(
        description="Classification of content (tutorial, research, article, guide, notes, etc.)"
    )

    sections: list[str] = Field(
        default_factory=list,
        description="List of section names extracted from headers"
    )

    links: list[str] = Field(
        default_factory=list,
        description="All extracted URLs from the document"
    )

    youtube_links: list[str] = Field(
        default_factory=list,
        description="Extracted YouTube URLs"
    )

    github_links: list[str] = Field(
        default_factory=list,
        description="Extracted GitHub URLs"
    )

    code_blocks: list[dict[str, str]] = Field(
        default_factory=list,
        description="Extracted code blocks with language and content"
    )

    tables: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Extracted table data with headers and rows"
    )

    entities: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Extracted entities (technologies, tools, concepts, etc.)"
    )


# Comprehensive regex patterns for link extraction
# Note: YouTube video IDs are typically 11 characters, but we allow 10-13 for edge cases
YOUTUBE_LINK_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?'
    r'(?:youtube\.com/(?:watch\?v=|embed/|v/|shorts/|live/)[a-zA-Z0-9_-]{6,13}|'
    r'youtu\.be/[a-zA-Z0-9_-]{6,13})'
    r'(?:[?&][^\s]*)?',
    re.IGNORECASE
)

GITHUB_LINK_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?(?:'
    r'github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(?:/[^\s)]*)?|'
    r'raw\.githubusercontent\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(?:/[^\s)]*)?|'
    r'gist\.github\.com/[a-zA-Z0-9_-]+(?:/[^\s)]*)?|'
    r'github\.io/[^\s)]*'
    r')',
    re.IGNORECASE
)

# Generic URL regex for all links
URL_REGEX = re.compile(
    r'(?:https?://|www\.)[^\s)\]]+',
    re.IGNORECASE
)

# Markdown link pattern [text](url)
MARKDOWN_LINK_REGEX = re.compile(
    r'\[([^\]]+)\]\(([^)]+)\)',
    re.IGNORECASE
)


def parse_markdown(content: str) -> dict[str, Any]:
    """
    Parse Markdown content to extract structural elements.

    Extracts sections (headers), links, code blocks, and tables using
    regex patterns and Markdown syntax rules.

    Args:
        content: Raw Markdown content as string

    Returns:
        Dictionary containing:
        - title: Document title (from first H1 or inferred)
        - sections: List of section names from headers
        - all_links: List of all extracted URLs
        - youtube_links: List of YouTube URLs
        - github_links: List of GitHub URLs
        - code_blocks: List of code block dictionaries
        - tables: List of table dictionaries
    """
    result = {
        'title': '',
        'sections': [],
        'all_links': [],
        'youtube_links': [],
        'github_links': [],
        'code_blocks': [],
        'tables': []
    }

    # Extract title (first H1 header)
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if title_match:
        result['title'] = title_match.group(1).strip()
    else:
        # Fallback: use first line or "Untitled"
        first_line = content.split('\n')[0].strip() if content else ''
        result['title'] = first_line[:100] if first_line else 'Untitled Document'

    # Extract all headers (sections)
    header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    headers = header_pattern.findall(content)
    result['sections'] = [header[1].strip() for header in headers]

    # Extract all links (from Markdown syntax [text](url))
    markdown_links = MARKDOWN_LINK_REGEX.findall(content)
    for text, url in markdown_links:
        result['all_links'].append(url.strip())

    # Also extract plain URLs in text
    plain_urls = URL_REGEX.findall(content)
    for url in plain_urls:
        cleaned_url = url.strip()
        if cleaned_url not in result['all_links']:
            result['all_links'].append(cleaned_url)

    # Extract YouTube links
    youtube_matches = YOUTUBE_LINK_REGEX.finditer(content)
    for match in youtube_matches:
        youtube_url = match.group(0)
        if youtube_url not in result['youtube_links']:
            result['youtube_links'].append(youtube_url)

    # Extract GitHub links
    github_matches = GITHUB_LINK_REGEX.finditer(content)
    for match in github_matches:
        github_url = match.group(0)
        if github_url not in result['github_links']:
            result['github_links'].append(github_url)

    # Extract code blocks with language specification
    code_block_pattern = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
    code_matches = code_block_pattern.findall(content)
    for language, code in code_matches:
        result['code_blocks'].append({
            'language': language.strip() if language else 'text',
            'code': code.strip()
        })

    # Extract tables (Markdown table syntax)
    # Simple table detection: lines with | separators
    table_pattern = re.compile(
        r'(\|.+\|[\r\n]+\|[-:\s|]+\|[\r\n]+(?:\|.+\|[\r\n]+)*)',
        re.MULTILINE
    )
    table_matches = table_pattern.findall(content)

    for table_text in table_matches:
        lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
        if len(lines) >= 2:
            # Parse header row
            header_row = lines[0]
            headers = [cell.strip() for cell in header_row.split('|') if cell.strip()]

            # Parse data rows (skip separator line at index 1)
            rows = []
            for line in lines[2:]:
                cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                if cells:
                    rows.append(cells)

            result['tables'].append({
                'headers': headers,
                'rows': rows,
                'row_count': len(rows)
            })

    return result


async def analyze_content(markdown: str, agent) -> ContentAnalysis:
    """
    Analyze Markdown content using LLM-based classification and entity extraction.

    This async function uses the Pydantic AI agent to perform advanced analysis
    including document classification and entity extraction.

    Args:
        markdown: Raw Markdown content to analyze
        agent: Pydantic AI agent instance for LLM-based analysis

    Returns:
        ContentAnalysis model with complete analysis results
    """
    # First, parse the markdown structure
    parsed = parse_markdown(markdown)

    # Use agent for LLM-based classification and entity extraction
    classification_prompt = f"""
    Analyze this markdown document and classify its type.

    Document title: {parsed['title']}
    Sections: {', '.join(parsed['sections'][:5])}

    Classify this document into one of these types:
    - tutorial: Step-by-step guides or how-to content
    - research: Academic papers, research notes, or analysis
    - article: Blog posts, news, or general articles
    - guide: Reference documentation or comprehensive guides
    - notes: Personal notes or quick references
    - technical_doc: Technical documentation or API references
    - overview: High-level summaries or overviews

    Respond with just the document type.
    """

    # Get classification from agent (if available)
    document_type = 'article'  # Default fallback

    if agent is not None:
        try:
            # Run agent to classify content
            from agent import AgentState

            state = AgentState(document_content=markdown)
            result = await agent.run(classification_prompt, deps=state)

            # Extract document type from result
            response_text = result.data.lower().strip()

            # Match against valid types
            valid_types = ['tutorial', 'research', 'article', 'guide', 'notes', 'technical_doc', 'overview']
            for doc_type in valid_types:
                if doc_type in response_text:
                    document_type = doc_type
                    break
        except Exception as e:
            print(f"Agent classification failed, using heuristic: {e}")
            # Fallback to heuristic classification
            document_type = _classify_heuristic(markdown, parsed)
    else:
        # Fallback to heuristic classification if agent not available
        document_type = _classify_heuristic(markdown, parsed)

    # Extract entities using pattern matching
    entities = _extract_entities(markdown)

    # Build ContentAnalysis model
    analysis = ContentAnalysis(
        title=parsed['title'],
        document_type=document_type,
        sections=parsed['sections'],
        links=parsed['all_links'],
        youtube_links=parsed['youtube_links'],
        github_links=parsed['github_links'],
        code_blocks=parsed['code_blocks'],
        tables=parsed['tables'],
        entities=entities
    )

    return analysis


def _classify_heuristic(markdown: str, parsed: dict[str, Any]) -> str:
    """
    Heuristic-based document classification fallback.

    Uses keyword patterns and structural analysis to classify documents
    when LLM-based classification is unavailable.

    Args:
        markdown: Raw markdown content
        parsed: Pre-parsed structural data

    Returns:
        Document type classification string
    """
    content_lower = markdown.lower()

    # Check for tutorial indicators
    tutorial_keywords = ['step', 'tutorial', 'how to', 'guide', 'lesson', 'walkthrough']
    if any(keyword in content_lower for keyword in tutorial_keywords):
        return 'tutorial'

    # Check for research indicators
    research_keywords = ['abstract', 'methodology', 'results', 'conclusion', 'references', 'citation']
    if any(keyword in content_lower for keyword in research_keywords):
        return 'research'

    # Check for technical documentation
    tech_doc_keywords = ['api', 'endpoint', 'parameter', 'function', 'class', 'method']
    if any(keyword in content_lower for keyword in tech_doc_keywords) and len(parsed['code_blocks']) >= 2:
        return 'technical_doc'

    # Check for code-heavy content (guides)
    if len(parsed['code_blocks']) >= 3:
        return 'guide'

    # Check for notes (short, list-heavy)
    if len(markdown) < 1000 and content_lower.count('\n- ') > 5:
        return 'notes'

    # Default to article
    return 'article'


def _extract_entities(markdown: str) -> dict[str, list[str]]:
    """
    Extract entities from markdown content using pattern matching.

    Identifies technologies, tools, programming languages, and key concepts
    mentioned in the document.

    Args:
        markdown: Raw markdown content

    Returns:
        Dictionary with entity categories and lists of extracted entities
    """
    entities = {
        'technologies': [],
        'tools': [],
        'languages': [],
        'concepts': []
    }

    # Common technology patterns
    tech_patterns = [
        'React', 'Vue', 'Angular', 'Node.js', 'Express', 'FastAPI', 'Django', 'Flask',
        'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Docker', 'Kubernetes', 'AWS', 'Azure',
        'TensorFlow', 'PyTorch', 'Scikit-learn', 'Pandas', 'NumPy', 'OpenAI', 'Claude',
        'TypeScript', 'JavaScript', 'Rust', 'Go', 'Java', 'C++', 'C#', 'Swift', 'Kotlin'
    ]

    # Tools patterns
    tool_patterns = [
        'Git', 'GitHub', 'GitLab', 'VS Code', 'IntelliJ', 'Webpack', 'Vite', 'npm', 'yarn',
        'pip', 'cargo', 'gradle', 'maven', 'Jenkins', 'CircleCI', 'Travis', 'Playwright',
        'Selenium', 'Jest', 'Pytest', 'JUnit', 'Postman', 'curl', 'Jupyter', 'Colab'
    ]

    # Programming languages
    language_patterns = [
        'Python', 'JavaScript', 'TypeScript', 'Java', 'C++', 'C#', 'Go', 'Rust', 'Ruby',
        'PHP', 'Swift', 'Kotlin', 'Scala', 'Perl', 'R', 'Julia', 'Haskell', 'Elixir',
        'Clojure', 'Dart', 'Lua', 'Shell', 'Bash', 'PowerShell', 'SQL', 'HTML', 'CSS'
    ]

    # Search for technologies
    for tech in tech_patterns:
        if re.search(r'\b' + re.escape(tech) + r'\b', markdown, re.IGNORECASE):
            if tech not in entities['technologies']:
                entities['technologies'].append(tech)

    # Search for tools
    for tool in tool_patterns:
        if re.search(r'\b' + re.escape(tool) + r'\b', markdown, re.IGNORECASE):
            if tool not in entities['tools']:
                entities['tools'].append(tool)

    # Search for languages
    for lang in language_patterns:
        if re.search(r'\b' + re.escape(lang) + r'\b', markdown, re.IGNORECASE):
            if lang not in entities['languages']:
                entities['languages'].append(lang)

    # Extract concepts from headers
    header_pattern = re.compile(r'^#{1,6}\s+(.+)$', re.MULTILINE)
    headers = header_pattern.findall(markdown)
    for header in headers[:10]:  # Top 10 headers as concepts
        cleaned = header.strip()
        if len(cleaned) > 3 and cleaned not in entities['concepts']:
            entities['concepts'].append(cleaned)

    return entities


# Exported regex patterns for external use
youtube_link_extraction_regex = YOUTUBE_LINK_REGEX
github_link_extraction_regex = GITHUB_LINK_REGEX
