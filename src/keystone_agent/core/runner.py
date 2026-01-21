"""Main runner for board execution using OpenAI Agents SDK."""

import asyncio
import json
import time
from typing import Any, Callable

from agents import Runner, set_tracing_disabled
from openai.types.responses import ResponseTextDeltaEvent
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

# Disable SDK tracing to avoid 500 errors and reduce overhead
set_tracing_disabled(True)

from keystone_agent.agents.orchestrator import build_orchestrator_agent
from keystone_agent.agents.tools import format_history_for_context, get_project_history
from keystone_agent.config import settings
from keystone_agent.schemas import BoardFinalOutput, BoardRequest
from keystone_agent.storage.session import DynamoDBSession
from keystone_agent.utils.background import wait_for_background_tasks

console = Console()

# Board branding
BOARD_NAME = "Keystone Board"
BOARD_TAGLINE = "Your AI Advisory Board"

# Agent codename to display name mapping
AGENT_DISPLAY = {
    "Keystone": ("🎯", "Orchestrator"),
    "Lynx": ("🔍", "Product"),
    "Wildfire": ("🔥", "Growth"),
    "Bedrock": ("🪨", "Systems"),
    "Leverage": ("⚖️", "Capital"),
    "Sentinel": ("🛡️", "Risk"),
    "Prism": ("💎", "Creative"),
    "Razor": ("✂️", "Purist"),
}

# Cache for agent builds (reused across requests in chat mode)
_cached_orchestrator = None
_cached_specialists = None


def get_cached_agents():
    """Get or build cached orchestrator and specialist agents."""
    global _cached_orchestrator, _cached_specialists
    if _cached_orchestrator is None:
        _cached_orchestrator, _cached_specialists = build_orchestrator_agent()
    return _cached_orchestrator, _cached_specialists


class BoardProgress:
    """Tracks and displays board execution progress using Rich Progress."""

    def __init__(self):
        self.current_agent: str | None = None
        self.phase: str = "init"
        self.status_message: str = "Initializing..."
        self.specialists_called: set[str] = set()
        self.specialists_done: set[str] = set()
        self.start_time: float = time.time()
        self.streaming_text: str = ""  # Captured output text

    def elapsed(self) -> str:
        """Get elapsed time as formatted string."""
        secs = int(time.time() - self.start_time)
        if secs < 60:
            return f"{secs}s"
        return f"{secs // 60}m {secs % 60}s"

    def build_display(self) -> Panel:
        """Build the progress display panel."""
        lines = []

        # Phase with elapsed time
        phase_icons = {
            "init": "◔",
            "reasoning": "◑",
            "calling_specialists": "◕",
            "synthesizing": "●",
            "done": "✓",
        }
        phase_text = {
            "init": "Initializing",
            "reasoning": "Analyzing request",
            "calling_specialists": "Consulting board",
            "synthesizing": "Synthesizing verdict",
            "done": "Complete",
        }.get(self.phase, self.phase)

        icon = phase_icons.get(self.phase, "○")
        style = "green bold" if self.phase == "done" else "cyan"
        lines.append(Text.assemble(
            (f"{icon} ", style),
            (phase_text, "bold" if self.phase != "done" else "bold green"),
            (f"  {self.elapsed()}", "dim"),
        ))

        # Current agent activity
        if self.current_agent and self.phase != "done":
            emoji, name = AGENT_DISPLAY.get(self.current_agent, ("🤖", self.current_agent))
            lines.append(Text.assemble(
                ("  └─ ", "dim"),
                (f"{emoji} {name}", "cyan"),
                (f": {self.status_message}", "dim italic"),
            ))

        # Specialists board - show names with status
        if self.specialists_called:
            # Spinner frames for smooth animation
            spinners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            tick = int(time.time() * 8)  # ~8 fps animation

            board_parts = [("  ", "")]
            specialist_list = ["Lynx", "Wildfire", "Bedrock", "Leverage", "Sentinel", "Prism", "Razor"]
            for i, codename in enumerate(specialist_list):
                if codename in self.specialists_done:
                    board_parts.append((codename, "green"))
                    board_parts.append((" ✓", "green bold"))
                elif codename in self.specialists_called:
                    spinner = spinners[(tick + i * 2) % len(spinners)]
                    board_parts.append((codename, "yellow"))
                    board_parts.append((f" {spinner}", "yellow"))
                else:
                    board_parts.append((codename, "dim"))
                    board_parts.append((" ·", "dim"))

                if i < len(specialist_list) - 1:
                    board_parts.append(("  ", ""))  # spacing between

            lines.append(Text.assemble(*board_parts))

        # Streaming output preview (if any)
        if self.streaming_text:
            preview = self.streaming_text[-80:].replace("\n", " ")
            if len(self.streaming_text) > 80:
                preview = "..." + preview
            lines.append(Text.assemble(
                ("  Output: ", "dim"),
                (preview, "white"),
            ))

        return Panel(
            Group(*lines),
            title=f"[bold cyan]{BOARD_NAME}[/bold cyan]",
            subtitle=f"[dim]{BOARD_TAGLINE}[/dim]",
            border_style="cyan",
            padding=(0, 1),
        )


async def run_board_async(
    request: BoardRequest,
    on_progress: Callable[[BoardProgress], None] | None = None,
) -> tuple[BoardFinalOutput, str]:
    """
    Execute the board asynchronously using OpenAI Agents SDK with streaming.

    The orchestrator will:
    1. Call run_all_specialists tool to get parallel feedback from all 7 specialists
    2. Apply consensus rules
    3. Produce final BoardFinalOutput

    Args:
        request: The board request
        on_progress: Optional callback for progress updates

    Returns:
        Tuple of (BoardFinalOutput, session_id)
    """
    progress = BoardProgress()

    # Create SDK-managed session with DynamoDB backend
    session = DynamoDBSession(
        project_id=request.project_id or "default",
        metadata={
            "mode": request.mode.value,
            "request_text": request.request_text,
            "option_a": request.option_a,
            "option_b": request.option_b,
            "since_days": request.since_days,
        },
    )

    # Get project history for context
    history_context = ""
    if request.project_id:
        project_history = await get_project_history(
            request.project_id,
            settings.history_limit,
        )
        history_context = format_history_for_context(project_history)

    # Build orchestrator input
    orchestrator_input = _build_orchestrator_input(request, history_context)

    # Get cached orchestrator agent (avoids rebuild on each request)
    orchestrator, specialist_agents = get_cached_agents()

    # Set initial agent
    progress.current_agent = "Keystone"
    progress.phase = "reasoning"
    progress.status_message = "Understanding your request..."
    progress.streaming_text = ""  # Clear any previous
    if on_progress:
        on_progress(progress)

    # Run the orchestrator with streaming
    result = Runner.run_streamed(
        starting_agent=orchestrator,
        input=orchestrator_input,
        max_turns=10,
    )

    # Process streaming events
    async for event in result.stream_events():
        if event.type == "agent_updated_stream_event":
            progress.current_agent = event.new_agent.name
            # Update status based on agent
            if event.new_agent.name == "Keystone":
                if progress.specialists_done:
                    progress.phase = "synthesizing"
                    progress.status_message = "Applying consensus rules..."
                else:
                    progress.phase = "reasoning"
                    progress.status_message = "Analyzing request..."
            else:
                emoji, name = AGENT_DISPLAY.get(event.new_agent.name, ("", event.new_agent.name))
                progress.status_message = f"{name} evaluating..."
            if on_progress:
                on_progress(progress)

        elif event.type == "run_item_stream_event":
            item = event.item
            if item.type == "tool_call_item":
                tool_name = getattr(item, "name", None) or getattr(item.raw_item, "name", "")
                if tool_name == "run_all_specialists":
                    # Mark all specialists as called
                    progress.phase = "calling_specialists"
                    progress.specialists_called = {"Lynx", "Wildfire", "Bedrock", "Leverage", "Sentinel", "Prism", "Razor"}
                    progress.status_message = "Gathering specialist opinions..."
                    if on_progress:
                        on_progress(progress)
                elif tool_name.startswith("consult_"):
                    codename = tool_name.replace("consult_", "").title()
                    progress.specialists_called.add(codename)
                    emoji, name = AGENT_DISPLAY.get(codename, ("", codename))
                    progress.status_message = f"Consulting {name}..."
                    if on_progress:
                        on_progress(progress)

            elif item.type == "tool_call_output_item":
                # Tool finished - try to detect which specialist
                tool_name = getattr(item, "name", None) or ""
                if tool_name == "run_all_specialists":
                    progress.specialists_done = progress.specialists_called.copy()
                    progress.phase = "synthesizing"
                    progress.status_message = "All specialists responded, synthesizing..."
                    if on_progress:
                        on_progress(progress)
                elif tool_name.startswith("consult_"):
                    codename = tool_name.replace("consult_", "").title()
                    progress.specialists_done.add(codename)
                    done_count = len(progress.specialists_done)
                    total = len(progress.specialists_called)
                    progress.status_message = f"Received {done_count}/{total} specialist opinions..."
                    if on_progress:
                        on_progress(progress)

            elif item.type == "message_output_item":
                # Final message being generated
                progress.phase = "synthesizing"
                progress.status_message = "Generating final verdict..."
                if on_progress:
                    on_progress(progress)

        elif event.type == "raw_response_event":
            # Capture streaming text deltas
            if isinstance(event.data, ResponseTextDeltaEvent):
                delta = event.data.delta
                if delta:
                    progress.streaming_text += delta
            if on_progress:
                on_progress(progress)

    # Mark as done
    progress.phase = "done"
    progress.status_message = "Board complete!"
    if on_progress:
        on_progress(progress)

    # Extract final output from streaming result
    raw_output = result.final_output
    if raw_output:
        if isinstance(raw_output, BoardFinalOutput):
            final_output = raw_output
        elif hasattr(raw_output, "model_dump"):
            final_output = BoardFinalOutput.model_validate(raw_output.model_dump())
        else:
            final_output = BoardFinalOutput.model_validate(raw_output)
    else:
        final_output = _build_fallback_output(request)

    # Save final output to session
    await session.save_final_output(final_output.model_dump())

    return final_output, session.session_id


def run_board(request: BoardRequest, show_progress: bool = True) -> tuple[BoardFinalOutput, str]:
    """
    Execute the board synchronously with optional live progress display.

    Args:
        request: The board request
        show_progress: Whether to show live progress (default True)

    Returns:
        Tuple of (BoardFinalOutput, session_id)
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    live_display: Live | None = None
    progress_state: BoardProgress | None = None

    def update_display(progress: BoardProgress):
        nonlocal progress_state
        progress_state = progress
        if live_display:
            live_display.update(progress.build_display())

    try:
        if show_progress:
            # Create initial progress state for first display
            initial_progress = BoardProgress()
            initial_progress.phase = "init"
            initial_progress.status_message = "Connecting to board..."
            live_display = Live(
                initial_progress.build_display(),
                console=console,
                refresh_per_second=8,  # Faster refresh for smooth animation
            )
            live_display.start()

        output, session_id = loop.run_until_complete(
            run_board_async(request, on_progress=update_display if show_progress else None)
        )

        # Wait for background storage tasks to complete before returning
        loop.run_until_complete(wait_for_background_tasks(timeout=10.0))

        return output, session_id
    finally:
        if live_display:
            live_display.stop()
        loop.close()


def _build_orchestrator_input(request: BoardRequest, history_context: str) -> str:
    """Build the input string for the orchestrator."""
    parts = [
        f"MODE: {request.mode.value}",
        f"REQUEST: {request.get_formatted_request()}",
    ]

    if history_context:
        parts.append(f"\nPREVIOUS BOARD DECISIONS:\n{history_context}")

    if request.option_a:
        parts.append(f"\nOPTION A: {request.option_a}")
    if request.option_b:
        parts.append(f"OPTION B: {request.option_b}")

    if request.context:
        ctx = request.context
        context_parts = []
        if ctx.product_stage:
            context_parts.append(f"Product Stage: {ctx.product_stage}")
        if ctx.runway_months:
            context_parts.append(f"Runway: {ctx.runway_months} months")
        if ctx.team_size:
            context_parts.append(f"Team Size: {ctx.team_size}")
        if ctx.revenue_monthly:
            context_parts.append(f"MRR: ${ctx.revenue_monthly:,}")
        if ctx.users_count:
            context_parts.append(f"Users: {ctx.users_count:,}")
        if ctx.key_metrics:
            context_parts.append(f"Key Metrics: {json.dumps(ctx.key_metrics)}")
        if ctx.constraints:
            context_parts.append(f"Constraints: {', '.join(ctx.constraints)}")
        if ctx.additional_context:
            context_parts.append(f"Additional: {ctx.additional_context}")

        if context_parts:
            parts.append(f"\nCONTEXT:\n" + "\n".join(context_parts))

    parts.append(
        "\n\nINSTRUCTIONS: Use run_all_specialists to get comprehensive feedback from all "
        "board members, then synthesize their inputs and produce your final verdict."
    )

    return "\n".join(parts)


def _build_fallback_output(request: BoardRequest) -> BoardFinalOutput:
    """Build a fallback output if orchestrator fails."""
    from keystone_agent.schemas import DayTask, Experiment, Verdict

    return BoardFinalOutput(
        request_type=request.mode,
        final_verdict=Verdict.UNCLEAR,
        final_summary="Board was unable to reach consensus. Please try again or provide more context.",
        why_this_verdict=[
            "Specialists did not return valid outputs",
            "Unable to apply consensus rules",
            "Consider breaking down the request",
        ],
        key_tradeoffs=[
            "Need more information to evaluate trade-offs",
            "Consider specificity vs breadth",
            "Time investment vs validation depth",
        ],
        top_risks=[
            "Incomplete analysis due to system error",
            "Decision made without full board input",
            "Consider retrying with more specific request",
        ],
        next_3_actions=[
            "Retry the board review with more specific details",
            "Break down the request into smaller questions",
            "Add context about your current situation",
        ],
        one_week_plan=[
            DayTask(day="Day 1-2", task="Reformulate request with specific details"),
            DayTask(day="Day 3-4", task="Retry board review"),
            DayTask(day="Day 5-7", task="Act on board recommendations"),
        ],
        single_best_experiment=Experiment(
            name="Validate Core Assumption",
            hypothesis="The core problem is well understood",
            success_criteria="5 users confirm the problem exists",
            time_box="3 days",
        ),
        board_votes=[],
        confidence=0.0,
        assumptions=["System encountered an error"],
        missing_info=["Valid specialist responses"],
        failed_agents=["All specialists"],
    )
