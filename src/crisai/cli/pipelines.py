from __future__ import annotations

import io
import re
from contextlib import asynccontextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from uuid import uuid4

import typer
from agents import Runner

from crisai.agents.factory import AgentFactory
from crisai.logging_utils import get_logger
from crisai.runtime import MultiServerContext, RuntimeManager
from crisai.tracing import TRACE_FILE_NAME, append_trace

from .display import create_agent_live, print_agent_output
from .peer_transcript import PeerRunResult, append_peer_message
from .prompt_builders import (
    build_author_prompt,
    build_challenger_prompt,
    build_design_prompt,
    build_discovery_prompt,
    build_context_retrieval_prompt,
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


def _get_run_id(environment: WorkflowEnvironment | object) -> str | None:
    """Return the workflow run id when available.

    This keeps pipeline logging and tracing compatible with older tests that
    monkeypatch create_workflow_environment with lightweight objects.
    """
    return getattr(environment, "run_id", None)


def _append_trace_compat(path: Path, stage: str, content: str, **kwargs: Any) -> None:
    """Call append_trace with backward-compatible fallback.

    Some existing tests monkeypatch append_trace with the historical
    three-argument signature. Production code uses structured keyword
    arguments. This helper preserves both call styles.
    """
    try:
        append_trace(path, stage, content, **kwargs)
    except TypeError:
        append_trace(path, stage, content)


def _append_trace_entry_compat(
    environment: WorkflowEnvironment,
    stage: str,
    content: str,
    *,
    event_type: str = "workflow_event",
    agent_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Call append_trace_entry with backward-compatible fallback.

    Some existing tests monkeypatch append_trace_entry with the historical
    three-argument signature. This helper allows the richer structured call in
    production while preserving those tests.
    """
    try:
        append_trace_entry(
            environment,
            stage,
            content,
            event_type=event_type,
            agent_id=agent_id,
            metadata=metadata,
        )
    except TypeError:
        append_trace_entry(environment, stage, content)


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



def build_context_prompt(message: str, discovery_text: str) -> str:
    """Build a grounded prompt for the context agent.

    The context stage is intentionally separate from both discovery and design:
    discovery identifies candidate source material, while context converts that
    material into an evidence-led brief that a downstream design agent can use.

    Args:
        message: Original user request.
        discovery_text: Output produced by the discovery stage.

    Returns:
        A structured prompt that asks the context agent to extract relevant
        information, preserve source references, identify uncertainty, and avoid
        drafting the final solution design.
    """
    return f"""You are the Context agent in the crisAI workflow.

Your job is to transform discovered source material into a concise, grounded context brief for a downstream solution design agent.

## Original user request

```text
{message}
```

## Discovery output

```text
{discovery_text}
```

## Task

Create a context brief that helps the design agent draft a solution design using only the information available in the discovery output.

## Rules

- Use only facts supported by the discovery output.
- Preserve file names, paths, document titles, sections, links, citations, or other source references when they are available.
- Separate confirmed facts from assumptions and uncertainties.
- Remove irrelevant findings, duplication, and low-value noise.
- Do not invent missing details.
- Do not draft, recommend, or optimise the solution design.
- If the discovery output is empty, weak, or not relevant, say so clearly and explain what is missing.

## Output format

```markdown
## Context Summary
A short paragraph explaining what relevant context was found and how strong the source basis is.

## Relevant Facts
- Fact: ...
  Source: ...

## Constraints and Dependencies
- Constraint/dependency: ...
  Source: ...

## Assumptions
- Assumption: ...
  Basis: ...

## Gaps and Uncertainties
- Gap/uncertainty: ...
  Why it matters: ...

## Source Notes
- Source: ...
  Relevance: ...
```
"""


def create_workflow_environment(settings, model_specs=None) -> WorkflowEnvironment:
    """Create workflow runtime objects using local module dependencies.

    This wrapper intentionally lives in pipelines.py so existing tests that
    monkeypatch RuntimeManager or AgentFactory on this module continue to work.
    """
    root_dir = Path.cwd()
    return WorkflowEnvironment(
        root_dir=root_dir,
        runtime=RuntimeManager(root_dir),
        factory=_build_agent_factory(root_dir, settings, model_specs=model_specs),
        trace_file=settings.log_dir / TRACE_FILE_NAME,
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
    _append_trace_compat(
        environment.trace_file,
        stage,
        content,
        run_id=_get_run_id(environment),
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
    _append_trace_entry_compat(
        environment,
        f"{trace_label}_START",
        f"Starting stage for {ui_agent_id}.",
        event_type="stage_start",
        agent_id=ui_agent_id,
    )
    result = await runner(ui_agent_id, agent, prompt)
    _append_trace_compat(
        environment.trace_file,
        trace_label,
        result,
        run_id=_get_run_id(environment),
        event_type="stage_output",
        agent_id=ui_agent_id,
    )
    _append_trace_entry_compat(
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

    logger.info("Running single agent request.", extra={"agent_id": agent_id, "run_id": _get_run_id(environment)})

    async with workflow_server_context(environment, [agent_spec], server_specs) as active_servers:
        _append_trace_entry_compat(
            environment,
            "USER_INPUT",
            message,
            event_type="workflow_input",
            metadata={"mode": "single", "agent_id": agent_id},
        )
        agent = environment.factory.build_agent(agent_spec, active_servers)
        result = await _run_agent_silently(agent, message)
        _append_trace_compat(
            environment.trace_file,
            "FINAL_OUTPUT",
            result,
            run_id=_get_run_id(environment),
            event_type="workflow_output",
            agent_id=agent_id,
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
    """Run the standard discovery → context_retrieval → context → design pipeline."""
    ensure_openai_api_key(settings)
    environment = _create_environment(settings, model_specs=model_specs)

    logger.info("Running pipeline workflow.", extra={"run_id": _get_run_id(environment), "review": review})

    specs = resolve_required_agents(
        agent_specs,
        ["discovery", "context_retrieval", "context", "design", "review", "orchestrator"],
        mode_name="Pipeline mode",
    )

    async with workflow_server_context(environment, specs.values(), server_specs) as active_servers:
        _append_trace_entry_compat(
            environment,
            "WORKFLOW_START",
            "Starting pipeline workflow.",
            metadata={"mode": "pipeline", "review": review},
        )
        _append_trace_entry_compat(environment, "USER INPUT", message, event_type="workflow_input")

        discovery_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["discovery"],
            ui_agent_id="discovery",
            prompt=build_discovery_prompt(message),
            trace_label="DISCOVERY OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
        )

        context_retrieval_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["context_retrieval"],
            ui_agent_id="context_retrieval",
            prompt=build_context_retrieval_prompt(message, discovery_text),
            trace_label="CONTEXT RETRIEVAL OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
        )

        context_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["context"],
            ui_agent_id="context",
            prompt=build_context_prompt(message, context_retrieval_text),
            trace_label="CONTEXT OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
        )

        design_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["design"],
            ui_agent_id="design",
            prompt=build_design_prompt(message, context_text),
            trace_label="DESIGN OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
        )

        if review:
            review_text = await run_traced_stage(
                environment=environment,
                active_servers=active_servers,
                spec=specs["review"],
                ui_agent_id="review",
                prompt=build_review_prompt(message, context_text, design_text),
                trace_label="REVIEW OUTPUT",
                verbose=verbose,
                runner=_run_agent_with_transient_box,
            )
        else:
            review_text = "Review stage skipped because review is disabled."
            _append_trace_entry_compat(
                environment,
                "REVIEW OUTPUT",
                review_text,
                event_type="stage_skipped",
                agent_id="review",
            )

        final_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["orchestrator"],
            ui_agent_id="orchestrator",
            prompt=build_pipeline_final_prompt(message, context_text, design_text, review_text),
            trace_label="FINAL OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
            print_output=False,
        )
        _append_trace_entry_compat(environment, "WORKFLOW_END", "Pipeline workflow completed.", metadata={"mode": "pipeline"})
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
        extra={"run_id": _get_run_id(environment), "needs_retrieval": needs_retrieval},
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
        _append_trace_entry_compat(
            environment,
            "WORKFLOW_START",
            "Starting peer workflow.",
            metadata={"mode": "peer", "needs_retrieval": needs_retrieval},
        )
        _append_trace_entry_compat(environment, "USER INPUT", message, event_type="workflow_input")

        discovery_text = ""
        if needs_retrieval:
            discovery_text = await run_traced_stage(
                environment=environment,
                active_servers=active_servers,
                spec=specs["discovery"],
                ui_agent_id="discovery",
                prompt=build_discovery_prompt(message),
                trace_label="DISCOVERY OUTPUT",
                verbose=verbose,
                runner=_run_agent_with_transient_box,
            )
        else:
            _append_trace_entry_compat(
                environment,
                "DISCOVERY OUTPUT",
                "Discovery skipped because this peer task does not require retrieval.",
                event_type="stage_skipped",
                agent_id="discovery",
            )

        discovery_basis = discovery_text or "None."

        author_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["design_author"],
            ui_agent_id="design_author",
            prompt=build_author_prompt(message, discovery_basis),
            trace_label="AUTHOR OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
        )

        challenger_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["design_challenger"],
            ui_agent_id="design_challenger",
            prompt=build_challenger_prompt(message, discovery_basis, author_text),
            trace_label="CHALLENGER OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
        )

        refiner_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["design_refiner"],
            ui_agent_id="design_refiner",
            prompt=build_refiner_prompt(message, discovery_basis, author_text, challenger_text),
            trace_label="REFINER OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
        )

        judge_text = await run_traced_stage(
            environment=environment,
            active_servers=active_servers,
            spec=specs["judge"],
            ui_agent_id="judge",
            prompt=build_judge_prompt(message, discovery_basis, challenger_text, refiner_text),
            trace_label="JUDGE OUTPUT",
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
            trace_label="FINAL OUTPUT",
            verbose=verbose,
            runner=_run_agent_with_transient_box,
            print_output=False,
        )
        _append_trace_entry_compat(environment, "WORKFLOW_END", "Peer workflow completed.", metadata={"mode": "peer"})
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
