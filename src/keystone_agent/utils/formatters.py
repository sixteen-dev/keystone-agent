"""Output formatters for CLI display."""

import sys
import time
from typing import Iterator

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from keystone_agent.schemas import BoardFinalOutput, Verdict

console = Console()

VERDICT_COLORS = {
    Verdict.GO: "bold green",
    Verdict.NO_GO: "bold red",
    Verdict.PIVOT: "bold yellow",
    Verdict.UNCLEAR: "dim",
}

VERDICT_EMOJI = {
    Verdict.GO: "[green]✓ GO[/green]",
    Verdict.NO_GO: "[red]✗ NO GO[/red]",
    Verdict.PIVOT: "[yellow]↻ PIVOT[/yellow]",
    Verdict.UNCLEAR: "[dim]? UNCLEAR[/dim]",
}


def _stream_text(text: str, delay: float = 0.01) -> None:
    """Print text with a typing effect."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


def _section_delay(delay: float = 0.05) -> None:
    """Small delay between sections for visual flow."""
    time.sleep(delay)


def format_board_output(result: BoardFinalOutput, session_id: str, stream: bool = True) -> None:
    """Pretty print the board result to the console with optional streaming effect."""
    color = VERDICT_COLORS.get(result.final_verdict, "white")
    delay = 0.008 if stream else 0

    # Header with verdict
    console.print()
    verdict_display = VERDICT_EMOJI.get(result.final_verdict, result.final_verdict.value.upper())
    console.print(
        Panel(
            f"[{color}]VERDICT: {verdict_display}[/{color}]\n"
            f"[dim]Confidence: {result.confidence:.0%}[/dim]",
            title="[bold]Board Decision[/bold]",
            border_style=color.replace("bold ", ""),
        )
    )
    if stream:
        _section_delay()

    # Summary - stream this one for effect
    console.print(f"\n[bold]Summary[/bold]")
    if stream and len(result.final_summary) < 500:
        console.print("  ", end="")
        _stream_text(result.final_summary, delay)
    else:
        console.print(f"  {result.final_summary}")

    # Why this verdict
    if stream:
        _section_delay()
    console.print(f"\n[bold]Why This Verdict[/bold]")
    for reason in result.why_this_verdict:
        console.print(f"  [green]▸[/green] {reason}")
        if stream:
            _section_delay(0.02)

    # Top risks
    if stream:
        _section_delay()
    console.print(f"\n[bold]Top Risks[/bold]")
    for risk in result.top_risks:
        console.print(f"  [red]▸[/red] {risk}")
        if stream:
            _section_delay(0.02)

    # Key tradeoffs
    if stream:
        _section_delay()
    console.print(f"\n[bold]Key Tradeoffs[/bold]")
    for tradeoff in result.key_tradeoffs:
        console.print(f"  [yellow]▸[/yellow] {tradeoff}")
        if stream:
            _section_delay(0.02)

    # Next actions
    if stream:
        _section_delay()
    console.print(f"\n[bold]Next 3 Actions[/bold]")
    for i, action in enumerate(result.next_3_actions, 1):
        console.print(f"  [cyan]{i}.[/cyan] {action}")
        if stream:
            _section_delay(0.03)

    # One week plan
    if stream:
        _section_delay()
    console.print(f"\n[bold]One Week Plan[/bold]")
    for task in result.one_week_plan:
        console.print(f"  [cyan]{task.day}[/cyan]: {task.task}")
        if stream:
            _section_delay(0.02)

    # Experiment
    if stream:
        _section_delay()
    console.print(f"\n[bold]Experiment[/bold]")
    exp = result.single_best_experiment
    console.print(f"  [dim]Hypothesis:[/dim] {exp.hypothesis}")
    if stream:
        _section_delay(0.02)
    console.print(f"  [dim]Test:[/dim] {exp.test}")
    if stream:
        _section_delay(0.02)
    console.print(f"  [dim]Success:[/dim] {exp.success_metric}")
    if stream:
        _section_delay(0.02)
    console.print(f"  [dim]Timebox:[/dim] {exp.timebox}")

    # Board votes table
    if stream:
        _section_delay()
    console.print(f"\n[bold]Board Votes[/bold]")
    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("Agent", style="cyan")
    table.add_column("Verdict")
    table.add_column("Conf", justify="right")

    for vote in result.board_votes:
        v = vote.verdict.lower() if isinstance(vote.verdict, str) else vote.verdict
        verdict_color = "green" if v == "go" else "red" if v == "no_go" else "yellow"
        table.add_row(
            vote.agent_name,
            f"[{verdict_color}]{str(v).upper()}[/{verdict_color}]",
            f"{vote.confidence:.0%}",
        )

    console.print(table)

    # Failed agents (if any)
    if result.failed_agents:
        console.print(f"\n[yellow]⚠ Some agents failed:[/yellow]")
        for agent in result.failed_agents:
            console.print(f"  [dim]- {agent}[/dim]")

    # Missing info
    if result.missing_info:
        console.print(f"\n[bold]Missing Information[/bold]")
        for info in result.missing_info:
            console.print(f"  [dim]?[/dim] {info}")

    # Footer with session ID
    console.print()
    console.print(f"[dim]Session: {session_id}[/dim]")
    console.print(f"[dim]Rate: board rate {session_id} --rating correct|partial|wrong[/dim]")


def format_history(history: list[dict]) -> None:
    """Format project history for display."""
    if not history:
        console.print("[dim]No history found for this project.[/dim]")
        return

    table = Table(title="Project History", show_header=True, header_style="bold")
    table.add_column("Date", style="dim")
    table.add_column("Mode")
    table.add_column("Verdict")
    table.add_column("Confidence")
    table.add_column("Request Summary", max_width=40)

    for item in history:
        verdict = item.get("verdict", "N/A")
        verdict_color = (
            "green" if verdict == "go"
            else "red" if verdict == "no_go"
            else "yellow" if verdict == "pivot"
            else "dim"
        )

        confidence = item.get("confidence")
        confidence_str = f"{confidence:.0%}" if confidence else "N/A"

        # Parse and format date
        created_at = item.get("created_at", "")
        date_str = created_at[:10] if created_at else "N/A"

        table.add_row(
            date_str,
            item.get("mode", "N/A"),
            f"[{verdict_color}]{verdict.upper() if verdict else 'N/A'}[/{verdict_color}]",
            confidence_str,
            item.get("request_summary", "")[:40] + "...",
        )

    console.print(table)
