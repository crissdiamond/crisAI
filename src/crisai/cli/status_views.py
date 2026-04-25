from __future__ import annotations

from typing import Iterable

from rich.table import Table

from crisai.cli.display import print_status_message
from crisai.config import load_settings
from crisai.orchestration.router import RoutingDecision
from crisai.registry import Registry

HistoryEntry = tuple[str, str]


def server_icon(server_id: str) -> str:
    """Return the icon for a server identifier."""
    sid = server_id.lower()
    if "workspace" in sid:
        return "📁"
    if "document" in sid:
        return "📄"
    if "diagram" in sid:
        return "📊"
    if "sharepoint" in sid:
        return "☁"
    return "⚙"


def agent_icon(agent_id: str) -> str:
    """Return the icon for an agent identifier."""
    aid = agent_id.lower()
    if "orchestrator" in aid:
        return "🧭"
    if "discovery" in aid:
        return "🔎"
    if "design_author" in aid:
        return "✍"
    if "design_challenger" in aid:
        return "⚔"
    if "design_refiner" in aid:
        return "🛠"
    if aid == "design":
        return "🏗"
    if "review" in aid:
        return "🛡"
    if "judge" in aid:
        return "⚖"
    if "operations" in aid:
        return "🖧"
    return "🧠"


# Backward-compatible aliases used by the existing tests and CLI modules.
_server_icon = server_icon
_agent_icon = agent_icon


def _agent_model_label(spec: object) -> str:
    """Return the best available label for an agent model assignment."""
    for attr in ("display_model", "model_ref", "model"):
        value = getattr(spec, attr, None)
        if value:
            return str(value)
    return "-"


def print_servers_table() -> None:
    """Render the MCP server table."""
    from rich.console import Console

    console = Console()
    settings = load_settings()
    registry = Registry(settings.registry_dir)
    servers = registry.load_servers()

    table = Table(title="⚙ MCP Servers", header_style="bold bright_white")
    table.add_column("Type", justify="center")
    table.add_column("Server", style="bold cyan")
    table.add_column("Status", justify="center")
    table.add_column("Transport", style="magenta")
    table.add_column("Tags", style="dim cyan")

    for spec in servers:
        status = "[green]enabled[/green]" if spec.enabled else "[red]disabled[/red]"
        tags = ", ".join(spec.tags) if spec.tags else "[dim]-[/dim]"
        table.add_row(server_icon(spec.id), spec.id, status, spec.transport, tags)

    console.print(f"[dim]Registry:[/dim] {settings.registry_dir}")
    console.print(table)


def print_agents_table() -> None:
    """Render the agent table."""
    from rich.console import Console

    console = Console()
    settings = load_settings()
    registry = Registry(settings.registry_dir)
    agents = registry.load_agents()

    table = Table(title="🧠 Agents", header_style="bold bright_white")
    table.add_column("Type", justify="center")
    table.add_column("Agent", style="bold bright_cyan")
    table.add_column("Model", style="yellow")
    table.add_column("Allowed servers", style="green")

    for spec in agents:
        servers = ", ".join(spec.allowed_servers) if spec.allowed_servers else "[dim]-[/dim]"
        table.add_row(agent_icon(spec.id), spec.id, _agent_model_label(spec), servers)

    console.print(table)


# Backward-compatible aliases.
_print_servers_table = print_servers_table
_print_agents_table = print_agents_table


def route_display(decision: RoutingDecision) -> str:
    """Format a routing decision for user display."""
    agent = decision.agent or "-"
    label = "pinned" if decision.intent == "explicit" else "auto"
    review_label = "review:on" if decision.needs_review else "review:off"
    retrieval_label = "retrieval:on" if decision.needs_retrieval else "retrieval:off"
    return f"router:{label} • {decision.mode} • {agent} • {review_label} • {retrieval_label} • {decision.reason}"


_route_display = route_display


def mode_status(current_mode: str, mode_pinned: bool) -> str:
    """Return the display value for the current routing mode."""
    if not mode_pinned:
        return "auto"
    return f"pinned:{current_mode}"


_mode_status = mode_status


def agent_status(current_agent: str, agent_pinned: bool) -> str:
    """Return the display value for the current agent selection."""
    if not agent_pinned:
        return "auto"
    return f"pinned:{current_agent}"


_agent_status = agent_status


def print_chat_state(
    *,
    current_session: str,
    current_mode: str,
    current_agent: str,
    current_review: bool,
    current_verbose: bool,
    mode_pinned: bool,
    agent_pinned: bool,
    history_count: int,
) -> None:
    """Render the current interactive chat state."""
    lines = [
        f"Session: {current_session}",
        f"Routing: {mode_status(current_mode, mode_pinned)}",
        f"Agent: {agent_status(current_agent, agent_pinned)}",
        f"Review preference: {'on' if current_review else 'off'}",
        f"Verbose: {'on' if current_verbose else 'off'}",
        f"Loaded history entries: {history_count}",
        "Commands: /mode auto|single|pipeline|peer • /agent auto|<agent_id> • /status • /help",
    ]
    print_status_message("\n".join(lines), title="💬 Chat state")


_print_chat_state = print_chat_state


def print_session_history(history: Iterable[HistoryEntry]) -> None:
    """Render the last session history entries."""
    history = list(history)
    if not history:
        print_status_message("No history in this session.", title="📜 Session history")
        return

    lines = []
    for idx, (role, content) in enumerate(history[-20:], start=1):
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{idx}. {label}: {content[:500]}")
    print_status_message("\n".join(lines), title="📜 Session history")


_print_session_history = print_session_history
