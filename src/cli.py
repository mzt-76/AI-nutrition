#!/usr/bin/env python3
"""
Rich CLI chat interface for AI Nutrition Assistant.

Interactive terminal chat with real-time streaming and tool call visibility.
Adapted from custom-agent-with-skills CLI pattern.

Usage:
    python -m src.cli
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from pydantic_ai import Agent
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPartDelta

# Load environment variables
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env", override=True)

from src.agent import agent, create_agent_deps
from src.clients import get_memory_client

# Setup logging - only show warnings+ to keep terminal clean
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Force UTF-8 encoding on Windows/WSL
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console(force_terminal=True)

USER_ID = "cli_user"


def load_memories(memory, query: str) -> str:
    """Load relevant memories for the current query.

    Args:
        memory: mem0 Memory client
        query: User's message to search relevant memories for

    Returns:
        Formatted string of relevant memories, or empty string
    """
    try:
        relevant = memory.search(query=query, user_id=USER_ID, limit=3)
        if relevant and relevant.get("results"):
            return "\n".join(f"- {entry['memory']}" for entry in relevant["results"])
    except Exception as e:
        logger.warning(f"Could not load memories: {e}")
    return ""


def save_memory(memory, user_message: str, agent_response: str = "") -> None:
    """Save conversation turn to long-term memory (only if potentially useful).

    Filters out trivial messages (short confirmations, generic requests) and
    sends user+agent pair so mem0 has full context to extract facts.

    Args:
        memory: mem0 Memory client
        user_message: User message
        agent_response: Agent response (provides context for extraction)
    """
    # Skip trivial messages — no useful facts to extract
    stripped = user_message.strip().lower()
    if len(stripped) < 15 and stripped in (
        "oui",
        "non",
        "ok",
        "merci",
        "yes",
        "no",
        "thanks",
        "d'accord",
        "c'est bon",
        "parfait",
        "super",
        "go",
        "next",
    ):
        logger.debug(f"Skipping trivial message for memory: '{stripped}'")
        return

    try:
        messages = [{"role": "user", "content": user_message}]
        if agent_response:
            # Truncate long responses — mem0 only needs key facts
            truncated = (
                agent_response[:500] if len(agent_response) > 500 else agent_response
            )
            messages.append({"role": "assistant", "content": truncated})
        memory.add(messages, user_id=USER_ID)
    except Exception as e:
        logger.warning(f"Could not save memory: {e}")


async def stream_agent_interaction(
    user_input: str,
    message_history: List,
    deps,
) -> tuple[str, List]:
    """Stream agent interaction with real-time tool call display.

    Args:
        user_input: The user's input text
        message_history: List of ModelRequest/ModelResponse objects for conversation context
        deps: AgentDeps instance

    Returns:
        Tuple of (streamed_text, new_messages_from_this_run)
    """
    try:
        return await _stream_agent(user_input, message_history, deps)
    except Exception as e:
        console.print(f"[red]Erreur: {e}[/red]")
        import traceback

        traceback.print_exc()
        return ("", [])


async def _stream_agent(
    user_input: str,
    message_history: List,
    deps,
) -> tuple[str, List]:
    """Stream the agent execution and return response."""
    response_text = ""

    async with agent.iter(
        user_input,
        message_history=message_history,
        deps=deps,
    ) as run:
        async for node in run:
            # Handle user prompt node
            if Agent.is_user_prompt_node(node):
                pass

            # Handle model request node - stream text
            elif Agent.is_model_request_node(node):
                console.print("[bold blue]Assistant:[/bold blue] ", end="")

                async with node.stream(run.ctx) as request_stream:
                    async for event in request_stream:
                        if (
                            isinstance(event, PartStartEvent)
                            and event.part.part_kind == "text"
                        ):
                            initial_text = event.part.content
                            if initial_text:
                                console.print(initial_text, end="")
                                response_text += initial_text

                        elif isinstance(event, PartDeltaEvent) and isinstance(
                            event.delta, TextPartDelta
                        ):
                            delta_text = event.delta.content_delta
                            if delta_text:
                                console.print(delta_text, end="")
                                response_text += delta_text

                console.print()

            # Handle tool calls - show which tools are being called
            elif Agent.is_call_tools_node(node):
                async with node.stream(run.ctx) as tool_stream:
                    async for event in tool_stream:
                        event_type = type(event).__name__

                        if event_type == "FunctionToolCallEvent":
                            tool_name = "Unknown"
                            args = None

                            if hasattr(event, "part"):
                                part = event.part
                                if hasattr(part, "tool_name"):
                                    tool_name = part.tool_name
                                elif hasattr(part, "function_name"):
                                    tool_name = part.function_name

                                if hasattr(part, "args"):
                                    args = part.args

                            console.print(
                                f"  [cyan]Outil:[/cyan] [bold]{tool_name}[/bold]"
                            )

                            # Show relevant args for nutrition tools
                            if args and isinstance(args, dict):
                                display_args = {}
                                for key in [
                                    "age",
                                    "gender",
                                    "weight_kg",
                                    "height_cm",
                                    "activity_level",
                                    "start_date",
                                    "week_start",
                                    "meal_structure",
                                    "selected_days",
                                    "weight_start_kg",
                                    "weight_end_kg",
                                    "adherence_percent",
                                    "user_query",
                                    "query",
                                ]:
                                    if key in args:
                                        display_args[key] = args[key]

                                if display_args:
                                    args_str = ", ".join(
                                        f"{k}={v}" for k, v in display_args.items()
                                    )
                                    console.print(f"    [dim]{args_str}[/dim]")

                        elif event_type == "FunctionToolResultEvent":
                            console.print(f"  [green]Outil termine[/green]")

            # Handle end node
            elif Agent.is_end_node(node):
                pass

    new_messages = run.result.new_messages()
    final_output = (
        run.result.output if hasattr(run.result, "output") else str(run.result)
    )
    response = response_text.strip() or final_output

    return (response, new_messages)


def display_welcome():
    """Display welcome message with configuration info."""
    llm_model = os.getenv("LLM_CHOICE", "gpt-4o-mini")
    llm_base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")

    welcome = Panel(
        "[bold blue]AI Nutrition Assistant[/bold blue]\n\n"
        "[green]Ton coach nutrition personnalise, base sur la science[/green]\n"
        f"[dim]LLM: {llm_model} @ {llm_base_url}[/dim]\n\n"
        "[dim]Commandes: 'exit' quitter | 'clear' effacer | 'info' config | 'help' aide[/dim]",
        style="blue",
        padding=(1, 2),
    )
    console.print(welcome)
    console.print()


async def main():
    """Main conversation loop."""
    display_welcome()

    # Initialize memory
    memory = None
    try:
        memory = get_memory_client()
        console.print("[bold green]OK[/bold green] mem0 connecte")
    except Exception as e:
        console.print(f"[yellow]mem0 non disponible:[/yellow] {e}")

    console.print("[bold green]OK[/bold green] Agent initialise")
    console.print()

    # Message history for multi-turn conversations (Pydantic AI format)
    message_history: List = []

    try:
        while True:
            try:
                user_input = Prompt.ask("[bold green]Toi").strip()

                if not user_input:
                    continue

                # Special commands
                if user_input.lower() in ("exit", "quit", "q"):
                    console.print("\n[yellow]A bientot ![/yellow]")
                    break

                elif user_input.lower() == "clear":
                    message_history.clear()
                    console.clear()
                    display_welcome()
                    console.print("[dim]Historique efface[/dim]\n")
                    continue

                elif user_input.lower() == "info":
                    llm_model = os.getenv("LLM_CHOICE", "gpt-4o-mini")
                    llm_base_url = os.getenv(
                        "LLM_BASE_URL", "https://api.openai.com/v1"
                    )
                    mem_status = "Connecte" if memory else "Non disponible"
                    console.print(
                        Panel(
                            f"[cyan]LLM:[/cyan] {llm_model}\n"
                            f"[cyan]Base URL:[/cyan] {llm_base_url}\n"
                            f"[cyan]Memoire:[/cyan] {mem_status}\n"
                            f"[cyan]Historique:[/cyan] {len(message_history)} messages",
                            title="Configuration",
                            border_style="magenta",
                        )
                    )
                    continue

                elif user_input.lower() == "help":
                    console.print(
                        Panel(
                            "[bold]Exemples de questions:[/bold]\n\n"
                            '  "Calcule mes besoins: 35 ans, homme, 87kg, 178cm"\n'
                            '  "Combien de proteines pour prendre du muscle?"\n'
                            '  "Genere un plan de repas pour la semaine"\n'
                            '  "Liste de courses pour cette semaine"\n'
                            "  \"Qu'est-ce que je mange aujourd'hui?\"\n"
                            '  "Bilan de la semaine: 87kg -> 86.4kg, 85% adherence"',
                            title="Aide",
                            border_style="green",
                        )
                    )
                    continue

                # Load memories for context
                memories_str = ""
                if memory:
                    memories_str = load_memories(memory, user_input)

                # Create deps
                deps = create_agent_deps(memories=memories_str)

                # Stream the interaction
                console.print()
                response_text, new_messages = await stream_agent_interaction(
                    user_input, message_history, deps
                )

                # Add new messages to history for multi-turn
                message_history.extend(new_messages)

                # Save to memory (with agent response for context)
                if memory:
                    save_memory(memory, user_input, response_text)

                console.print()

            except KeyboardInterrupt:
                console.print("\n[yellow]Ctrl+C - tape 'exit' pour quitter[/yellow]")
                continue

            except Exception as e:
                console.print(f"[red]Erreur: {e}[/red]")
                logger.error(f"Chat error: {e}", exc_info=True)
                continue

    finally:
        console.print("\n[dim]Goodbye![/dim]")


if __name__ == "__main__":
    asyncio.run(main())
