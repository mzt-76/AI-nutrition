"""
Second Brain Agent - Pydantic AI agent with AG-UI protocol support.

This agent uses StateDeps for bidirectional state sync with the frontend
via the AG-UI protocol, enabling seamless CopilotKit integration.
"""

import os
from typing import Any
from uuid import uuid4
from datetime import datetime
from textwrap import dedent

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.models.openai import OpenAIModel
from ag_ui.core import EventType, StateSnapshotEvent

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


class DashboardState(BaseModel):
    """
    Shared state between frontend and agent.

    This state is synchronized bidirectionally via AG-UI protocol.
    The frontend can read and update this state, and the agent
    can emit StateSnapshot events to update it.
    """
    # Document info
    markdown_content: str = ""
    document_title: str = ""
    document_type: str = ""  # tutorial, research, article, etc.

    # Analysis results
    content_analysis: dict[str, Any] = Field(default_factory=dict)
    layout_type: str = ""  # instructional, data, news, etc.

    # Generated components (A2UI format)
    components: list[dict[str, Any]] = Field(default_factory=list)

    # Processing status
    status: str = "idle"  # idle, analyzing, generating, complete, error
    progress: int = 0  # 0-100
    current_step: str = ""

    # Activity log for frontend rendering
    activity_log: list[dict[str, Any]] = Field(default_factory=list)

    # Error tracking
    error_message: str | None = None


def create_openrouter_model() -> OpenAIModel:
    """Create OpenRouter model instance."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable required")

    model_name = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4")
    return OpenAIModel(model_name, provider='openrouter')


# Create the agent with StateDeps for AG-UI integration
agent = Agent(
    model=create_openrouter_model(),
    deps_type=StateDeps[DashboardState],
    system_prompt=dedent("""
        You are a specialized AI assistant that transforms Markdown research documents
        into interactive dashboard components.

        Your workflow:
        1. Analyze the markdown content to understand its structure and type
        2. Generate A2UI dashboard components that best represent the information

        When the user provides markdown content:
        1. First call analyze_content() to understand and classify the document
        2. Then call generate_components() to create the UI components

        Always explain what you're doing as you work. The user can see the dashboard
        being built in real-time as you generate components.
    """).strip()
)


@agent.tool
def get_markdown_content(ctx: RunContext[StateDeps[DashboardState]]) -> str:
    """Get the current markdown content from state."""
    content = ctx.deps.state.markdown_content
    print(f"[TOOL] get_markdown_content: {len(content)} chars")
    return content if content else "No markdown content provided yet."


@agent.tool
async def analyze_content(ctx: RunContext[StateDeps[DashboardState]]) -> StateSnapshotEvent:
    """
    Analyze the markdown content to determine document type and extract key elements.
    Updates the shared state with analysis results.
    """
    from content_analyzer import parse_markdown
    from llm_orchestrator import analyze_content_with_llm

    state = ctx.deps.state
    markdown = state.markdown_content

    print(f"[TOOL] analyze_content: analyzing {len(markdown)} chars")

    # Update state to show we're analyzing
    state.status = "analyzing"
    state.progress = 20
    state.current_step = "Analyzing document structure..."
    state.activity_log.append({
        "id": str(uuid4()),
        "message": "Starting content analysis",
        "timestamp": datetime.now().isoformat(),
        "status": "in_progress"
    })

    # Parse markdown structure
    parsed = parse_markdown(markdown)

    # Get LLM analysis
    analysis = await analyze_content_with_llm(markdown)

    # Update state with results
    state.document_title = parsed.get("title", "Untitled")
    state.document_type = analysis.get("document_type", "article")
    state.content_analysis = {
        **parsed,
        **analysis
    }
    state.progress = 40
    state.current_step = f"Document classified as: {state.document_type}"
    state.activity_log.append({
        "id": str(uuid4()),
        "message": f"Analysis complete: {state.document_type}",
        "timestamp": datetime.now().isoformat(),
        "status": "completed"
    })

    print(f"[TOOL] analyze_content: document_type={state.document_type}")

    # Return StateSnapshotEvent to sync state with frontend
    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=state,
    )


@agent.tool
async def generate_components(ctx: RunContext[StateDeps[DashboardState]]) -> StateSnapshotEvent:
    """
    Generate A2UI dashboard components based on the analyzed content.
    Each component is added to state and synced with the frontend.
    """
    from llm_orchestrator import orchestrate_dashboard_with_llm

    state = ctx.deps.state

    print(f"[TOOL] generate_components: starting")

    # Update status
    state.status = "generating"
    state.current_step = "Generating dashboard components..."
    state.progress = 50
    state.components = []  # Clear existing

    # Generate components using the orchestrator
    component_count = 0
    async for component in orchestrate_dashboard_with_llm(state.markdown_content):
        component_count += 1

        # Convert component to dict
        component_dict = {
            "type": component.type,
            "id": component.id,
            "props": component.props,
        }
        if component.layout:
            component_dict["layout"] = component.layout
        if component.zone:
            component_dict["zone"] = component.zone

        state.components.append(component_dict)
        state.progress = min(50 + (component_count * 3), 95)
        state.current_step = f"Generated {component.type}"

        print(f"[TOOL] generate_components: added {component.type}")

    # Final status
    state.status = "complete"
    state.progress = 100
    state.current_step = "Dashboard complete!"
    state.activity_log.append({
        "id": str(uuid4()),
        "message": f"Generated {component_count} components",
        "timestamp": datetime.now().isoformat(),
        "status": "completed"
    })

    print(f"[TOOL] generate_components: complete with {component_count} components")

    # Return StateSnapshotEvent to sync final state with frontend
    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=state,
    )
