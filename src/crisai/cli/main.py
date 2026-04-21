from __future__ import annotations

import asyncio
import typer
from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory

from crisai.cli.chat_context import build_chat_input
from crisai.cli.chat_controller import ChatRuntimeState, handle_chat_command
from crisai.cli.display import print_final_answer, print_final_recommendation, print_status_message
from crisai.cli.session_store import cli_history_file, load_history, save_history
from crisai.cli.status_views import print_agents_table, print_chat_state, print_servers_table, route_display
from crisai.config import load_settings
from crisai.orchestration.router import RoutingDecision, decide_route
from crisai.registry import Registry
from .pipelines import run_peer_pipeline, run_pipeline, run_single


app = typer.Typer(help="crisAI CLI")


def _load_registry():
    """Loads runtime settings and enabled registry entries."""
    settings = load_settings()
    registry = Registry(settings.registry_dir)
    server_specs = {s.id: s for s in registry.load_servers() if s.enabled}
    agent_specs = {a.id: a for a in registry.load_agents()}
    return settings, registry, server_specs, agent_specs


def _resolve_route(
    user_input: str,
    review_enabled: bool,
    mode_override: str | None = None,
    agent_override: str | None = None,
) -> RoutingDecision:
    """Delegates routing decisions to the router."""
    return decide_route(
        user_input=user_input,
        review_enabled=review_enabled,
        current_mode=mode_override,
        selected_agent=agent_override,
    )


def _effective_pipeline_review(decision: RoutingDecision) -> bool:
    """Returns whether pipeline review should execute for this decision."""
    return decision.mode == "pipeline" and decision.needs_review


def _render_final_output(decision: RoutingDecision, body: str) -> None:
    """Renders the final output according to the chosen mode."""
    if decision.mode == "peer":
        print_final_recommendation(body)
        return
    print_final_answer(body)


@app.command("list-servers")
def list_servers() -> None:
    """Lists registered MCP servers."""
    print_servers_table()


@app.command("list-agents")
def list_agents() -> None:
    """Lists registered agents."""
    print_agents_table()


async def _run_with_routing(
    message: str,
    verbose: bool,
    review: bool,
    decision: RoutingDecision,
) -> str:
    """Executes the selected runtime path for a routed request."""
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


@app.command()
def ask(
    message: str = typer.Option(..., "--message", "-m"),
    agent_id: str = typer.Option("orchestrator", "--agent"),
    pipeline: bool = typer.Option(False, "--pipeline", help="Run the visible discovery/design/review/orchestrator pipeline."),
    peer: bool = typer.Option(False, "--peer", help="Run the peer workflow: discovery -> author -> challenger -> refiner -> judge -> orchestrator."),
    review: bool = typer.Option(False, "--review/--no-review", help="Review is off by default. Use --review to enable it."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Runs a single non-interactive crisAI request."""
    decision = _resolve_route(
        message,
        review_enabled=review,
        mode_override="peer" if peer else "pipeline" if pipeline else None,
        agent_override=agent_id if agent_id != "orchestrator" else None,
    )
    print_status_message(route_display(decision), title="🧭 Routing decision")

    async def _run() -> None:
        text = await _run_with_routing(message, verbose, review, decision)
        _render_final_output(decision, text)

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
    """Starts the interactive crisAI chat session."""
    state = ChatRuntimeState(
        current_session=session,
        history=load_history(session),
        current_mode="peer" if peer else "pipeline" if pipeline else "single",
        current_agent=agent_id,
        current_review=review,
        current_verbose=verbose,
        mode_pinned=True if (peer or pipeline) else False,
        agent_pinned=True if (agent_id != "orchestrator") else False,
    )

    print_chat_state(
        current_session=state.current_session,
        current_mode=state.current_mode,
        current_agent=state.current_agent,
        current_review=state.current_review,
        current_verbose=state.current_verbose,
        mode_pinned=state.mode_pinned,
        agent_pinned=state.agent_pinned,
        history_count=len(state.history),
    )

    while True:
        try:
            user_input = prompt(
                "> ",
                history=FileHistory(str(cli_history_file())),
                auto_suggest=AutoSuggestFromHistory(),
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print_status_message("Exiting.", title="👋 Session closed")
            break

        if not user_input:
            continue

        try:
            handled = handle_chat_command(user_input, state)
        except EOFError:
            break

        if handled:
            continue

        chat_input = build_chat_input(user_input, state.history)
        decision = _resolve_route(
            user_input,
            review_enabled=state.current_review,
            mode_override=state.current_mode if state.mode_pinned else None,
            agent_override=state.current_agent if state.agent_pinned else None,
        )

        print_status_message(route_display(decision), title="🧭 Routing decision")

        async def _run() -> str:
            return await _run_with_routing(chat_input, state.current_verbose, state.current_review, decision)

        try:
            text = asyncio.run(_run())
        except Exception as e:
            print_status_message(str(e), title="❌ Error")
            continue

        _render_final_output(decision, text)

        state.history.append(("user", user_input))
        state.history.append(("assistant", text))
        save_history(state.current_session, state.history)


if __name__ == "__main__":
    app()
