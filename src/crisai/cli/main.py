from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

import typer
from agents import Runner
from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from crisai.agents.factory import AgentFactory
from crisai.config import load_settings
from crisai.orchestration.router import RoutingDecision, decide_route
from crisai.registry import Registry
from crisai.runtime import MultiServerContext, RuntimeManager
from crisai.tracing import append_trace

app = typer.Typer(help="crisAI CLI")
console = Console()


def _load_registry():
    settings = load_settings()
    registry = Registry(settings.registry_dir)
    server_specs = {s.id: s for s in registry.load_servers() if s.enabled}
    agent_specs = {a.id: a for a in registry.load_agents()}
    return settings, registry, server_specs, agent_specs


def _build_agent_servers(runtime: RuntimeManager, agent_spec, server_specs):
    servers = []
    for server_id in agent_spec.allowed_servers:
        spec = server_specs.get(server_id)
        if spec:
            servers.append(runtime.build_server(spec))
    return servers


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
    return f"""Conversation so far:
{transcript}

Latest user message:
{user_input}

Please answer consistently with the conversation so far."""


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


@app.command("list-servers")
def list_servers() -> None:
    _print_servers_table()


@app.command("list-agents")
def list_agents() -> None:
    _print_agents_table()


async def _run_single(message: str, agent_id: str) -> str:
    settings, _, server_specs, agent_specs = _load_registry()
    if not settings.openai_api_key:
        raise typer.BadParameter("OPENAI_API_KEY is not set.")

    if agent_id not in agent_specs:
        raise typer.BadParameter(f"Unknown agent_id: {agent_id}")

    root_dir = Path.cwd()
    runtime = RuntimeManager(root_dir)
    factory = AgentFactory(root_dir)
    agent_spec = agent_specs[agent_id]
    servers = _build_agent_servers(runtime, agent_spec, server_specs)

    async with MultiServerContext(servers) as active_servers:
        agent = factory.build_agent(agent_spec, active_servers)
        result = await Runner.run(agent, message)
        return str(result.final_output)


async def _run_pipeline(message: str, verbose: bool, review: bool = False) -> str:
    settings, _, server_specs, agent_specs = _load_registry()
    if not settings.openai_api_key:
        raise typer.BadParameter("OPENAI_API_KEY is not set.")

    root_dir = Path.cwd()
    runtime = RuntimeManager(root_dir)
    factory = AgentFactory(root_dir)
    trace_file = settings.log_dir / "agent_trace.log"

    discovery_spec = agent_specs["discovery"]
    design_spec = agent_specs["design"]
    review_spec = agent_specs["review"]
    orchestrator_spec = agent_specs["orchestrator"]

    all_server_ids = sorted(
        {
            *discovery_spec.allowed_servers,
            *design_spec.allowed_servers,
            *review_spec.allowed_servers,
            *orchestrator_spec.allowed_servers,
        }
    )
    servers = [runtime.build_server(server_specs[sid]) for sid in all_server_ids if sid in server_specs]

    async with MultiServerContext(servers) as active_servers:
        append_trace(trace_file, "USER INPUT", message)

        if verbose:
            console.print(Panel.fit("Running Discovery Agent", style="cyan"))
        discovery_agent = factory.build_agent(discovery_spec, active_servers)
        discovery_prompt = f"""
User request:
{message}

Task:
Inspect the available sources and retrieve the most relevant material for this request.

Rules:
- For workspace sources, all paths must be relative to the workspace root.
- Never guess file paths, site names, drive IDs, item IDs, or document IDs.
- Always list or search before reading.
- Only read a path or item returned by a listing/search tool in this run.
- For supported document formats such as .docx, .pdf, .pptx, .xlsx, use the document-reading tools.
- For plain text files, use workspace text reads where appropriate.
- Use SharePoint tools when the relevant information may be in SharePoint.
- When using SharePoint, first check auth status before searching.
- If no valid silent token is available, report that login is required.
- Do not trigger interactive SharePoint login unless explicitly requested by the user.
- Use get_document_metadata or get_sharepoint_document_metadata only if needed, and only with a valid item returned in this run.
- If a tool fails, report the exact tool name and exact error.
- Do not claim you inspected or read a source unless a tool call succeeded.

Return:
1. relevant sources with exact paths or identifiers
2. extracted facts
3. assumptions
4. constraints
5. decisions already present
6. missing information
7. exact tool errors, if any
"""
        discovery_result = await Runner.run(discovery_agent, discovery_prompt)
        discovery_text = str(discovery_result.final_output)
        append_trace(trace_file, "DISCOVERY OUTPUT", discovery_text)
        if verbose:
            console.print(Markdown(f"## Discovery Agent\n\n{discovery_text}"))

        if verbose:
            console.print(Panel.fit("Running Design Agent", style="green"))
        design_agent = factory.build_agent(design_spec, active_servers)
        design_prompt = f"""
User request:
{message}

Discovery findings:
{discovery_text}

Task:
Produce the best possible architecture, design, or documentation response for the user's request.

Rules:
- Treat the discovery findings as the authoritative retrieval result for this run.
- Do not invent or reopen file paths unless discovery explicitly identified them.
- If discovery found no reliable sources, say so and work only from the verified findings provided.
- Where a diagram would help, generate Mermaid.
"""
        design_result = await Runner.run(design_agent, design_prompt)
        design_text = str(design_result.final_output)
        append_trace(trace_file, "DESIGN OUTPUT", design_text)
        if verbose:
            console.print(Markdown(f"## Design Agent\n\n{design_text}"))

        if review:
            if verbose:
                console.print(Panel.fit("Running Review Agent", style="yellow"))
            review_agent = factory.build_agent(review_spec, active_servers)
            review_prompt = f"""
User request:
{message}

Discovery findings:
{discovery_text}

Draft design response:
{design_text}

Task:
Critically review the draft.

Rules:
- Treat discovery findings as the factual basis for this review.
- Do not invent additional files, SharePoint items, or file contents.
- If discovery reported tool failures or missing retrieval, take that into account.

Highlight:
- governance gaps
- ownership gaps
- NFR or assurance gaps
- delivery risks
- suggested improvements
"""
            review_result = await Runner.run(review_agent, review_prompt)
            review_text = str(review_result.final_output)
            append_trace(trace_file, "REVIEW OUTPUT", review_text)
            if verbose:
                console.print(Markdown(f"## Review Agent\n\n{review_text}"))
        else:
            review_text = "Review stage skipped because review is disabled."
            append_trace(trace_file, "REVIEW OUTPUT", review_text)
            if verbose:
                console.print(Panel.fit("Skipping Review Agent", style="yellow"))

        if verbose:
            console.print(Panel.fit("Running Orchestrator", style="white"))
        orchestrator_agent = factory.build_agent(orchestrator_spec, active_servers)
        final_prompt = f"""
User request:
{message}

Discovery findings:
{discovery_text}

Draft design response:
{design_text}

Review notes:
{review_text}

Task:
Produce the final answer to the user.

Rules:
- Use the design response as the main draft.
- Incorporate justified review improvements if review was enabled.
- Do not mention internal pipeline stages unless the user explicitly asked for them.
"""
        final_result = await Runner.run(orchestrator_agent, final_prompt)
        final_text = str(final_result.final_output)
        append_trace(trace_file, "FINAL OUTPUT", final_text)
        return final_text


async def _run_peer_pipeline(message: str, verbose: bool, review: bool = False) -> str:
    settings, _, server_specs, agent_specs = _load_registry()
    if not settings.openai_api_key:
        raise typer.BadParameter("OPENAI_API_KEY is not set.")

    root_dir = Path.cwd()
    runtime = RuntimeManager(root_dir)
    factory = AgentFactory(root_dir)
    trace_file = settings.log_dir / "agent_trace.log"

    discovery_spec = agent_specs["discovery"]
    author_spec = agent_specs["design_author"]
    challenger_spec = agent_specs["design_challenger"]
    refiner_spec = agent_specs["design_refiner"]
    judge_spec = agent_specs["judge"]
    orchestrator_spec = agent_specs["orchestrator"]

    all_server_ids = sorted(
        {
            *discovery_spec.allowed_servers,
            *author_spec.allowed_servers,
            *challenger_spec.allowed_servers,
            *refiner_spec.allowed_servers,
            *judge_spec.allowed_servers,
            *orchestrator_spec.allowed_servers,
        }
    )
    servers = [runtime.build_server(server_specs[sid]) for sid in all_server_ids if sid in server_specs]

    async with MultiServerContext(servers) as active_servers:
        append_trace(trace_file, "USER INPUT", message)

        if verbose:
            console.print(Panel.fit("Running Discovery Agent", style="cyan"))
        discovery_agent = factory.build_agent(discovery_spec, active_servers)
        discovery_prompt = f"""
User request:
{message}

Task:
Inspect the available sources and retrieve the most relevant material for this request.

Rules:
- For workspace sources, all paths must be relative to the workspace root.
- Never guess file paths, site names, drive IDs, item IDs, or document IDs.
- Always list or search before reading.
- Only read a path or item returned by a listing/search tool in this run.
- For supported document formats such as .docx, .pdf, .pptx, .xlsx, use the document-reading tools.
- For plain text files, use workspace text reads where appropriate.
- Use SharePoint tools when the relevant information may be in SharePoint.
- When using SharePoint, first check auth status before searching.
- If no valid silent token is available, report that login is required.
- Do not trigger interactive SharePoint login unless explicitly requested by the user.
- If a tool fails, report the exact tool name and exact error.
- Do not claim you inspected or read a source unless a tool call succeeded.
"""
        discovery_result = await Runner.run(discovery_agent, discovery_prompt)
        discovery_text = str(discovery_result.final_output)
        append_trace(trace_file, "DISCOVERY OUTPUT", discovery_text)
        if verbose:
            console.print(Markdown(f"## Discovery Agent\n\n{discovery_text}"))

        if verbose:
            console.print(Panel.fit("Running Design Author", style="green"))
        author_agent = factory.build_agent(author_spec, active_servers)
        author_prompt = f"""
User request:
{message}

Discovery findings:
{discovery_text}

Task:
Draft the strongest practical answer you can from the verified findings.

Rules:
- Treat the discovery findings as the only verified retrieval for this run.
- Do not invent sources, file contents, or SharePoint details.
- If discovery found gaps, be transparent about them.
"""
        author_result = await Runner.run(author_agent, author_prompt)
        author_text = str(author_result.final_output)
        append_trace(trace_file, "AUTHOR OUTPUT", author_text)
        if verbose:
            console.print(Markdown(f"## Design Author\n\n{author_text}"))

        challenger_text = "Peer challenge skipped because review is disabled."
        refiner_text = author_text
        judge_text = "Judge stage skipped because review is disabled."

        if review:
            if verbose:
                console.print(Panel.fit("Running Design Challenger", style="yellow"))
            challenger_agent = factory.build_agent(challenger_spec, active_servers)
            challenger_prompt = f"""
User request:
{message}

Discovery findings:
{discovery_text}

Draft design response:
{author_text}

Task:
Challenge the draft and identify its weaknesses.

Rules:
- Work only from the user request, discovery findings, and draft.
- Do not invent sources or evidence.

Highlight:
- unclear reasoning
- weak assumptions
- missing constraints
- delivery risks
- architecture gaps
- better alternatives if justified
"""
            challenger_result = await Runner.run(challenger_agent, challenger_prompt)
            challenger_text = str(challenger_result.final_output)
            append_trace(trace_file, "CHALLENGER OUTPUT", challenger_text)
            if verbose:
                console.print(Markdown(f"## Design Challenger\n\n{challenger_text}"))

            if verbose:
                console.print(Panel.fit("Running Design Refiner", style="blue"))
            refiner_agent = factory.build_agent(refiner_spec, active_servers)
            refiner_prompt = f"""
User request:
{message}

Discovery findings:
{discovery_text}

Original draft:
{author_text}

Challenge:
{challenger_text}

Task:
Produce a refined answer.

Rules:
- Keep the useful parts of the original draft.
- Correct the weaknesses identified by the challenger.
- Do not invent evidence or file contents.
- Keep the answer practical and clear.
"""
            refiner_result = await Runner.run(refiner_agent, refiner_prompt)
            refiner_text = str(refiner_result.final_output)
            append_trace(trace_file, "REFINER OUTPUT", refiner_text)
            if verbose:
                console.print(Markdown(f"## Design Refiner\n\n{refiner_text}"))

            if verbose:
                console.print(Panel.fit("Running Judge", style="magenta"))
            judge_agent = factory.build_agent(judge_spec, active_servers)
            judge_prompt = f"""
User request:
{message}

Discovery findings:
{discovery_text}

Challenge:
{challenger_text}

Refined draft:
{refiner_text}

Task:
Decide whether the refined answer is good enough.

Rules:
- Work only from the user request, discovery findings, critique, and refined answer.
- Do not invent new evidence.
- Be decisive.

Check:
- relevance to the request
- fidelity to the evidence
- whether major critique points were addressed
- whether the answer is clear, useful, and internally consistent

Output:
- decision: accept / revise
- reason
- remaining issues, if any
"""
            judge_result = await Runner.run(judge_agent, judge_prompt)
            judge_text = str(judge_result.final_output)
            append_trace(trace_file, "JUDGE OUTPUT", judge_text)
            if verbose:
                console.print(Markdown(f"## Judge\n\n{judge_text}"))
        else:
            append_trace(trace_file, "CHALLENGER OUTPUT", "Challenger stage skipped.")
            append_trace(trace_file, "REFINER OUTPUT", "Refiner stage skipped; author draft used directly.")
            append_trace(trace_file, "JUDGE OUTPUT", judge_text)
            if verbose:
                console.print(Panel.fit("Skipping peer review stages", style="yellow"))

        if verbose:
            console.print(Panel.fit("Running Orchestrator", style="white"))
        orchestrator_agent = factory.build_agent(orchestrator_spec, active_servers)
        final_prompt = f"""
User request:
{message}

Discovery findings:
{discovery_text}

Original draft:
{author_text}

Challenge:
{challenger_text}

Refined draft:
{refiner_text}

Judge decision:
{judge_text}

Task:
Produce the final answer to the user.

Rules:
- Use the refined draft as the main body.
- Incorporate only improvements justified by the critique and judge decision.
- Do not mention internal peer stages unless the user explicitly asked for them.
"""
        final_result = await Runner.run(orchestrator_agent, final_prompt)
        final_text = str(final_result.final_output)
        append_trace(trace_file, "FINAL OUTPUT", final_text)
        return final_text


async def _run_with_routing(
    message: str,
    verbose: bool,
    review: bool,
    decision: RoutingDecision,
) -> str:
    if decision.mode == "peer":
        return await _run_peer_pipeline(message, verbose, review=review)
    if decision.mode == "pipeline":
        return await _run_pipeline(message, verbose, review=review)
    return await _run_single(message, decision.agent or "orchestrator")


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
    mode_pinned = True if (peer or pipeline) else False
    agent_pinned = True if (agent_id != "orchestrator") else False

    console.print("[bold green]crisAI interactive chat[/bold green]")
    console.print(f"Session: [bold]{current_session}[/bold]")
    console.print(f"Mode: [bold]{current_mode}[/bold] | Agent: [bold]{current_agent}[/bold]")
    console.print(f"Review: [bold]{'on' if current_review else 'off'}[/bold]")
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

        if user_input in {"/exit", "/quit"}:
            break

        if user_input == "/help":
            console.print(
                Markdown(
                    """
### Commands
- `/exit` or `/quit` — leave chat
- `/mode single` — use single-agent mode and pin the mode
- `/mode pipeline` — use pipeline mode and pin the mode
- `/mode peer` — use peer mode and pin the mode
- `/review on` — enable review
- `/review off` — disable review
- `/list servers` — list registered MCP servers
- `/list agents` — list registered agents
- `/history` — show saved conversation history in this session
- `/clear` — clear conversation history for this session
- `/session <name>` — switch to another persistent session
- `/agent <id>` — set single-agent target and pin the agent
- `/help` — show this help
"""
                )
            )
            continue

        if user_input == "/clear":
            history.clear()
            _save_history(current_session, history)
            console.print(f"[yellow]Conversation history cleared for session '{current_session}'.[/yellow]")
            continue

        if user_input in {"/list servers", "/list-servers"}:
            _print_servers_table()
            continue

        if user_input in {"/list agents", "/list-agents"}:
            _print_agents_table()
            continue

        if user_input == "/history":
            if not history:
                console.print("[yellow]No history in this session.[/yellow]")
            else:
                console.print(Markdown("### Session history"))
                for idx, (role, content) in enumerate(history[-20:], start=1):
                    label = "User" if role == "user" else "Assistant"
                    console.print(f"[bold]{idx}. {label}[/bold]: {content[:500]}")
            continue

        if user_input.startswith("/session "):
            new_session = user_input.split(maxsplit=1)[1].strip()
            if not new_session:
                console.print("[red]Please provide a session name.[/red]")
                continue

            current_session = new_session
            history = _load_history(current_session)
            console.print(f"[green]Switched to session '{current_session}'.[/green]")
            console.print(f"[green]Loaded history entries: {len(history)}[/green]")
            continue

        if user_input.startswith("/mode "):
            mode = user_input.split(maxsplit=1)[1].strip().lower()
            if mode in {"single", "pipeline", "peer"}:
                current_mode = mode
                mode_pinned = True
                console.print(f"[green]Mode set to {current_mode}[/green]")
            else:
                console.print("[red]Invalid mode. Use single, pipeline, or peer.[/red]")
            continue

        if user_input.startswith("/review "):
            value = user_input.split(maxsplit=1)[1].strip().lower()
            if value in {"on", "true", "yes"}:
                current_review = True
                console.print("[green]Review enabled.[/green]")
            elif value in {"off", "false", "no"}:
                current_review = False
                console.print("[green]Review disabled.[/green]")
            else:
                console.print("[red]Invalid review setting. Use /review on or /review off.[/red]")
            continue

        if user_input.startswith("/agent "):
            current_agent = user_input.split(maxsplit=1)[1].strip()
            agent_pinned = True
            console.print(f"[green]Single-agent target set to {current_agent}[/green]")
            continue

        chat_input = _build_chat_input(user_input, history)

        explicit_mode_override = current_mode if mode_pinned else None
        explicit_agent_override = current_agent if agent_pinned else None

        decision = _resolve_route(
            chat_input,
            review_enabled=current_review,
            mode_override=explicit_mode_override,
            agent_override=explicit_agent_override,
        )
        console.print(_route_display(decision))

        async def _run() -> str:
            return await _run_with_routing(chat_input, verbose, current_review, decision)

        try:
            text = asyncio.run(_run())
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            continue

        console.print()
        console.print(Markdown(text))
        console.print()

        history.append(("user", user_input))
        history.append(("assistant", text))
        _save_history(current_session, history)


if __name__ == "__main__":
    app()
