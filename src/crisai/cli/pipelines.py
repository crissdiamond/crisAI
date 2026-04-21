from __future__ import annotations

import io
import re
from contextlib import asynccontextmanager, redirect_stderr, redirect_stdout
from pathlib import Path

import typer
from agents import Runner
from uuid import uuid4

from crisai.agents.factory import AgentFactory
from crisai.logging_utils import get_logger
from crisai.runtime import MultiServerContext, RuntimeManager
from crisai.tracing import append_trace

from .display import create_agent_live, print_agent_output
from .peer_transcript import PeerRunResult, append_peer_message
from .prompt_builders import (
    build_author_prompt,
    build_challenger_prompt,
    build_design_prompt,
    build_discovery_prompt,
    build_judge_prompt,
    build_peer_final_prompt,
    build_pipeline_final_prompt,
    build_refiner_prompt,
    build_review_prompt,
)
from .workflow_support import (
    WorkflowEnvironment,
    collect_server_ids,
    ensure_openai_api_key,
    resolve_required_agents,
)

logger = get_logger(__name__)


async def _run_agent_silently(agent, prompt: str) -> str:
    """Run an agent while suppressing direct stdout/stderr noise only.

    Logging is handled centrally by the application logging configuration.
    """
    result = None
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = await Runner.run(agent, prompt)
    except Exception:
        logger.exception("Agent execution failed.")
        raise
    return str(result.final_output)


async def _run_agent_with_transient_box(agent_id: str, agent, prompt: str) -> str:
    """Run an agent and render its transient progress box."""
    live = create_agent_live(agent_id)
    with live:
        result = await _run_agent_silently(agent, prompt)
    return result



def _build_agent_factory(root_dir: Path, settings, model_specs=None):
    """Build an agent factory with graceful fallback for older test doubles."""
    if model_specs:
        try:
            return AgentFactory(root_dir, model_specs=model_specs, settings=settings)
        except TypeError:
            pass

    try:
        return AgentFactory(root_dir, settings=settings)
    except TypeError:
        return AgentFactory(root_dir)



def create_workflow_environment(settings, model_specs=None) -> WorkflowEnvironment:
    """Create workflow runtime objects using local module dependencies.

    This wrapper intentionally lives in pipelines.py so existing tests that
    monkeypatch RuntimeManager or AgentFactory on this module continue to work.

    Args:
        settings: Loaded application settings.
        model_specs: Optional model catalogue entries loaded from the registry.

    Returns:
        Workflow environment with provider-aware agent factory support.
    """
    root_dir = Path.cwd()
    return WorkflowEnvironment(
        root_dir=root_dir,
        runtime=RuntimeManager(root_dir),
        factory=_build_agent_factory(root_dir, settings, model_specs=model_specs),
        trace_file=settings.log_dir / "agent_trace.jsonl",
        run_id=uuid4().hex,
    )


@asynccontextmanager
async def workflow_server_context(environment: WorkflowEnvironment, agent_specs, server_specs):
    """Build and open the required MCP server context for a workflow."""
    server_ids = collect_server_ids(agent_specs)
    servers = [
        environment.runtime.build_server(server_specs[server_id])
        for server_id in server_ids
        if server_id in server_specs
    ]
    async with MultiServerContext(servers) as active_servers:
        yield active_servers



def append_trace_entry(
    environment: WorkflowEnvironment,
    stage: str,
    content: str,
    *,
    event_type: str = "workflow_event",
    agent_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Append a structured trace entry.

    This wrapper keeps append_trace patchable from tests through the pipelines
    module surface.
    """
    append_trace(
        environment.trace_file,
        stage,
        content,
        run_id=environment.run_id,
        event_type=event_type,
        agent_id=agent_id,
        metadata=metadata,
    )


async def run_traced_stage(
    *,
    environment: WorkflowEnvironment,
    active_servers: list,
    spec,
    ui_agent_id: str,
    prompt: str,
    trace_label: str,
    verbose: bool,
    runner,
    print_output: bool = True,
) -> str:
    """Run a workflow stage, trace it, and optionally print stage output."""
    agent = environment.factory.build_agent(spec, active_servers)
    append_trace_entry(
        environment,
        f"{trace_label}_START",
        f"Starting stage for {ui_agent_id}.",
        event_type="stage_start",
        agent_id=ui_agent_id,
    )
    result = await runner(ui_agent_id, agent, prompt)
    append_trace(
        environment.trace_file,
        trace_label,
        result,
        run_id=environment.run_id,
        event_type="stage_output",
        agent_id=ui_agent_id,
    )
    append_trace_entry(
        environment,
        f"{trace_label}_END",
        f"Completed stage for {ui_agent_id}.",
        event_type="stage_end",
        agent_id=ui_agent_id,
    )
    if print_output:
        print_agent_output(ui_agent_id, result, verbose=verbose)
    return result


_FINAL_RECOMMENDATION_PATTERNS = [
    r"(?:^|\n)(#+\s*Final recommendation\s*\n+.*)$",
    r"(?:^|\n)(\*\*Final recommendation\*\*\s*\n+.*)$",
    r"(?:^|\n)(Final recommendation\s*\n+.*)$",
]



def _extract_final_recommendation(text: str) -> str:
    stripped = text.strip()
    for pattern in _FINAL_RECOMMENDATION_PATTERNS:
        match = re.search(pattern, stripped, flags=re.IGNORECASE | re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            if extracted:
                return extracted
    return stripped



def build_agent_servers(runtime, agent_spec, server_specs):
    servers = []
    for server_id in agent_spec.allowed_servers:
        spec = server_specs.get(server_id)
        if spec:
            servers.append(runtime.build_server(spec))
    return servers



def _create_environment(settings, model_specs=None) -> WorkflowEnvironment:
    """Create a workflow environment while preserving older monkeypatch seams."""
    if model_specs is not None:
        try:
            return create_workflow_environment(settings, model_specs=model_specs)
        except TypeError:
            pass
    return create_workflow_environment(settings)


async def run_single(message: str, agent_id: str, *, settings, server_specs, agent_specs, model_specs=None) -> str:
    """Run a single agent directly."""
    ensure_openai_api_key(settings)

    if agent_id not in agent_specs:
        raise typer.BadParameter(f"Unknown agent_id: {agent_id}")

    environment = _create_environment(settings, model_specs=model_specs)
    agent_spec = agent_specs[agent_id]

    logger.info("Running single agent request.", extra={"agent_id": agent_id, "run_id": environment.run_id})

    async with workflow_server_context(environment, [agent_spec], server_specs) as active_servers:
        append_trace_entry(
            environment,
            "USER_INPUT",
            message,
            event_type="workflow_input",
            metadata={"mode": "single", "agent_id": agent_id},
        )
        agent = environment.factory.build_agent(agent_spec, active_servers)
        result = await _run_agent_silently(agent, message)
        append_trace_entry(
            environment,
            "FINAL_OUTPUT",
            result,
            event_type="workflow_output",
            agent_id=agent_id,
            metadata={"mode": "single"},
        )
        return result


async def run_pipeline(
    message: str,
    verbose: bool,
    review: bool,
    *,
    settings,
    server_specs,
    agent_specs,
    model_specs=None,
) -> str:
    """Run the standard discovery → design → review → final pipeline."""
    ensure_openai_api_key(settings)
    environment = _create_environment(settings, model_specs=model_specs)

    logger.info("Running pipeline workflow.", extra={"run_id": environment.run_id, "review": review})

    specs = resolve_required_agents(
        agent_specs,
        ["discovery", "design", "review", "orchestrator"],
        mode_name="Pipeline mode",
    )

    async with workflow_server_context(environment, specs.values(), server_specs) as active_servers:
        append_trace_entry(
            environment,
            "WORKFLOW_START",
            "Starting pipeline workflow.",
            metadata={"mode": "pipeline", "review": review},
        )
        append_trace_entry(environment, "USER_INPUT", message, event_type="workflow_input")

        discovery_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["discovery"],
            ui_agent_id="discovery",
            prompt=build_discovery_prompt(message),
            trace_label="DISCOVERY_OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
        )

        design_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["design"],
            ui_agent_id="design",
            prompt=build_design_prompt(message, discovery_text),
            trace_label="DESIGN_OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
        )

        if review:
            review_text = await run_traced_stage(
                environment=environment,
                active_servers=active_servers,
                spec=specs["review"],
                ui_agent_id="review",
                prompt=build_review_prompt(message, discovery_text, design_text),
                trace_label="REVIEW_OUTPUT",
                verbose=verbose,
                runner=_run_agent_with_transient_box,
            )
        else:
            review_text = "Review stage skipped because review is disabled."
            append_trace_entry(
                environment,
                "REVIEW_OUTPUT",
                review_text,
                event_type="stage_skipped",
                metadata={"reason": "review_disabled"},
            )

        final_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["orchestrator"],
            ui_agent_id="orchestrator",
            prompt=build_pipeline_final_prompt(message, discovery_text, design_text, review_text),
            trace_label="FINAL_OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
            print_output=False,
        )
        append_trace_entry(environment, "WORKFLOW_END", "Completed pipeline workflow.")
        return final_text


async def run_peer_pipeline(
    message: str,
    verbose: bool,
    review: bool,
    *,
    settings,
    server_specs,
    agent_specs,
    model_specs=None,
    needs_retrieval: bool = True,
) -> str:
    """Run the peer workflow with optional discovery and final recommendation."""
    del review  # Unused in peer mode today; kept for API compatibility.
    ensure_openai_api_key(settings)
    environment = _create_environment(settings, model_specs=model_specs)

    logger.info(
        "Running peer workflow.",
        extra={"run_id": environment.run_id, "needs_retrieval": needs_retrieval},
    )

    required_agents = [
        "design_author",
        "design_challenger",
        "design_refiner",
        "judge",
        "orchestrator",
    ]
    if needs_retrieval:
        required_agents.insert(0, "discovery")

    specs = resolve_required_agents(
        agent_specs,
        required_agents,
        mode_name="Peer mode",
    )

    async with workflow_server_context(environment, specs.values(), server_specs) as active_servers:
        append_trace_entry(
            environment,
            "WORKFLOW_START",
            "Starting peer workflow.",
            metadata={"mode": "peer", "needs_retrieval": needs_retrieval},
        )
        append_trace_entry(environment, "USER_INPUT", message, event_type="workflow_input")

        discovery_text = ""
        if needs_retrieval:
            discovery_text = await run_traced_stage(
                environment=environment,
                active_servers=active_servers,
                spec=specs["discovery"],
                ui_agent_id="discovery",
                prompt=build_discovery_prompt(message),
                trace_label="DISCOVERY_OUTPUT",
                verbose=verbose,
                runner=_run_agent_with_transient_box,
            )
        else:
            append_trace_entry(
                environment,
                "DISCOVERY_OUTPUT",
                "Discovery skipped because this peer task does not require retrieval.",
                event_type="stage_skipped",
                metadata={"reason": "retrieval_not_required"},
            )

        discovery_basis = discovery_text or "None."

        author_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["design_author"],
            ui_agent_id="design_author",
            prompt=build_author_prompt(message, discovery_basis),
            trace_label="AUTHOR_OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
        )

        challenger_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["design_challenger"],
            ui_agent_id="design_challenger",
            prompt=build_challenger_prompt(message, discovery_basis, author_text),
            trace_label="CHALLENGER_OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
        )

        refiner_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["design_refiner"],
            ui_agent_id="design_refiner",
            prompt=build_refiner_prompt(message, discovery_basis, author_text, challenger_text),
            trace_label="REFINER_OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
        )

        judge_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["judge"],
            ui_agent_id="judge",
            prompt=build_judge_prompt(message, discovery_basis, challenger_text, refiner_text),
            trace_label="JUDGE_OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
        )

        final_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["orchestrator"],
            ui_agent_id="orchestrator",
            prompt=build_peer_final_prompt(
                message,
                discovery_basis,
                author_text,
                challenger_text,
                refiner_text,
                judge_text,
            ),
            trace_label="FINAL_OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
            print_output=False,
        )
        append_trace_entry(environment, "WORKFLOW_END", "Completed peer workflow.")
        return _extract_final_recommendation(final_text)



def build_peer_run_result(
    discovery_text: str,
    author_text: str,
    challenger_text: str,
    refiner_text: str,
    judge_text: str,
    final_text: str,
) -> PeerRunResult:
    transcript = []
    append_peer_message(transcript, "discovery", discovery_text)
    append_peer_message(transcript, "design_author", author_text)
    append_peer_message(transcript, "design_challenger", challenger_text)
    append_peer_message(transcript, "design_refiner", refiner_text)
    append_peer_message(transcript, "judge", judge_text)
    append_peer_message(transcript, "orchestrator", final_text)
    return PeerRunResult(final_text=final_text, transcript=transcript)
