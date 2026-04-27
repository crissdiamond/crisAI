from __future__ import annotations

import io
import inspect
import os
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
    build_single_discovery_prompt,
    build_context_retrieval_prompt,
    build_judge_prompt,
    build_peer_final_prompt,
    build_pipeline_final_prompt,
    build_refiner_prompt,
    build_review_prompt,
)
from .pipeline_engine import WorkflowEngine
from .workflow_support import (
    WorkflowEnvironment,
    collect_server_ids,
    ensure_openai_api_key,
    resolve_required_agents,
)

logger = get_logger(__name__)
_DEFAULT_AGENT_MAX_TURNS = 30


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


def _resolve_agent_max_turns() -> int:
    """Return the max turns used for each agent run.

    The OpenAI Agents SDK defaults to 10 turns, which can interrupt longer
    multi-step prompts. This resolver provides a safer default while allowing
    environment overrides.

    Returns:
        A positive integer max-turn value.
    """
    raw_value = os.getenv("CRISAI_AGENT_MAX_TURNS", str(_DEFAULT_AGENT_MAX_TURNS))
    try:
        parsed = int(raw_value)
    except ValueError:
        return _DEFAULT_AGENT_MAX_TURNS
    return parsed if parsed > 0 else _DEFAULT_AGENT_MAX_TURNS


async def _run_agent_silently(agent, prompt: str) -> str:
    """Run an agent while suppressing direct stdout/stderr noise only.

    Logging is handled centrally by the application logging configuration.
    """
    result = None
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = await Runner.run(
                agent,
                prompt,
                max_turns=_resolve_agent_max_turns(),
            )
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
    """Build an agent factory with compatibility for lightweight test doubles."""
    kwargs: dict[str, Any] = {}
    signature = inspect.signature(AgentFactory)
    if model_specs is not None and "model_specs" in signature.parameters:
        kwargs["model_specs"] = model_specs
    if "settings" in signature.parameters:
        kwargs["settings"] = settings
    return AgentFactory(root_dir, **kwargs)



def build_context_synthesizer_prompt(message: str, discovery_text: str) -> str:
    """Build a grounded prompt for the context synthesizer agent.

    The context_synthesizer stage is intentionally separate from both discovery
    and design: discovery identifies candidate source material, while
    context_synthesizer converts that material into an evidence-led brief that a
    downstream design agent can use.

    Args:
        message: Original user request.
        discovery_text: Output produced by the discovery stage.

    Returns:
        A structured prompt that asks the context_synthesizer agent to extract
        relevant information, preserve source references, identify uncertainty,
        and avoid drafting the final solution design.
    """
    return f"""You are the Context Synthesizer agent in the crisAI workflow.

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


def _create_environment(settings, model_specs=None) -> WorkflowEnvironment:
    """Create a workflow environment while preserving older monkeypatch seams."""
    signature = inspect.signature(create_workflow_environment)
    if model_specs is not None and "model_specs" in signature.parameters:
        return create_workflow_environment(settings, model_specs=model_specs)
    return create_workflow_environment(settings)


def _create_workflow_engine(environment: WorkflowEnvironment, server_specs) -> WorkflowEngine:
    """Create a workflow engine wired to the local compatibility helpers.

    Keeping this wiring in ``pipelines.py`` preserves existing monkeypatch
    seams for tests that patch runtime, tracing, or agent execution helpers on
    this module.
    """

    def trace_writer(stage: str, content: str, **kwargs: Any) -> None:
        """Forward structured workflow events through the compatibility layer."""
        _append_trace_entry_compat(environment, stage, content, **kwargs)

    return WorkflowEngine(
        environment=environment,
        server_specs=server_specs,
        server_context_factory=workflow_server_context,
        stage_runner=_run_agent_with_transient_box,
        trace_writer=trace_writer,
        output_printer=print_agent_output,
    )


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
        prompt = build_single_discovery_prompt(message) if agent_id == "discovery" else message
        result = await _run_agent_silently(agent, prompt)
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
    """Run the standard discovery → context_retrieval → context_synthesizer → design pipeline."""
    ensure_openai_api_key(settings)
    environment = _create_environment(settings, model_specs=model_specs)

    logger.info("Running pipeline workflow.", extra={"run_id": _get_run_id(environment), "review": review})

    specs = resolve_required_agents(
        agent_specs,
        ["discovery", "context_retrieval", "context_synthesizer", "design", "review", "orchestrator"],
        mode_name="Pipeline mode",
    )

    engine = _create_workflow_engine(environment, server_specs)

    async with engine.session(specs.values()) as workflow:
        workflow.start_workflow(
            "Starting pipeline workflow.",
            metadata={"mode": "pipeline", "review": review},
        )
        workflow.trace_user_input(message)

        discovery_text = await workflow.run_stage(
            spec=specs["discovery"],
            ui_agent_id="discovery",
            prompt=build_discovery_prompt(message),
            trace_label="DISCOVERY OUTPUT",
            verbose=verbose,
        )

        context_retrieval_text = await workflow.run_stage(
            spec=specs["context_retrieval"],
            ui_agent_id="context_retrieval",
            prompt=build_context_retrieval_prompt(message, discovery_text),
            trace_label="CONTEXT RETRIEVAL OUTPUT",
            verbose=verbose,
        )

        context_text = await workflow.run_stage(
            spec=specs["context_synthesizer"],
            ui_agent_id="context_synthesizer",
            prompt=build_context_synthesizer_prompt(message, context_retrieval_text),
            trace_label="CONTEXT OUTPUT",
            verbose=verbose,
        )

        design_text = await workflow.run_stage(
            spec=specs["design"],
            ui_agent_id="design",
            prompt=build_design_prompt(message, context_text),
            trace_label="DESIGN OUTPUT",
            verbose=verbose,
        )

        if review:
            review_text = await workflow.run_stage(
                spec=specs["review"],
                ui_agent_id="review",
                prompt=build_review_prompt(message, context_text, design_text),
                trace_label="REVIEW OUTPUT",
                verbose=verbose,
            )
        else:
            review_text = workflow.skip_stage(
                "REVIEW OUTPUT",
                "Review stage skipped because review is disabled.",
                agent_id="review",
            )

        final_text = await workflow.run_stage(
            spec=specs["orchestrator"],
            ui_agent_id="orchestrator",
            prompt=build_pipeline_final_prompt(message, context_text, design_text, review_text),
            trace_label="FINAL OUTPUT",
            verbose=verbose,
            print_output=False,
        )
        workflow.finish_workflow("Pipeline workflow completed.", metadata={"mode": "pipeline"})
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
    """Run the peer workflow with optional retrieval and final recommendation."""
    del review  # Unused in peer mode today; kept for API compatibility.
    ensure_openai_api_key(settings)
    environment = _create_environment(settings, model_specs=model_specs)

    logger.info(
        "Running peer workflow.",
        extra={"run_id": _get_run_id(environment), "needs_retrieval": needs_retrieval},
    )

    use_context_retrieval = needs_retrieval and "context_retrieval" in agent_specs

    required_agents = [
        "design_author",
        "design_challenger",
        "design_refiner",
        "judge",
        "orchestrator",
    ]
    if needs_retrieval:
        required_agents.insert(0, "discovery")
    if use_context_retrieval:
        required_agents.insert(1, "context_retrieval")

    specs = resolve_required_agents(
        agent_specs,
        required_agents,
        mode_name="Peer mode",
    )

    engine = _create_workflow_engine(environment, server_specs)

    async with engine.session(specs.values()) as workflow:
        workflow.start_workflow(
            "Starting peer workflow.",
            metadata={"mode": "peer", "needs_retrieval": needs_retrieval},
        )
        workflow.trace_user_input(message)

        discovery_text = ""
        context_retrieval_text = ""
        if needs_retrieval:
            discovery_text = await workflow.run_stage(
                spec=specs["discovery"],
                ui_agent_id="discovery",
                prompt=build_discovery_prompt(message),
                trace_label="DISCOVERY OUTPUT",
                verbose=verbose,
            )
            if use_context_retrieval:
                context_retrieval_text = await workflow.run_stage(
                    spec=specs["context_retrieval"],
                    ui_agent_id="context_retrieval",
                    prompt=build_context_retrieval_prompt(message, discovery_text),
                    trace_label="CONTEXT RETRIEVAL OUTPUT",
                    verbose=verbose,
                )
            else:
                workflow.skip_stage(
                    "CONTEXT RETRIEVAL OUTPUT",
                    "Context retrieval stage skipped in peer mode.",
                    agent_id="context_retrieval",
                )
        else:
            workflow.skip_stage(
                "DISCOVERY OUTPUT",
                "Discovery skipped because this peer task does not require retrieval.",
                agent_id="discovery",
            )
            workflow.skip_stage(
                "CONTEXT RETRIEVAL OUTPUT",
                "Context retrieval skipped because this peer task does not require retrieval.",
                agent_id="context_retrieval",
            )

        discovery_basis = context_retrieval_text or discovery_text or "None."

        author_text = await workflow.run_stage(
            spec=specs["design_author"],
            ui_agent_id="design_author",
            prompt=build_author_prompt(message, discovery_basis),
            trace_label="AUTHOR OUTPUT",
            verbose=verbose,
        )

        challenger_text = await workflow.run_stage(
            spec=specs["design_challenger"],
            ui_agent_id="design_challenger",
            prompt=build_challenger_prompt(message, discovery_basis, author_text),
            trace_label="CHALLENGER OUTPUT",
            verbose=verbose,
        )

        refiner_text = await workflow.run_stage(
            spec=specs["design_refiner"],
            ui_agent_id="design_refiner",
            prompt=build_refiner_prompt(message, discovery_basis, author_text, challenger_text),
            trace_label="REFINER OUTPUT",
            verbose=verbose,
        )

        judge_text = await workflow.run_stage(
            spec=specs["judge"],
            ui_agent_id="judge",
            prompt=build_judge_prompt(message, discovery_basis, challenger_text, refiner_text),
            trace_label="JUDGE OUTPUT",
            verbose=verbose,
        )

        final_text = await workflow.run_stage(
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
            print_output=False,
        )
        workflow.finish_workflow("Peer workflow completed.", metadata={"mode": "peer"})
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
