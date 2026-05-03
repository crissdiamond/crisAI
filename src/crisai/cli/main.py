from __future__ import annotations

import asyncio
import logging
import re
import ssl
from contextlib import contextmanager
from dataclasses import is_dataclass, replace
from types import SimpleNamespace
from typing import Any, Awaitable

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
from crisai.logging_utils import configure_logging, get_logger
from crisai.orchestration.router import RoutingDecision, decide_route
from crisai.registry import Registry

from .pipelines import run_peer_pipeline, run_pipeline, run_single

app = typer.Typer(help="crisAI CLI")
logger = get_logger(__name__)


@app.callback()
def _cli_bootstrap(ctx: typer.Context) -> None:
    """Ensure log directory and crisai.log exist before any subcommand runs.

    Bare ``crisai`` (no subcommand) only prints help and skips this setup.
    """
    if ctx.invoked_subcommand is None:
        return
    configure_logging(load_settings())
_EXPECTED_RUNTIME_ERRORS = (typer.BadParameter, ValueError, RuntimeError, FileNotFoundError)

_EXPLICIT_MODE_PATTERNS: dict[str, tuple[str, ...]] = {
    "peer": (
        r"\buse\s+peer\s+mode\b",
        r"\brun\s+in\s+peer\s+mode\b",
        r"\bshow\s+the\s+peer\s+conversation\b",
        r"\bpeer\s+conversation\b",
        r"\bauthor\b.*\bchallenger\b.*\brefiner\b.*\bjudge\b",
    ),
    "pipeline": (
        r"\buse\s+pipeline\s+mode\b",
        r"\brun\s+the\s+pipeline\b",
        r"\bdiscovery\b.*\bdesign\b.*\breview\b.*\borchestrator\b",
        r"\bretrieval\s+planner\b.*\bdesign\b.*\breview\b.*\borchestrator\b",
    ),
    "single": (
        r"\buse\s+single\s+mode\b",
        r"\brun\s+a\s+single\s+agent\b",
    ),
}

_GENERATIVE_PEER_PATTERNS: tuple[str, ...] = (
    r"\bpropose\b",
    r"\bdesign\b",
    r"\bdraft\b",
    r"\bcreate\b",
    r"\bwrite\b",
    r"\bimprov(?:e|ing|ement)\b",
    r"\brefactor\b",
    r"\bsimple\s+design\b",
)

_RETRIEVAL_REQUIRED_PATTERNS: tuple[str, ...] = (
    r"\bbased\s+on\b",
    r"\bfrom\s+the\s+workspace\b",
    r"\bfrom\s+existing\b",
    r"\buse\s+the\s+existing\b",
    r"\buse\s+the\s+document\b",
    r"\breview\s+the\s+document\b",
    r"\bretrieve\b",
    r"\blook\s+up\b",
    r"\bfind\b",
    r"\bsearch\b",
    r"\bsource\b",
    r"\bcitation\b",
    r"\bcontext\s+from\b",
)


def _load_registry():
    """Load runtime settings and enabled registry entries.

    Returns:
        Tuple containing settings, registry, enabled server specs, agent specs,
        and model specs loaded from the active registry directory.
    """
    settings = load_settings()
    configure_logging(settings)

    registry = Registry(settings.registry_dir)
    server_specs = {s.id: s for s in registry.load_servers() if s.enabled}
    agent_specs = {a.id: a for a in registry.load_agents()}
    model_specs = registry.load_models()

    logger.debug(
        "Registry loaded.",
        extra={
            "server_count": len(server_specs),
            "agent_count": len(agent_specs),
            "model_count": len(model_specs),
        },
    )
    return settings, registry, server_specs, agent_specs, model_specs



def _detect_explicit_mode(user_input: str) -> str | None:
    """Return a mode explicitly requested in the user prompt when present.

    Args:
        user_input: Raw user text entered in the CLI.

    Returns:
        One of ``peer``, ``pipeline``, or ``single`` when the request contains
        an explicit mode instruction. Returns ``None`` when no strong signal is
        present.
    """
    normalized = " ".join(user_input.lower().split())
    for mode, patterns in _EXPLICIT_MODE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL):
                return mode
    return None



def _should_disable_peer_retrieval(user_input: str, explicit_mode: str | None, decision: RoutingDecision) -> bool:
    """Return whether retrieval stages should be skipped for a peer design task.

    For generation-first peer requests, retrieval can bias the entire workflow
    toward stale workspace artefacts. This override only applies when the user
    explicitly asks for peer mode and the prompt is asking the agents to create
    or improve a design rather than analyse existing sources.

    Args:
        user_input: Raw user prompt for the current request.
        explicit_mode: Mode explicitly detected from the prompt, if any.
        decision: Router decision before local CLI overrides.

    Returns:
        ``True`` when peer retrieval should be disabled locally.
    """
    if getattr(decision, "mode", None) != "peer":
        return False

    if explicit_mode != "peer":
        return False

    normalized = " ".join(user_input.lower().split())

    for pattern in _RETRIEVAL_REQUIRED_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL):
            return False

    if re.search(r"\bauthor\b.*\bchallenger\b.*\brefiner\b.*\bjudge\b", normalized, flags=re.IGNORECASE | re.DOTALL):
        return True

    return any(
        re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
        for pattern in _GENERATIVE_PEER_PATTERNS
    )



def _copy_decision_with_updates(decision: RoutingDecision, **updates):
    """Return a decision-like object with selected fields updated.

    This supports both mutable objects and frozen dataclass-style routing
    decisions without forcing changes in the router implementation.
    """
    try:
        for field_name, value in updates.items():
            setattr(decision, field_name, value)
        return decision
    except Exception:  # noqa: BLE001
        if is_dataclass(decision):
            return replace(decision, **updates)

    data = vars(decision).copy() if hasattr(decision, "__dict__") else {}
    data.update(updates)
    return SimpleNamespace(**data)



def _apply_decision_overrides(user_input: str, explicit_mode: str | None, decision: RoutingDecision):
    """Apply local CLI safeguards on top of the router decision.

    The router remains the source of truth for general routing, but the CLI can
    impose narrower interaction guarantees when the user gave a clear local
    instruction such as explicit peer mode for a generative design task.
    """
    if _should_disable_peer_retrieval(user_input, explicit_mode, decision):
        return _copy_decision_with_updates(decision, needs_retrieval=False)
    return decision


@contextmanager
def _suppress_console_info_logs():
    """Hide non-file INFO logs from the interactive console.

    The CLI should remain clean while preserving structured logs written to
    files. This helper temporarily raises the threshold only for non-file
    handlers such as console or Rich handlers.
    """
    handler_states: list[tuple[logging.Handler, int]] = []
    seen_handler_ids: set[int] = set()

    logger_objects: list[logging.Logger] = [logging.getLogger()]
    logger_objects.extend(
        candidate
        for candidate in logging.root.manager.loggerDict.values()
        if isinstance(candidate, logging.Logger)
    )

    for logger_obj in logger_objects:
        for handler in logger_obj.handlers:
            handler_id = id(handler)
            if handler_id in seen_handler_ids:
                continue
            if isinstance(handler, logging.FileHandler):
                continue
            seen_handler_ids.add(handler_id)
            handler_states.append((handler, handler.level))
            if handler.level < logging.WARNING:
                handler.setLevel(logging.WARNING)

    try:
        yield
    finally:
        for handler, original_level in handler_states:
            handler.setLevel(original_level)



def _resolve_route(
    user_input: str,
    review_enabled: bool,
    mode_override: str | None = None,
    agent_override: str | None = None,
) -> RoutingDecision:
    """Delegate routing decisions to the router."""
    return decide_route(
        user_input=user_input,
        review_enabled=review_enabled,
        current_mode=mode_override,
        selected_agent=agent_override,
    )



def _effective_pipeline_review(decision: RoutingDecision) -> bool:
    """Return whether pipeline review should execute for this decision."""
    return decision.mode == "pipeline" and decision.needs_review



def _render_final_output(decision: RoutingDecision, body: str) -> None:
    """Render the final output according to the chosen mode."""
    if decision.mode == "peer":
        print_final_recommendation(body)
        return
    print_final_answer(body)


def _render_runtime_error(exc: Exception) -> None:
    """Render runtime failures with consistent expected/unexpected handling."""
    if isinstance(exc, _EXPECTED_RUNTIME_ERRORS):
        logger.warning("Request failed with expected runtime error.", extra={"error_type": type(exc).__name__})
        print_status_message(str(exc), title="⚠ Request error")
        return

    logger.exception("Request failed with unexpected runtime error.")
    print_status_message(
        "Unexpected runtime error. Check logs/ (agent_trace.jsonl, crisai.log, *_mcp.log) for details.",
        title="❌ Unexpected error",
    )


def _is_benign_ssl_shutdown_context(context: dict[str, Any]) -> bool:
    """Return whether an asyncio loop error context is a benign SSL shutdown noise."""
    message = str(context.get("message", "")).lower()
    if "fatal error on ssl transport" in message:
        return True

    exc = context.get("exception")
    if isinstance(exc, ssl.SSLError):
        text = str(exc).lower()
        if "application data after close notify" in text:
            return True
    return False


def _run_async(coro: Awaitable[Any]) -> Any:
    """Run a coroutine with graceful loop teardown and benign SSL shutdown filtering."""
    loop = asyncio.new_event_loop()
    previous_loop = None
    try:
        try:
            previous_loop = asyncio.get_event_loop_policy().get_event_loop()
        except Exception:  # noqa: BLE001
            previous_loop = None

        def _exception_handler(current_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
            if _is_benign_ssl_shutdown_context(context):
                logger.debug("Suppressed benign asyncio SSL shutdown noise.", extra={"context": str(context)})
                return
            current_loop.default_exception_handler(context)

        loop.set_exception_handler(_exception_handler)
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:  # noqa: BLE001
            pass
        asyncio.set_event_loop(previous_loop)
        loop.close()


@app.command("list-servers")
def list_servers() -> None:
    """List registered MCP servers."""
    print_servers_table()


@app.command("list-agents")
def list_agents() -> None:
    """List registered agents."""
    print_agents_table()


async def _run_with_routing(
    message: str,
    verbose: bool,
    review: bool,
    decision: RoutingDecision,
) -> str:
    """Execute the selected runtime path for a routed request."""
    settings, _, server_specs, agent_specs, model_specs = _load_registry()
    effective_review = _effective_pipeline_review(decision)

    logger.info(
        "Executing request.",
        extra={
            "mode": decision.mode,
            "review_enabled": review,
            "effective_review": effective_review,
            "needs_retrieval": getattr(decision, "needs_retrieval", None),
            "selected_agent": decision.agent,
        },
    )

    if decision.mode == "peer":
        return await run_peer_pipeline(
            message,
            verbose,
            False,
            settings=settings,
            server_specs=server_specs,
            agent_specs=agent_specs,
            model_specs=model_specs,
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
            model_specs=model_specs,
        )
    return await run_single(
        message,
        decision.agent or "orchestrator",
        settings=settings,
        server_specs=server_specs,
        agent_specs=agent_specs,
        model_specs=model_specs,
    )


@app.command()
def ask(
    message: str = typer.Option(..., "--message", "-m"),
    agent_id: str = typer.Option("orchestrator", "--agent"),
    pipeline: bool = typer.Option(False, "--pipeline", help="Run the visible retrieval planner / design / review / orchestrator pipeline."),
    peer: bool = typer.Option(False, "--peer", help="Run the peer workflow: retrieval planner -> author -> challenger -> refiner -> judge -> orchestrator."),
    review: bool = typer.Option(False, "--review/--no-review", help="Review is off by default. Use --review to enable it."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run a single non-interactive crisAI request."""
    explicit_mode = _detect_explicit_mode(message)
    mode_override = "peer" if peer else "pipeline" if pipeline else explicit_mode

    decision = _resolve_route(
        message,
        review_enabled=review,
        mode_override=mode_override,
        agent_override=agent_id if agent_id != "orchestrator" else None,
    )
    decision = _apply_decision_overrides(message, explicit_mode, decision)
    print_status_message(route_display(decision), title="🧭 Routing decision")

    async def _run() -> None:
        text = await _run_with_routing(message, verbose, review, decision)
        _render_final_output(decision, text)

    try:
        with _suppress_console_info_logs():
            _run_async(_run())
    except Exception as exc:  # noqa: BLE001
        _render_runtime_error(exc)


@app.command()
def chat(
    agent_id: str = typer.Option("orchestrator", "--agent"),
    session: str = typer.Option("default", "--session", "-s", help="Persistent chat session name."),
    pipeline: bool = typer.Option(False, "--pipeline", help="Run the visible retrieval planner / design / review / orchestrator pipeline."),
    peer: bool = typer.Option(False, "--peer", help="Run the peer workflow: retrieval planner -> author -> challenger -> refiner -> judge -> orchestrator."),
    review: bool = typer.Option(False, "--review/--no-review", help="Review is off by default. Use --review to enable it."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Start the interactive crisAI chat session."""
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
    last_route_line: str | None = None

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
        explicit_mode = _detect_explicit_mode(user_input)
        mode_override = state.current_mode if state.mode_pinned else explicit_mode
        agent_override = state.current_agent if state.agent_pinned else None

        decision = _resolve_route(
            user_input,
            review_enabled=state.current_review,
            mode_override=mode_override,
            agent_override=agent_override,
        )
        decision = _apply_decision_overrides(user_input, explicit_mode, decision)

        current_route_line = route_display(decision)
        if current_route_line != last_route_line:
            print_status_message(current_route_line, title="🧭 Routing decision")
            last_route_line = current_route_line

        async def _run() -> str:
            return await _run_with_routing(chat_input, state.current_verbose, state.current_review, decision)

        try:
            with _suppress_console_info_logs():
                text = _run_async(_run())
        except Exception as exc:  # noqa: BLE001
            _render_runtime_error(exc)
            continue

        _render_final_output(decision, text)

        state.history.append(("user", user_input))
        state.history.append(("assistant", text))
        save_history(state.current_session, state.history)


if __name__ == "__main__":
    app()
