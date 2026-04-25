from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
import inspect
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

import typer

from crisai.agents.factory import AgentFactory
from crisai.runtime import MultiServerContext, RuntimeManager
from crisai.tracing import TRACE_FILE_NAME, append_trace

from .display import print_agent_output


@dataclass(slots=True)
class WorkflowEnvironment:
    """Shared runtime objects for a workflow execution.

    Attributes:
        root_dir: Repository root used as the runtime working directory.
        runtime: Builds MCP server instances from server specs.
        factory: Builds agent instances from agent specs.
        trace_file: Destination file for workflow stage traces.
        run_id: Correlation id shared across all workflow events.
    """

    root_dir: Path
    runtime: RuntimeManager
    factory: AgentFactory
    trace_file: Path
    run_id: str


def _get_run_id(environment: WorkflowEnvironment | object) -> str | None:
    """Return the workflow run id when available.

    This keeps tracing helpers compatible with older tests that provide
    lightweight SimpleNamespace environments without the newer run_id field.

    Args:
        environment: Workflow environment or test double.

    Returns:
        The workflow run identifier, or None when not available.
    """
    return getattr(environment, "run_id", None)


def _append_trace_compat(path: Path, stage: str, content: str, **kwargs: Any) -> None:
    """Call append_trace with backward-compatible fallback.

    Some existing tests monkeypatch append_trace with the historical
    three-argument signature. Production code uses structured keyword
    arguments. This helper preserves both call styles.

    Args:
        path: Trace file path.
        stage: Logical stage name.
        content: Trace body content.
        **kwargs: Structured tracing fields for the real implementation.
    """
    try:
        append_trace(path, stage, content, **kwargs)
    except TypeError:
        append_trace(path, stage, content)


def ensure_openai_api_key(settings) -> None:
    """Raise when the OpenAI API key is missing."""
    if not settings.openai_api_key:
        raise typer.BadParameter("OPENAI_API_KEY is not set.")


def _build_agent_factory(root_dir: Path, settings, model_specs=None):
    """Build an agent factory with compatibility for lightweight test doubles."""
    kwargs: dict[str, Any] = {}
    signature = inspect.signature(AgentFactory)
    if model_specs is not None and "model_specs" in signature.parameters:
        kwargs["model_specs"] = model_specs
    if "settings" in signature.parameters:
        kwargs["settings"] = settings
    return AgentFactory(root_dir, **kwargs)


def create_workflow_environment(settings, model_specs=None) -> WorkflowEnvironment:
    """Create shared runtime objects for a workflow run.

    Args:
        settings: Loaded application settings.
        model_specs: Optional model catalogue entries loaded from the registry.

    Returns:
        A workflow environment with a provider-aware agent factory.
    """
    root_dir = Path.cwd()
    return WorkflowEnvironment(
        root_dir=root_dir,
        runtime=RuntimeManager(root_dir),
        factory=_build_agent_factory(root_dir, settings, model_specs=model_specs),
        trace_file=settings.log_dir / TRACE_FILE_NAME,
        run_id=str(uuid4()),
    )


def resolve_required_agents(
    agent_specs: Mapping[str, object],
    required_ids: Sequence[str],
    *,
    mode_name: str | None = None,
) -> dict[str, object]:
    """Resolve required agent specs or raise a clear validation error."""
    missing = [agent_id for agent_id in required_ids if agent_id not in agent_specs]
    if missing:
        if mode_name:
            raise typer.BadParameter(
                f"{mode_name} requires these agents in registry/agents.yaml: {', '.join(missing)}"
            )
        raise typer.BadParameter(
            f"Missing required agents in registry/agents.yaml: {', '.join(missing)}"
        )
    return {agent_id: agent_specs[agent_id] for agent_id in required_ids}


def collect_server_ids(agent_specs: Sequence[object]) -> list[str]:
    """Return the sorted unique allowed server ids across the provided agent specs."""
    server_ids: set[str] = set()
    for spec in agent_specs:
        server_ids.update(getattr(spec, "allowed_servers", []))
    return sorted(server_ids)


@asynccontextmanager
async def workflow_server_context(environment: WorkflowEnvironment, agent_specs: Sequence[object], server_specs):
    """Build and open the MCP servers required by the provided agent specs."""
    server_ids = collect_server_ids(agent_specs)
    servers = [
        environment.runtime.build_server(server_specs[server_id])
        for server_id in server_ids
        if server_id in server_specs
    ]
    async with MultiServerContext(servers) as active_servers:
        yield active_servers


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
    """Run a workflow stage, trace it, and optionally print its output."""
    agent = environment.factory.build_agent(spec, active_servers)
    result = await runner(ui_agent_id, agent, prompt)
    _append_trace_compat(
        environment.trace_file,
        trace_label,
        result,
        run_id=_get_run_id(environment),
        agent_id=ui_agent_id,
        event_type="stage_output",
    )
    if print_output:
        print_agent_output(ui_agent_id, result, verbose=verbose)
    return result


def append_trace_entry(
    environment: WorkflowEnvironment,
    stage: str,
    content: str,
    *,
    event_type: str = "workflow_event",
    agent_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Append a structured trace event using the workflow environment trace file."""
    _append_trace_compat(
        environment.trace_file,
        stage,
        content,
        run_id=_get_run_id(environment),
        event_type=event_type,
        agent_id=agent_id,
        metadata=metadata,
    )
