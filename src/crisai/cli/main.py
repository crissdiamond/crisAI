from __future__ import annotations

import asyncio
import collections.abc
import contextlib
import dataclasses
import json
import logging
import os
import pathlib
import re
import ssl
import subprocess
import types
from typing import Any

import prompt_toolkit
import rich.table as rich_table
import typer

from crisai import config as config_module
from crisai import logging_utils as logging_utils_module
from crisai import registry as registry_module
from crisai import registry_validation as validation_module
from crisai import tracing as tracing_module
from crisai.cli import chat_context as chat_context_module
from crisai.cli import display as display_module
from crisai.cli import pipelines as pipelines_module
from crisai.cli import session_store as session_store_module
from crisai.cli import status_views as status_views_module
from crisai.orchestration import exceptions as exceptions_module
from crisai.orchestration import request_contract as request_contract_module
from crisai.orchestration import retrieval_checkpoint as retrieval_checkpoint_module
from crisai.orchestration import router as router_module
from crisai.orchestration import semantic_catalog as catalog_module
from crisai.orchestration import usage_cost as usage_cost_module
from crisai.workspace import artefact_validation as artefact_validation_module
from crisai.workspace import spaces as spaces_module

# Alias definitions for module-level symbols to satisfy import rules while preserving references
Awaitable = collections.abc.Awaitable
contextmanager = contextlib.contextmanager
is_dataclass = dataclasses.is_dataclass
replace = dataclasses.replace
Path = pathlib.Path
SimpleNamespace = types.SimpleNamespace
PromptSession = prompt_toolkit.PromptSession

# cli/chat_context
build_chat_input = chat_context_module.build_chat_input
continuation_intent_message = chat_context_module.continuation_intent_message
normalise_legacy_workspace_paths = chat_context_module.normalise_legacy_workspace_paths

# cli/display
print_final_answer = display_module.print_final_answer
print_final_recommendation = display_module.print_final_recommendation
print_status_message = display_module.print_status_message
update_terminal_title = display_module.update_terminal_title

# cli/session_store
clear_cli_history = session_store_module.clear_cli_history
clear_history = session_store_module.clear_history
load_history = session_store_module.load_history
sanitize_session_name = session_store_module.sanitize_session_name

# cli/status_views
print_agents_table = status_views_module.print_agents_table
print_servers_table = status_views_module.print_servers_table
route_display = status_views_module.route_display

# config
load_settings = config_module.load_settings

# logging_utils
configure_logging = logging_utils_module.configure_logging
get_logger = logging_utils_module.get_logger

# orchestration/exceptions
WorkflowValidationError = exceptions_module.WorkflowValidationError

# orchestration/request_contract
infer_request_contract = request_contract_module.infer_request_contract
render_request_contract_brief = request_contract_module.render_request_contract_brief

# orchestration/retrieval_checkpoint
RetrievalCheckpointDecision = retrieval_checkpoint_module.RetrievalCheckpointDecision
RetrievalCheckpointSnapshot = retrieval_checkpoint_module.RetrievalCheckpointSnapshot

# orchestration/router
RoutingDecision = router_module.RoutingDecision
decide_route = router_module.decide_route

# orchestration/semantic_catalog
load_semantic_catalog = catalog_module.load_semantic_catalog

# registry
Registry = registry_module.Registry

# registry_validation
run_doctor = validation_module.run_doctor

# workspace/artefact_validation
validate_workspace_artefact_paths = artefact_validation_module.validate_workspace_artefact_paths

# workspace/spaces
load_workspace_spaces = spaces_module.load_workspace_spaces

# cli/pipelines
run_peer_pipeline = pipelines_module.run_peer_pipeline
run_pipeline = pipelines_module.run_pipeline
run_single = pipelines_module.run_single

# tracing
TRACE_FILE_NAME = tracing_module.TRACE_FILE_NAME

# orchestration/usage_cost
USAGE_COST_SCHEMA_VERSION = usage_cost_module.USAGE_COST_SCHEMA_VERSION

# rich
Table = rich_table.Table


app = typer.Typer(help="crisAI CLI")
logger = get_logger(__name__)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_UI_WORKSPACE = _REPO_ROOT / "ui"


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


def _request_contract_display(user_input: str, decision: RoutingDecision) -> str:
    """Return the user-facing request contract summary for a routed run."""
    settings = load_settings()
    contract = infer_request_contract(
        user_input,
        current_mode=str(getattr(decision, "mode", "") or "auto"),
        registry_dir=Path(settings.registry_dir),
    )
    return render_request_contract_brief(
        contract,
        selected_mode=str(getattr(decision, "mode", "") or ""),
        selected_agent=str(getattr(decision, "agent", "") or ""),
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
        lines.append("- Run `uv run crisai doctor --models` after changing model providers or agent model_ref values.")

    if result.ok:
        print_status_message("\n".join(lines), title="✅ crisai doctor")
        raise typer.Exit(0)
    print_status_message("\n".join(lines), title="❌ crisai doctor")
    raise typer.Exit(1)


def _parse_spend_events(
    lines: collections.abc.Iterable[str],
    *,
    run_filter: str | None = None,
    last: int = 1,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """Parse JSONL trace lines and group cost events by run_id.

    Args:
        lines: Iterable of raw JSONL lines from a trace file.
        run_filter: When set, return only runs whose run_id equals or starts with this value.
        last: When run_filter is None, return this many most-recent runs (by last-event timestamp).

    Returns:
        Tuple of (selected_runs, warnings). selected_runs maps run_id to a list of
        cost event dicts. warnings contains a message for each malformed line.
    """
    run_groups: dict[str, list[dict[str, Any]]] = {}
    warnings: list[str] = []

    for lineno, raw in enumerate(lines, 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            event: Any = json.loads(raw)
        except json.JSONDecodeError:
            warnings.append(f"Skipping malformed JSONL at line {lineno}.")
            continue
        if not isinstance(event, dict):
            warnings.append(f"Skipping non-object JSONL at line {lineno}.")
            continue
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            continue
        obs = metadata.get("observability")
        if not isinstance(obs, dict):
            continue
        cost = obs.get("cost")
        if not isinstance(cost, dict):
            continue
        if cost.get("schema_version") != USAGE_COST_SCHEMA_VERSION:
            continue
        run_id: str = event.get("run_id") or "(no run_id)"
        if run_id not in run_groups:
            run_groups[run_id] = []
        run_groups[run_id].append(event)

    if run_filter is not None:
        matching = {k: v for k, v in run_groups.items() if k == run_filter or k.startswith(run_filter)}
        return matching, warnings

    sorted_ids = sorted(
        run_groups,
        key=lambda rid: (run_groups[rid][-1].get("timestamp") or ""),
        reverse=True,
    )
    selected = {rid: run_groups[rid] for rid in sorted_ids[: max(1, last)]}
    return selected, warnings


@app.command("spend")
def spend(
    run: str | None = typer.Option(None, "--run", help="Filter to a specific run ID (prefix match)."),
    last: int = typer.Option(1, "--last", help="Number of most recent runs to show."),
) -> None:
    """Summarise token usage and estimated cost from run traces."""
    settings = load_settings()
    trace_file = Path(settings.log_dir) / TRACE_FILE_NAME

    if not trace_file.exists():
        print_status_message(
            f"No trace file found at {trace_file}.\nRun `crisai ask` to generate traces.",
            title="◇ crisai spend",
        )
        raise typer.Exit(0)

    with trace_file.open("r", encoding="utf-8") as fh:
        selected_runs, warnings = _parse_spend_events(fh, run_filter=run, last=last)

    for warning in warnings:
        print_status_message(warning, title="⚠ crisai spend")

    if not selected_runs:
        label = f"run '{run}'" if run else "any run"
        print_status_message(
            f"No cost events found for {label}.\n"
            "Cost tracking requires model pricing configured in registry/models.yaml.",
            title="◇ crisai spend",
        )
        raise typer.Exit(0)

    table = Table(title="crisai spend", show_header=True, header_style="bold bright_blue")
    table.add_column("Run", style="dim", no_wrap=True)
    table.add_column("Stage")
    table.add_column("Agent")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("In", justify="right")
    table.add_column("Out", justify="right")
    table.add_column("Cost USD", justify="right", style="bright_green")

    for run_id, events in selected_runs.items():
        run_short = (run_id[:12] + "…") if len(run_id) > 12 else run_id
        run_total_usd = 0.0
        first_row = True
        for event in events:
            obs = (event.get("metadata") or {}).get("observability") or {}
            cost = obs.get("cost") or {}
            model_meta = obs.get("model") or {}
            pu = obs.get("provider_usage") or {}
            stage = str(event.get("stage") or "")
            agent_id = str(event.get("agent_id") or "")
            provider = str(model_meta.get("provider") or "")
            model_name = str(model_meta.get("model_name") or "")
            input_tokens = int(pu.get("input_tokens") or 0)
            output_tokens = int(pu.get("output_tokens") or 0)
            total_cost_usd = float(cost.get("total_cost_usd") or 0.0)
            run_total_usd += total_cost_usd
            table.add_row(
                run_short if first_row else "",
                stage,
                agent_id,
                provider,
                model_name,
                str(input_tokens),
                str(output_tokens),
                f"${total_cost_usd:.6f}",
            )
            first_row = False
        table.add_section()
        table.add_row(
            "", "", "", "", "[bold]Total[/bold]", "", "", f"[bold]${run_total_usd:.6f}[/bold]"
        )

    display_module.console.print(table)


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
    session: str = typer.Option("default", "--session", "-s", help="Session history to use for continuation context."),
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
    session_name = sanitize_session_name(session)
    history = load_history(session_name)
    runtime_message = normalise_legacy_workspace_paths(message)
    intent_message = continuation_intent_message(
        runtime_message,
        history,
        registry_dir=Path(load_settings().registry_dir),
    )
    agent_message = (
        build_chat_input(runtime_message, history, session_name=session_name)
        if history
        else runtime_message
    )
    explicit_mode = _detect_explicit_mode(intent_message)
    mode_override = "peer" if peer else "pipeline" if pipeline else explicit_mode

    decision = _resolve_route(
        intent_message,
        review_enabled=review,
        mode_override=mode_override,
        agent_override=agent_id if agent_id != "orchestrator" else None,
    )
    decision = _apply_decision_overrides(intent_message, explicit_mode, decision)
    print_status_message(route_display(decision), title="🧭 Routing decision")
    checkpoint_override = _resolve_checkpoint_override(retrieval_checkpoint, no_retrieval_checkpoint)

    async def _run() -> None:
        text = await _run_with_routing(
            agent_message,
            verbose,
            review,
            decision,
            user_intent_message=intent_message,
            session_name=session_name,
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



def _run_ui_workspace_script(script: str) -> None:
    """Run an experimental UI workspace npm script with setup guidance."""
    if not (_UI_WORKSPACE / "package.json").is_file():
        print_status_message(
            "The UI workspace is missing. Reinstall or pull the latest repository state.",
            title="🧪 Experimental UI",
        )
        raise typer.Exit(1)
    if not (_UI_WORKSPACE / "node_modules").is_dir():
        print_status_message(
            "Install UI dependencies first with `npm --prefix ui install`, then retry.",
            title="🧪 Experimental UI",
        )
        raise typer.Exit(1)
    try:
        result = subprocess.run(
            ["npm", "--prefix", str(_UI_WORKSPACE), "run", script],
            check=False,
            env=_ui_workspace_env(script),
        )
    except FileNotFoundError as exc:
        print_status_message(
            "npm is required for experimental React/Ink UI clients.",
            title="🧪 Experimental UI",
        )
        raise typer.Exit(1) from exc
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


def _ui_workspace_env(script: str) -> dict[str, str]:
    """Return environment variables for experimental TypeScript UI clients."""
    env = dict(os.environ)
    if script == "dev:web":
        api_token = env.get("VITE_CRISAI_API_KEY") or env.get("VITE_CRISAI_API_TOKEN")
        api_token = api_token or env.get("CRISAI_API_KEY") or env.get("CRISAI_API_TOKEN")
        runtime_url = env.get("VITE_CRISAI_RUNTIME_URL") or env.get("CRISAI_RUNTIME_URL")
        if api_token:
            env["VITE_CRISAI_API_KEY"] = api_token
            env.setdefault("VITE_CRISAI_API_TOKEN", api_token)
        if runtime_url:
            env["VITE_CRISAI_RUNTIME_URL"] = runtime_url
    return env


@app.command("web-react")
def web_react() -> None:
    """Start the experimental React web client."""
    _run_ui_workspace_script("dev:web")


@app.command("gem-ink")
def gem_ink() -> None:
    """Start the experimental Ink Gem terminal client."""
    _run_ui_workspace_script("dev:gem")


if __name__ == "__main__":
    app()
