from __future__ import annotations

from collections.abc import Iterable

from rich import console as rich_console
from rich import table as rich_table

from crisai.cli import display as display_module
from crisai import config as config_module
from crisai.orchestration import router as router_module
from crisai import registry as registry_module

Console = rich_console.Console
Table = rich_table.Table
print_status_message = display_module.print_status_message
load_settings = config_module.load_settings
RoutingDecision = router_module.RoutingDecision
Registry = registry_module.Registry

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
        return "🛰️"
    if "retrieval_planner" in aid:
        return "🔍"
    if "context_retrieval" in aid:
        return "📖"
    if "context_synthesizer" in aid:
        return "🧬"
    if "summary" in aid:
        return "📑"
    if "design_author" in aid:
        return "✍️"
    if "design_challenger" in aid:
        return "🤺"
    if "design_refiner" in aid:
        return "💎"
    if "design" in aid:
        return "🎨"
    if "review" in aid:
        return "🔎"
    if "judge" in aid:
        return "🏛️"
    if "operations" in aid:
        return "🛠️"
    if "document_formatter" in aid:
        return "🎭"
    if "publisher" in aid:
        return "🚢"
    return "🧠"


def _agent_model_label(spec: object) -> str:
    """Return the best available label for an agent model assignment."""
    for attr in ("display_model", "model_ref", "model"):
        value = getattr(spec, attr, None)
        if value:
            return str(value)
    return "-"


def print_servers_table() -> None:
    """Render the MCP server table."""
    console = rich_console.Console()
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
    console = rich_console.Console()
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


def route_display(decision: RoutingDecision) -> str:
    """Format a routing decision for user display."""
    agent = decision.agent or "-"
    label = "pinned" if decision.intent == "explicit" else "auto"
    review_label = "review:on" if decision.needs_review else "review:off"
    retrieval_label = "retrieval:on" if decision.needs_retrieval else "retrieval:off"
    return f"router:{label} • {decision.mode} • {agent} • {review_label} • {retrieval_label} • {decision.reason}"


def mode_status(current_mode: str, mode_pinned: bool) -> str:
    """Return the display value for the current routing mode."""
    if not mode_pinned:
        return "auto"
    return f"pinned:{current_mode}"


def agent_status(current_agent: str, agent_pinned: bool) -> str:
    """Return the display value for the current agent selection."""
    if not agent_pinned:
        return "auto"
    return f"pinned:{current_agent}"


def print_chat_state(
    *,
    current_session: str,
    history_count: int,
) -> None:
    """Render lean interactive session diagnostics."""
    log_dir = load_settings().log_dir.resolve()
    lines = [
        f"Session: {current_session}",
        f"Loaded history entries: {history_count}",
        f"Logs: {log_dir} (crisai.log, agent_trace.jsonl, *_mcp.log when servers run)",
        "Commands: /settings • /context show • /history • /help",
    ]
    print_status_message("\n".join(lines), title="💬 Session status")


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
