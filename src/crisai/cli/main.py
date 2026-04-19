from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

import typer
from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from crisai.cli.commands import parse_chat_command
from crisai.cli.display import print_final_recommendation
from crisai.cli.text_loader import load_cli_text, render_cli_text
from crisai.config import load_settings
from crisai.orchestration.router import RoutingDecision, decide_route
from crisai.registry import Registry
from .pipelines import run_peer_pipeline, run_pipeline, run_single


app = typer.Typer(help="crisAI CLI")
console = Console()


def _load_registry():
    settings = load_settings()
    registry = Registry(settings.registry_dir)
    server_specs = {s.id: s for s in registry.load_servers() if s.enabled}
    agent_specs = {a.id: a for a in registry.load_agents()}
    return settings, registry, server_specs, agent_specs


def _render_history(history: list[tuple[str, str]]) -> str:
    if not history:
        return ""

    lines: list[str] = []
    for role, content in history:
        if role == "user":
            lines.append(f"User: {content}")
        else:
            lines.append(f"Assistant: {content}")

    return "\n\n".join(lines)


def _cli_history_file() -> Path:
    settings = load_settings()
    path = settings.workspace_dir / ".cli_history"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _build_chat_input(user_input: str, history: list[tuple[str, str]]) -> str:
    if not history:
        return user_input

    transcript = _render_history(history[-12:])
    return render_cli_text(
        "chat/history_wrapper.md",
        transcript=transcript,
        user_input=user_input,
    )


def _session_dir() -> Path:
    settings = load_settings()
    path = settings.workspace_dir / "chat_sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _session_file(session_name: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in session_name.strip())
    if not safe:
        safe = "default"
    return _session_dir() / f"{safe}.json"


def _load_history(session_name: str) -> list[tuple[str, str]]:
    path = _session_file(session_name)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        history: list[tuple[str, str]] = []
        for item in data:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                history.append((role, content))
        return history
    except Exception:
        return []


def _save_history(session_name: str, history: list[tuple[str, str]]) -> None:
    path = _session_file(session_name)
    payload = [
        {
            "role": role,
            "content": content,
            "saved_at": datetime.utcnow().isoformat() + "Z",
        }
        for role, content in history
    ]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _server_icon(server_id: str) -> str:
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


def _agent_icon(agent_id: str) -> str:
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


def _print_servers_table() -> None:
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
        table.add_row(_server_icon(spec.id), spec.id, status, spec.transport, tags)

    console.print(f"[dim]Registry:[/dim] {settings.registry_dir}")
    console.print(table)


def _print_agents_table() -> None:
    _, _, _, agent_specs = _load_registry()

    table = Table(title="🧠 Agents", header_style="bold bright_white")
    table.add_column("Type", justify="center")
    table.add_column("Agent", style="bold bright_cyan")
    table.add_column("Model", style="yellow")
    table.add_column("Allowed servers", style="green")

    for spec in agent_specs.values():
        servers = ", ".join(spec.allowed_servers) if spec.allowed_servers else "[dim]-[/dim]"
        table.add_row(_agent_icon(spec.id), spec.id, spec.model, servers)

    console.print(table)


def _route_display(decision: RoutingDecision) -> str:
    agent = decision.agent or "-"
    label = "pinned" if decision.intent == "explicit" else "auto"
    return f"[dim][router:{label}][/dim] {decision.mode} • {agent} • {decision.reason}"


def _resolve_route(
    user_input: str,
    review_enabled: bool,
    mode_override: str | None = None,
    agent_override: str | None = None,
) -> RoutingDecision:
    return decide_route(
        user_input=user_input,
        review_enabled=review_enabled,
        current_mode=mode_override,
        selected_agent=agent_override,
    )


def _effective_pipeline_review(decision: RoutingDecision) -> bool:
    return decision.mode == "pipeline" and decision.needs_review


@app.command("list-servers")
def list_servers() -> None:
    _print_servers_table()


@app.command("list-agents")
def list_agents() -> None:
    _print_agents_table()


async def _run_with_routing(
    message: str,
    verbose: bool,
    review: bool,
    decision: RoutingDecision,
) -> str:
    settings, _, server_specs, agent_specs = _load_registry()
    effective_review = _effective_pipeline_review(decision)

    if decision.mode == "peer":
        return await run_peer_pipeline(
            message,
            verbose,
            False,
            settings=settings,
            server_specs=server_specs,
            agent_specs=agent_specs,
            needs_retrieval=decision.needs_retrieval,
        )
    if decision.mode == "pipeline":
        return await run_pipeline(
            message,
            verbose,
            effective_review,
            settings=settings,
            server_specs=server_specs,
            agent_specs=agent_specs,
        )
    return await run_single(
        message,
        decision.agent or "orchestrator",
        settings=settings,
        server_specs=server_specs,
        agent_specs=agent_specs,
    )


def _print_session_history(history: list[tuple[str, str]]) -> None:
    if not history:
        console.print("[yellow]No history in this session.[/yellow]")
        return

    console.print(Markdown("### Session history"))
    for idx, (role, content) in enumerate(history[-20:], start=1):
        label = "User" if role == "user" else "Assistant"
        console.print(f"[bold]{idx}. {label}[/bold]: {content[:500]}")


def _handle_chat_command(
    user_input: str,
    *,
    history: list[tuple[str, str]],
    current_session: str,
    current_mode: str,
    current_agent: str,
    current_review: bool,
    current_verbose: bool,
    mode_pinned: bool,
    agent_pinned: bool,
) -> tuple[bool, str, list[tuple[str, str]], str, str, bool, bool, bool, bool]:
    command = parse_chat_command(user_input)

    if not command.handled:
        return False, current_session, history, current_mode, current_agent, current_review, current_verbose, mode_pinned, agent_pinned

    action = command.action

    if action == "exit":
        raise EOFError

    if action == "help":
        console.print(Markdown(load_cli_text("help.md")))
    elif action == "clear":
        history.clear()
        _save_history(current_session, history)
        console.print(f"[yellow]Conversation history cleared for session '{current_session}'.[/yellow]")
    elif action == "list_servers":
        _print_servers_table()
    elif action == "list_agents":
        _print_agents_table()
    elif action == "history":
        _print_session_history(history)
    elif action == "switch_session":
        current_session = str(command.value)
        history = _load_history(current_session)
        console.print(f"[green]Switched to session '{current_session}'.[/green]")
        console.print(f"[green]Loaded history entries: {len(history)}[/green]")
    elif action == "set_mode":
        current_mode = str(command.value)
        mode_pinned = True
        console.print(f"[green]Mode set to {current_mode}[/green]")
    elif action == "set_review":
        current_review = bool(command.value)
        console.print(f"[green]Review {'enabled' if current_review else 'disabled'}.[/green]")
    elif action == "set_verbose":
        current_verbose = bool(command.value)
        console.print(f"[green]Verbose {'enabled' if current_verbose else 'disabled'}.[/green]")
    elif action == "set_agent":
        current_agent = str(command.value)
        agent_pinned = True
        console.print(f"[green]Single-agent target set to {current_agent}[/green]")
    elif action in {"invalid", "noop"} and command.message:
        console.print(f"[yellow]{command.message}[/yellow]")

    return True, current_session, history, current_mode, current_agent, current_review, current_verbose, mode_pinned, agent_pinned


@app.command()
def ask(
    message: str = typer.Option(..., "--message", "-m"),
    agent_id: str = typer.Option("orchestrator", "--agent"),
    pipeline: bool = typer.Option(False, "--pipeline", help="Run the visible discovery/design/review/orchestrator pipeline."),
    peer: bool = typer.Option(False, "--peer", help="Run the peer workflow: discovery -> author -> challenger -> refiner -> judge -> orchestrator."),
    review: bool = typer.Option(False, "--review/--no-review", help="Review is off by default. Use --review to enable it."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    explicit_mode = "peer" if peer else "pipeline" if pipeline else None
    explicit_agent = agent_id if agent_id != "orchestrator" else None
    decision = _resolve_route(message, review_enabled=review, mode_override=explicit_mode, agent_override=explicit_agent)
    console.print(_route_display(decision))

    async def _run() -> None:
        text = await _run_with_routing(message, verbose, review, decision)
        if decision.mode == "peer":
            print_final_recommendation(text)
        else:
            console.print(Markdown(text))

    asyncio.run(_run())


@app.command()
def chat(
    agent_id: str = typer.Option("orchestrator", "--agent"),
    session: str = typer.Option("default", "--session", "-s", help="Persistent chat session name."),
    pipeline: bool = typer.Option(False, "--pipeline", help="Run the visible discovery/design/review/orchestrator pipeline."),
    peer: bool = typer.Option(False, "--peer", help="Run the peer workflow: discovery -> author -> challenger -> refiner -> judge -> orchestrator."),
    review: bool = typer.Option(False, "--review/--no-review", help="Review is off by default. Use --review to enable it."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    current_session = session
    history: list[tuple[str, str]] = _load_history(current_session)
    current_mode = "peer" if peer else "pipeline" if pipeline else "single"
    current_agent = agent_id
    current_review = review
    current_verbose = verbose
    mode_pinned = True if (peer or pipeline) else False
    agent_pinned = True if (agent_id != "orchestrator") else False

    console.print("[bold green]crisAI interactive chat[/bold green]")
    console.print(f"Session: [bold]{current_session}[/bold]")
    console.print(f"Mode: [bold]{current_mode}[/bold] | Agent: [bold]{current_agent}[/bold]")
    console.print(f"Review: [bold]{'on' if current_review else 'off'}[/bold] | Verbose: [bold]{'on' if current_verbose else 'off'}[/bold]")
    console.print(f"Loaded history entries: [bold]{len(history)}[/bold]")
    console.print("Type /help for commands.\n")

    while True:
        try:
            user_input = prompt(
                "> ",
                history=FileHistory(str(_cli_history_file())),
                auto_suggest=AutoSuggestFromHistory(),
            ).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nExiting.")
            break

        if not user_input:
            continue

        try:
            handled, current_session, history, current_mode, current_agent, current_review, current_verbose, mode_pinned, agent_pinned = _handle_chat_command(
                user_input,
                history=history,
                current_session=current_session,
                current_mode=current_mode,
                current_agent=current_agent,
                current_review=current_review,
                current_verbose=current_verbose,
                mode_pinned=mode_pinned,
                agent_pinned=agent_pinned,
            )
        except EOFError:
            break

        if handled:
            continue

        chat_input = _build_chat_input(user_input, history)

        explicit_mode_override = current_mode if mode_pinned else None
        explicit_agent_override = current_agent if agent_pinned else None

        decision = _resolve_route(
            user_input,
            review_enabled=current_review,
            mode_override=explicit_mode_override,
            agent_override=explicit_agent_override,
        )

        console.print(_route_display(decision))

        async def _run() -> str:
            return await _run_with_routing(chat_input, current_verbose, current_review, decision)

        try:
            text = asyncio.run(_run())
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            continue

        console.print()
        if decision.mode == "peer":
            print_final_recommendation(text)
        else:
            console.print(Markdown(text))
        console.print()

        history.append(("user", user_input))
        history.append(("assistant", text))
        _save_history(current_session, history)


if __name__ == "__main__":
    app()
