from __future__ import annotations

import asyncio
import logging
import re
import ssl
from collections.abc import Awaitable
from contextlib import contextmanager
from dataclasses import is_dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import typer
from prompt_toolkit import PromptSession, prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory

from crisai.cli.artefact_lifecycle import persist_reusable_deliverable
from crisai.cli.chat_context import (
    build_runtime_context_package,
    normalise_legacy_workspace_paths,
    update_session_memory,
)
from crisai.cli.chat_controller import ChatRuntimeState, handle_chat_command
from crisai.cli.display import (
    get_bottom_toolbar,
    print_final_answer,
    print_final_recommendation,
    print_status_message,
    sanitize_user_visible_text,
    update_terminal_title,
)
from crisai.cli.session_store import (
    clear_cli_history,
    clear_history,
    cli_history_file,
    list_task_names,
    load_history,
    save_history,
    session_dir,
    tasks_dir,
)
from crisai.cli.status_views import (
    print_agents_table,
    print_chat_state,
    print_servers_table,
    route_display,
)
from crisai.config import load_settings
from crisai.logging_utils import configure_logging, get_logger
from crisai.orchestration.exceptions import WorkflowValidationError
from crisai.orchestration.retrieval_checkpoint import (
    RetrievalCheckpointDecision,
    RetrievalCheckpointSnapshot,
)
from crisai.orchestration.router import RoutingDecision, decide_route
from crisai.orchestration.semantic_catalog import load_semantic_catalog
from crisai.registry import Registry
from crisai.registry_validation import run_doctor
from crisai.workspace.artefact_validation import validate_workspace_artefact_paths
from crisai.workspace.spaces import load_workspace_spaces

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
_EXPECTED_RUNTIME_ERRORS = (typer.BadParameter, WorkflowValidationError, ValueError, RuntimeError, FileNotFoundError)

def _interaction_patterns():
    return load_semantic_catalog().interaction


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
    for mode, patterns in _interaction_patterns().explicit_mode_patterns.items():
        for pattern in patterns:
            if pattern.search(normalized):
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

    interaction = _interaction_patterns()
    # Hard keep-on: for intranet-grounded or file-backed peer requests,
    # retrieval should remain enabled even in explicit generative peer mode.
    for pattern in interaction.peer_retrieval_force_patterns:
        if pattern.search(normalized):
            return False

    for pattern in interaction.retrieval_required_patterns:
        if pattern.search(normalized):
            return False

    if re.search(r"\bauthor\b.*\bchallenger\b.*\brefiner\b.*\bjudge\b", normalized, flags=re.IGNORECASE | re.DOTALL):
        return True

    return any(pattern.search(normalized) for pattern in interaction.generative_peer_patterns)


def _should_force_peer_retrieval(user_input: str, decision: RoutingDecision) -> bool:
    """Return whether retrieval should be force-enabled for peer mode.

    This guard protects intranet/source-grounded and file-backed peer requests
    from router or heuristic under-classification.
    """
    if getattr(decision, "mode", None) != "peer":
        return False
    normalized = " ".join(user_input.lower().split())
    return any(pattern.search(normalized) for pattern in _interaction_patterns().peer_retrieval_force_patterns)



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
    if _should_force_peer_retrieval(user_input, decision):
        return _copy_decision_with_updates(decision, needs_retrieval=True)
    if _should_disable_peer_retrieval(user_input, explicit_mode, decision):
        return _copy_decision_with_updates(decision, needs_retrieval=False)
    return decision


@contextmanager
def _suppress_console_info_logs():
    """Hide non-file INFO/WARNING logs from the interactive console.

    The CLI should remain clean while preserving structured logs written to
    files. This helper temporarily raises the threshold only for non-file
    handlers such as console or Rich handlers. Expected runtime failures are
    rendered as user-facing panels, so their warning log records do not need to
    appear in the transcript.
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
            if handler.level < logging.ERROR:
                handler.setLevel(logging.ERROR)

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
    settings = load_settings()
    return decide_route(
        user_input=user_input,
        review_enabled=review_enabled,
        current_mode=mode_override,
        selected_agent=agent_override,
        registry_dir=getattr(settings, "registry_dir", None),
    )


def _session_name_newest_by_mtime() -> str | None:
    """Return the newest persisted chat session name by file mtime.

    Preference order:
    1) newest non-default session when at least one exists
    2) otherwise newest session including ``default``
    """
    best_non_default_mtime: int | None = None
    best_non_default_name: str | None = None
    best_any_mtime: int | None = None
    best_name: str | None = None

    candidates = list(session_dir().glob("*.json"))
    for task_name in list_task_names():
        candidates.append(tasks_dir() / task_name / ".crisai" / "history.json")

    for file_path in candidates:
        try:
            mtime = file_path.stat().st_mtime_ns
        except OSError:
            continue
        stem = file_path.stem
        if file_path.name == "history.json" and file_path.parent.name == ".crisai":
            stem = file_path.parent.parent.name

        if best_any_mtime is None or mtime >= best_any_mtime:
            best_any_mtime = mtime
            best_name = stem

        if stem == "default":
            continue
        if best_non_default_mtime is None or mtime >= best_non_default_mtime:
            best_non_default_mtime = mtime
            best_non_default_name = stem

    return best_non_default_name or best_name


def _resolve_initial_chat_session(requested_session: str) -> str:
    """Resolve startup chat session.

    When chat starts with the default session value, prefer the most recently
    modified persisted session (if any) to resume the latest active context.
    """
    if requested_session != "default":
        return requested_session
    newest = _session_name_newest_by_mtime()
    return newest or requested_session



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


def _persist_failed_chat_turn(state: ChatRuntimeState, user_input: str, exc: Exception) -> None:
    """Persist failed turns so task history reflects what happened."""
    error_text = f"Request failed: {type(exc).__name__}: {exc}"
    state.history.append(("user", user_input))
    state.history.append(("assistant", sanitize_user_visible_text(error_text)))
    save_history(state.current_session, state.history)
    update_session_memory(state.current_session, state.history)


def _close_chat_session(state: ChatRuntimeState) -> None:
    """Persist current session state and render a consistent exit notice."""
    save_history(state.current_session, state.history)
    print_status_message("Exiting.", title="👋 Session closed")


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
            pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
            if pending:
                for task in pending:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:  # noqa: BLE001
            pass
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


@app.command("clear-session")
def clear_session(session: str = typer.Option("default", "--session", "-s", help="Session name to clear.")) -> None:
    """Clear persisted history for a named chat session."""
    clear_history(session)
    clear_cli_history(session)
    print_status_message(
        f"Conversation history cleared for session '{session}'.",
        title="🧹 Session cleared",
    )


@app.command("validate-artefacts")
def validate_artefacts(
    path: list[str] | None = typer.Option(
        None,
        "--path",
        "-p",
        help="Repo-relative Markdown path(s). Omit to scan configured knowledge, staging, and task roots.",
    ),
) -> None:
    """Validate Markdown artefacts against ``registry/workspace_artifact_profiles.yaml``."""
    settings = load_settings()
    root = Path(settings.root_dir)
    registry_dir = Path(settings.registry_dir)
    spaces = load_workspace_spaces(registry_dir)
    targets: list[str]
    if path:
        targets = sorted({str(Path(p).as_posix().lstrip("./")) for p in path})
    else:
        targets = []
        for base in (
            settings.workspace_dir / spaces.knowledge_root,
            settings.workspace_dir / spaces.knowledge_staging_root,
            settings.workspace_dir / spaces.tasks_root,
        ):
            if not base.is_dir():
                continue
            for fp in sorted(base.rglob("*.md")):
                targets.append(fp.resolve().relative_to(root).as_posix())
    result = validate_workspace_artefact_paths(
        root_dir=root, relative_paths=targets, registry_dir=registry_dir
    )
    if result.ok:
        print_status_message("All checked files passed artefact profiles.", title="✅ validate-artefacts")
        raise typer.Exit(0)
    body = "- " + "\n- ".join(result.violations)
    print_status_message(body, title="❌ Artefact validation failed")
    raise typer.Exit(1)


@app.command("doctor")
def doctor(
    models: bool = typer.Option(
        False,
        "--models",
        help="Dry-build configured agent models without calling provider APIs.",
    ),
) -> None:
    """Validate local registry, prompt, environment, and repo hygiene."""
    settings = load_settings()
    result = run_doctor(
        root_dir=Path(settings.root_dir),
        registry_dir=Path(settings.registry_dir),
        validate_models=models,
    )
    def _format_issues(issues: tuple) -> list[str]:
        out: list[str] = []
        for issue in issues:
            out.append(f"- {issue.message}")
            if issue.hint:
                out.append(f"  → {issue.hint}")
        return out

    lines: list[str] = []
    if result.info:
        lines.append("Registry:")
        lines.extend(f"  {line}" for line in result.info)
        lines.append("")
    if result.errors:
        lines.append("Errors:")
        lines.extend(_format_issues(result.errors))
    if result.warnings:
        lines.append("Warnings:")
        lines.extend(_format_issues(result.warnings))
    if not result.errors and not result.warnings:
        lines.append("No configuration issues found.")
        lines.append("")
        lines.append("Setup guidance:")
        lines.append("- Put local credentials and runtime overrides in `.env` copied from `.env.example`.")
        lines.append("- Keep shared agents, models, MCP servers, policy, and memory defaults in `registry/*.yaml`.")
        lines.append("- Run `crisai doctor --models` after changing model providers or agent model_ref values.")

    if result.ok:
        print_status_message("\n".join(lines), title="✅ crisai doctor")
        raise typer.Exit(0)
    print_status_message("\n".join(lines), title="❌ crisai doctor")
    raise typer.Exit(1)


async def _run_with_routing(
    message: str,
    verbose: bool,
    review: bool,
    decision: RoutingDecision,
    *,
    user_intent_message: str | None = None,
    session_name: str | None = None,
    retrieval_checkpoint_enabled: bool | None = None,
    retrieval_checkpoint_handler=None,
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
            user_intent_message=user_intent_message,
            session_name=session_name,
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
            user_intent_message=user_intent_message,
            session_name=session_name,
            retrieval_checkpoint_enabled=retrieval_checkpoint_enabled,
            retrieval_checkpoint_handler=retrieval_checkpoint_handler,
        )
    return await run_single(
        message,
        decision.agent or "orchestrator",
        settings=settings,
        server_specs=server_specs,
        agent_specs=agent_specs,
        model_specs=model_specs,
        user_intent_message=user_intent_message,
        session_name=session_name,
    )


def _render_retrieval_checkpoint_snapshot(snapshot: RetrievalCheckpointSnapshot) -> str:
    """Return the CLI markdown shown at the retrieval checkpoint."""
    parts = [
        "Retrieval has completed. Review the evidence before downstream stages run.",
        "",
        f"Redirects used: {snapshot.attempt}/{snapshot.max_redirects}",
    ]
    if snapshot.evidence_brief.strip():
        parts.extend(["", "## Evidence Brief", snapshot.evidence_brief.strip()])
    elif snapshot.retrieval_prose.strip():
        parts.extend(["", "## Retrieval Output", snapshot.retrieval_prose.strip()])
    if snapshot.retrieval_plan.strip():
        parts.extend(["", "## Retrieval Plan", snapshot.retrieval_plan.strip()])
    return "\n".join(parts)


def _resolve_checkpoint_override(enabled_flag: bool, disabled_flag: bool) -> bool | None:
    """Resolve per-command checkpoint flags into a tri-state override."""
    enabled_flag = enabled_flag if isinstance(enabled_flag, bool) else False
    disabled_flag = disabled_flag if isinstance(disabled_flag, bool) else False
    if enabled_flag and disabled_flag:
        raise typer.BadParameter("Use either --retrieval-checkpoint or --no-retrieval-checkpoint, not both.")
    if enabled_flag:
        return True
    if disabled_flag:
        return False
    return None


async def _prompt_retrieval_checkpoint(snapshot: RetrievalCheckpointSnapshot) -> RetrievalCheckpointDecision:
    """Prompt the CLI user for a retrieval checkpoint decision."""
    print_status_message(_render_retrieval_checkpoint_snapshot(snapshot), title="⏸ Retrieval checkpoint")
    can_redirect = snapshot.attempt < snapshot.max_redirects
    choices = "continue, redirect, stop" if can_redirect else "continue, stop"
    session: PromptSession[str] = PromptSession()
    while True:
        answer = (await session.prompt_async(f"Checkpoint decision ({choices}) > ")).strip().lower()
        if answer in {"", "c", "continue"}:
            return RetrievalCheckpointDecision.continue_()
        if answer in {"s", "stop"}:
            return RetrievalCheckpointDecision.stop()
        if answer in {"r", "redirect"}:
            if not can_redirect:
                print_status_message("Redirect limit reached. Choose continue or stop.", title="⚠ Checkpoint")
                continue
            instruction = (await session.prompt_async("Redirect retrieval with > ")).strip()
            if instruction:
                return RetrievalCheckpointDecision.redirect(instruction)
            print_status_message("Redirect guidance cannot be empty.", title="⚠ Checkpoint")
            continue
        print_status_message(f"Invalid checkpoint decision. Use {choices}.", title="⚠ Checkpoint")


@app.command()
def ask(
    message: str = typer.Option(..., "--message", "-m"),
    agent_id: str = typer.Option("orchestrator", "--agent"),
    pipeline: bool = typer.Option(False, "--pipeline", help="Run the visible retrieval planner / design / review / orchestrator pipeline."),
    peer: bool = typer.Option(False, "--peer", help="Run the peer workflow: retrieval planner -> author -> challenger -> refiner -> judge -> orchestrator."),
    review: bool = typer.Option(False, "--review/--no-review", help="Review is off by default. Use --review to enable it."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    retrieval_checkpoint: bool = typer.Option(
        False,
        "--retrieval-checkpoint",
        help="Enable the retrieval checkpoint for this run.",
    ),
    no_retrieval_checkpoint: bool = typer.Option(
        False,
        "--no-retrieval-checkpoint",
        help="Disable the retrieval checkpoint for this run.",
    ),
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
    checkpoint_override = _resolve_checkpoint_override(retrieval_checkpoint, no_retrieval_checkpoint)

    async def _run() -> None:
        text = await _run_with_routing(
            message,
            verbose,
            review,
            decision,
            user_intent_message=message,
            retrieval_checkpoint_enabled=checkpoint_override,
            retrieval_checkpoint_handler=_prompt_retrieval_checkpoint,
        )
        _render_final_output(decision, text)

    try:
        update_terminal_title("working")
        with _suppress_console_info_logs():
            _run_async(_run())
        update_terminal_title("ready")
    except Exception as exc:  # noqa: BLE001
        update_terminal_title("ready")
        _render_runtime_error(exc)


@app.command()
def chat(
    agent_id: str = typer.Option("orchestrator", "--agent"),
    session: str = typer.Option("default", "--session", "-s", help="Persistent chat session name."),
    pipeline: bool = typer.Option(False, "--pipeline", help="Run the visible retrieval planner / design / review / orchestrator pipeline."),
    peer: bool = typer.Option(False, "--peer", help="Run the peer workflow: retrieval planner -> author -> challenger -> refiner -> judge -> orchestrator."),
    review: bool = typer.Option(False, "--review/--no-review", help="Review is off by default. Use --review to enable it."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    retrieval_checkpoint: bool = typer.Option(
        False,
        "--retrieval-checkpoint",
        help="Enable the retrieval checkpoint for this chat session.",
    ),
    no_retrieval_checkpoint: bool = typer.Option(
        False,
        "--no-retrieval-checkpoint",
        help="Disable the retrieval checkpoint for this chat session.",
    ),
) -> None:
    """Start the interactive crisAI chat session."""
    update_terminal_title("ready")
    initial_session = _resolve_initial_chat_session(session)
    checkpoint_override = _resolve_checkpoint_override(retrieval_checkpoint, no_retrieval_checkpoint)
    checkpoint_default = load_settings().retrieval_checkpoint_enabled if checkpoint_override is None else checkpoint_override
    state = ChatRuntimeState(
        current_session=initial_session,
        history=load_history(initial_session),
        current_mode="peer" if peer else "pipeline" if pipeline else "single",
        current_agent=agent_id,
        current_review=review,
        current_verbose=verbose,
        current_retrieval_checkpoint=checkpoint_default,
        mode_pinned=True if (peer or pipeline) else False,
        agent_pinned=True if (agent_id != "orchestrator") else False,
    )

    print_chat_state(
        current_session=state.current_session,
        current_mode=state.current_mode,
        current_agent=state.current_agent,
        current_review=state.current_review,
        current_verbose=state.current_verbose,
        current_retrieval_checkpoint=state.current_retrieval_checkpoint,
        mode_pinned=state.mode_pinned,
        agent_pinned=state.agent_pinned,
        history_count=len(state.history),
    )
    last_route_line: str | None = None

    while True:
        try:
            update_terminal_title("input")
            user_input = prompt(
                "> ",
                history=FileHistory(str(cli_history_file(state.current_session))),
                auto_suggest=AutoSuggestFromHistory(),
                bottom_toolbar=lambda: get_bottom_toolbar(
                    state.current_session,
                    state.current_mode,
                    state.settings.model.default_model
                ),
            ).strip()
            update_terminal_title("working")
        except (EOFError, KeyboardInterrupt):
            _close_chat_session(state)
            break

        if not user_input:
            continue

        try:
            handled = handle_chat_command(user_input, state)
        except EOFError:
            _close_chat_session(state)
            break

        if handled:
            continue

        context_package = build_runtime_context_package(user_input, state.history, session_name=state.current_session)
        if context_package.drift_nudge:
            print_status_message(context_package.drift_nudge, title="💡 Session context")
        chat_input = context_package.prompt
        runtime_user_input = normalise_legacy_workspace_paths(user_input)
        explicit_mode = _detect_explicit_mode(runtime_user_input)
        mode_override = state.current_mode if state.mode_pinned else explicit_mode
        agent_override = state.current_agent if state.agent_pinned else None

        decision = _resolve_route(
            runtime_user_input,
            review_enabled=state.current_review,
            mode_override=mode_override,
            agent_override=agent_override,
        )
        decision = _apply_decision_overrides(runtime_user_input, explicit_mode, decision)

        current_route_line = route_display(decision)
        if current_route_line != last_route_line:
            print_status_message(current_route_line, title="🧭 Routing decision")
            last_route_line = current_route_line

        async def _run() -> str:
            return await _run_with_routing(
                chat_input,
                state.current_verbose,
                state.current_review,
                decision,
                user_intent_message=runtime_user_input,
                session_name=state.current_session,
                retrieval_checkpoint_enabled=state.current_retrieval_checkpoint,
                retrieval_checkpoint_handler=_prompt_retrieval_checkpoint,
            )

        try:
            with _suppress_console_info_logs():
                text = _run_async(_run())
        except Exception as exc:  # noqa: BLE001
            _render_runtime_error(exc)
            _persist_failed_chat_turn(state, user_input, exc)
            continue

        text = persist_reusable_deliverable(
            session_name=state.current_session,
            user_input=runtime_user_input,
            final_output=text,
            registry_dir=load_settings().registry_dir,
        )
        _render_final_output(decision, text)

        state.history.append(("user", user_input))
        state.history.append(("assistant", sanitize_user_visible_text(text)))
        save_history(state.current_session, state.history)
        update_session_memory(state.current_session, state.history)
        update_terminal_title("ready")


if __name__ == "__main__":
    app()
