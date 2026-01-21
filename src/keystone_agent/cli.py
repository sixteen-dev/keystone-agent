"""CLI for Keystone Agent - AI Board of Directors."""

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel

from keystone_agent.config import AGENT_CODENAMES, AGENT_ROLES
from keystone_agent.core.runner import run_board
from keystone_agent.schemas import BoardRequest, ProjectContext, ProjectStage, RequestMode
from keystone_agent.storage.session import DynamoDBSession
from keystone_agent.utils.formatters import format_board_output, format_history

app = typer.Typer(
    name="board",
    help="AI Board of Directors CLI - Your synthetic advisory board",
    no_args_is_help=True,
)
console = Console()


def get_stdin_or_empty() -> str:
    """Read from stdin if piped, else empty string."""
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return ""


def _validate_and_run(
    request: BoardRequest,
    json_output: bool = False,
) -> None:
    """Validate request and run the board."""
    # Run board with live progress display (unless JSON output)
    result, session_id = run_board(request, show_progress=not json_output)

    if json_output:
        console.print(JSON(result.model_dump_json(indent=2)))
        console.print(f"\n[dim]Session ID: {session_id}[/dim]")
    else:
        format_board_output(result, session_id)


@app.command()
def review(
    context: Optional[str] = typer.Argument(
        None,
        help="Context for the review (idea, problem, or question)",
    ),
    project: Optional[str] = typer.Option(
        None, "--project", "-p",
        help="Project ID for history tracking",
    ),
    stage: Optional[str] = typer.Option(
        None, "--stage", "-s",
        help="Project stage: idea, mvp, beta, launched",
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j",
        help="Output raw JSON instead of formatted output",
    ),
) -> None:
    """
    Validate an idea and find the smallest viable wedge.

    The board will evaluate your idea through 7 specialist lenses:
    - Lynx (Product): User pain, UX, adoption
    - Wildfire (Growth): Distribution, channels, spread
    - Bedrock (Architecture): Simplicity, stability, cost
    - Leverage (Capital): ROI of time, compounding
    - Sentinel (Risk): Blind spots, over-optimism
    - Prism (Creative): Positioning, narrative
    - Razor (Purist): Focus, ruthless cuts

    Example:
        board review "I'm building an AI news feed for retail investors"
        cat idea.txt | board review --project my-saas
    """
    stdin_context = get_stdin_or_empty()
    full_context = stdin_context or context

    if not full_context:
        console.print("[red]Error: Provide context as argument or via stdin[/red]")
        console.print("[dim]Usage: board review \"your idea or question\"[/dim]")
        raise typer.Exit(1)

    project_context = None
    if stage:
        try:
            project_context = ProjectContext(stage=ProjectStage(stage))
        except ValueError:
            console.print(f"[red]Invalid stage: {stage}. Use: idea, mvp, beta, launched[/red]")
            raise typer.Exit(1)

    request = BoardRequest(
        mode=RequestMode.REVIEW,
        request_text=full_context,
        project_id=project,
        context=project_context,
    )

    _validate_and_run(request, json_output)


@app.command()
def decide(
    option_a: str = typer.Option(
        ..., "--a",
        help="First option to evaluate",
    ),
    option_b: str = typer.Option(
        ..., "--b",
        help="Second option to evaluate",
    ),
    context: str = typer.Option(
        ..., "--context", "-c",
        help="Context for the decision",
    ),
    project: Optional[str] = typer.Option(
        None, "--project", "-p",
        help="Project ID for history tracking",
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j",
        help="Output raw JSON",
    ),
) -> None:
    """
    Compare two options and force a clear choice.

    The board will evaluate both options and pick a winner.
    No fence-sitting allowed.

    Example:
        board decide --a "Build mobile app" --b "Focus on web" --context "Limited time, weekend builder"
    """
    request = BoardRequest(
        mode=RequestMode.DECIDE,
        request_text=context,
        option_a=option_a,
        option_b=option_b,
        project_id=project,
    )

    _validate_and_run(request, json_output)


@app.command()
def audit(
    summary: str = typer.Argument(
        ...,
        help="Summary of recent progress and activities",
    ),
    since: int = typer.Option(
        14, "--since", "-s",
        help="Number of days to look back",
        min=1, max=90,
    ),
    project: Optional[str] = typer.Option(
        None, "--project", "-p",
        help="Project ID for history tracking",
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j",
        help="Output raw JSON",
    ),
) -> None:
    """
    Detect drift and stop low-leverage work.

    The board will audit your recent activities and identify:
    - Work that should stop
    - Drift from core goals
    - Misallocated effort

    Example:
        board audit "Spent last 2 weeks on redesign" --since 14 --project my-saas
    """
    request = BoardRequest(
        mode=RequestMode.AUDIT,
        request_text=summary,
        since_days=since,
        project_id=project,
    )

    _validate_and_run(request, json_output)


@app.command()
def creative(
    context: str = typer.Argument(
        ...,
        help="Context for creative reframing",
    ),
    project: Optional[str] = typer.Option(
        None, "--project", "-p",
        help="Project ID for history tracking",
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j",
        help="Output raw JSON",
    ),
) -> None:
    """
    Generate divergent positioning directions.

    The board will provide 3 distinct creative directions
    and recommend one to pursue.

    Example:
        board creative "How should I position my AI writing tool?"
    """
    request = BoardRequest(
        mode=RequestMode.CREATIVE,
        request_text=context,
        project_id=project,
    )

    _validate_and_run(request, json_output)


@app.command()
def rate(
    session_id: str = typer.Argument(
        ...,
        help="Session ID to rate (shown after each board decision)",
    ),
    rating: str = typer.Option(
        ..., "--rating", "-r",
        help="Rating: correct, partial, or wrong",
    ),
    notes: Optional[str] = typer.Option(
        None, "--notes", "-n",
        help="Optional notes about the outcome",
    ),
) -> None:
    """
    Rate a previous board decision for learning.

    Ratings help track decision quality over time.

    Example:
        board rate abc-123 --rating correct --notes "Followed advice, gained 50 users"
    """
    if rating not in ["correct", "partial", "wrong"]:
        console.print("[red]Rating must be: correct, partial, or wrong[/red]")
        raise typer.Exit(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Create session reference to existing session
        session = DynamoDBSession(session_id=session_id)

        # Verify session exists
        session_data = loop.run_until_complete(session.get_session_data())
        if not session_data:
            console.print(f"[red]Session not found: {session_id}[/red]")
            raise typer.Exit(1)

        # Save rating
        loop.run_until_complete(session.save_rating(rating, notes))

        console.print(f"[green]Rating saved for {session_id}[/green]")

        if notes:
            console.print(f"[dim]Notes: {notes}[/dim]")
    finally:
        loop.close()


@app.command()
def history(
    project: str = typer.Option(
        ..., "--project", "-p",
        help="Project ID to show history for",
    ),
    limit: int = typer.Option(
        10, "--limit", "-l",
        help="Number of results to show",
        min=1, max=50,
    ),
) -> None:
    """
    Show board decision history for a project.

    Example:
        board history --project my-saas --limit 5
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(
            DynamoDBSession.get_project_history(project, limit)
        )
        format_history(results)
    finally:
        loop.close()


@app.command()
def agents() -> None:
    """List all board member agents and their roles."""
    console.print(Panel(
        "[bold]The Board[/bold]\n"
        "Your synthetic advisory board consists of 7 specialists:",
        title="Keystone Agents",
    ))

    for role, codename in AGENT_CODENAMES.items():
        if role == "orchestrator":
            continue
        full_name = AGENT_ROLES.get(codename, role)
        console.print(f"  [cyan]{codename:10}[/cyan] - {full_name}")

    console.print("\n[dim]Each agent evaluates your request through their unique lens.[/dim]")


@app.command()
def chat(
    project: Optional[str] = typer.Option(
        None, "--project", "-p",
        help="Project ID for history tracking",
    ),
) -> None:
    """
    Start an interactive board session.

    Opens a chat-like interface where you can ask the board
    multiple questions without restarting.

    Commands:
        review <text>     - Validate an idea
        decide            - Compare two options (will prompt)
        audit <text>      - Audit recent work
        creative <text>   - Get creative directions
        history           - Show project history
        agents            - List board members
        help              - Show commands
        exit/quit         - Exit session

    Example:
        board chat --project my-saas
    """
    from rich.prompt import Prompt
    from rich.markdown import Markdown

    console.print(Panel(
        "[bold cyan]Keystone Board[/bold cyan] - Interactive Session\n\n"
        "Type your question or command. Use [bold]help[/bold] for available commands.\n"
        "Press [bold]Ctrl+C[/bold] or type [bold]exit[/bold] to quit.",
        title="🎯 Board Session",
        border_style="cyan",
    ))

    if project:
        console.print(f"[dim]Project: {project}[/dim]\n")

    current_project = project

    def show_help():
        help_text = """
**Available Commands:**

| Command | Description |
|---------|-------------|
| `review <text>` | Validate an idea or question |
| `decide` | Compare two options (interactive) |
| `audit <text>` | Audit recent work for drift |
| `creative <text>` | Get creative positioning directions |
| `history` | Show project decision history |
| `project <id>` | Set/change current project |
| `agents` | List board members |
| `clear` | Clear screen |
| `exit` / `quit` | Exit session |

**Tips:**
- Just type your question directly for a quick review
- Use quotes for multi-word inputs: `review "my idea here"`
"""
        console.print(Markdown(help_text))

    def parse_input(user_input: str) -> tuple[str, str]:
        """Parse command and argument from input."""
        parts = user_input.strip().split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        arg = parts[1] if len(parts) > 1 else ""
        return cmd, arg

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]board[/bold cyan]")

            if not user_input.strip():
                continue

            cmd, arg = parse_input(user_input)

            # Exit commands
            if cmd in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            # Help
            elif cmd == "help":
                show_help()

            # Clear screen
            elif cmd == "clear":
                console.clear()

            # Set project
            elif cmd == "project":
                if arg:
                    current_project = arg
                    console.print(f"[green]Project set to: {current_project}[/green]")
                else:
                    if current_project:
                        console.print(f"[dim]Current project: {current_project}[/dim]")
                    else:
                        console.print("[dim]No project set. Use: project <id>[/dim]")

            # List agents
            elif cmd == "agents":
                for role, codename in AGENT_CODENAMES.items():
                    if role == "orchestrator":
                        continue
                    full_name = AGENT_ROLES.get(codename, role)
                    console.print(f"  [cyan]{codename:10}[/cyan] - {full_name}")

            # History
            elif cmd == "history":
                if not current_project:
                    console.print("[yellow]Set a project first: project <id>[/yellow]")
                    continue
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    results = loop.run_until_complete(
                        DynamoDBSession.get_project_history(current_project, 10)
                    )
                    format_history(results)
                finally:
                    loop.close()

            # Review
            elif cmd == "review":
                if not arg:
                    console.print("[yellow]Usage: review <your question or idea>[/yellow]")
                    continue
                request = BoardRequest(
                    mode=RequestMode.REVIEW,
                    request_text=arg,
                    project_id=current_project,
                )
                _validate_and_run(request)

            # Decide (interactive)
            elif cmd == "decide":
                option_a = Prompt.ask("  [cyan]Option A[/cyan]")
                option_b = Prompt.ask("  [cyan]Option B[/cyan]")
                context = Prompt.ask("  [cyan]Context[/cyan]")
                request = BoardRequest(
                    mode=RequestMode.DECIDE,
                    request_text=context,
                    option_a=option_a,
                    option_b=option_b,
                    project_id=current_project,
                )
                _validate_and_run(request)

            # Audit
            elif cmd == "audit":
                if not arg:
                    console.print("[yellow]Usage: audit <summary of recent work>[/yellow]")
                    continue
                request = BoardRequest(
                    mode=RequestMode.AUDIT,
                    request_text=arg,
                    project_id=current_project,
                )
                _validate_and_run(request)

            # Creative
            elif cmd == "creative":
                if not arg:
                    console.print("[yellow]Usage: creative <positioning question>[/yellow]")
                    continue
                request = BoardRequest(
                    mode=RequestMode.CREATIVE,
                    request_text=arg,
                    project_id=current_project,
                )
                _validate_and_run(request)

            # Default: treat as review
            else:
                # Treat the entire input as a review request
                request = BoardRequest(
                    mode=RequestMode.REVIEW,
                    request_text=user_input,
                    project_id=current_project,
                )
                _validate_and_run(request)

        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


# Make chat the default when no command is given
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """AI Board of Directors CLI - Your synthetic advisory board."""
    if ctx.invoked_subcommand is None:
        # No subcommand provided, show help
        # User can run `board chat` for interactive mode
        pass


if __name__ == "__main__":
    app()
