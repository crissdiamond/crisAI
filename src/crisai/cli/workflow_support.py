from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import typer

from crisai.agents import factory as factory_module
from crisai import runtime as runtime_module
from crisai import tracing as tracing_module

from crisai.cli import display as display_module

AgentFactory = factory_module.AgentFactory
MultiServerContext = runtime_module.MultiServerContext
RuntimeManager = runtime_module.RuntimeManager
TRACE_FILE_NAME = tracing_module.TRACE_FILE_NAME
append_trace = tracing_module.append_trace
print_agent_output = display_module.print_agent_output


@dataclass(slots=True)
class WorkflowEnvironment:
    """Shared runtime objects for a workflow execution.

    Attributes:
        root_dir: Repository root used as the runtime working directory.
        runtime: Builds MCP server instances from server specs.
        factory: Builds agent instances from agent specs.
        trace_file: Destination file for workflow stage traces.
        run_id: Correlation id shared across all workflow events.
        mcp_env_overrides: Environment values passed to stdio MCP servers.
    """

    root_dir: Path
    runtime: RuntimeManager
    factory: AgentFactory
    trace_file: Path
    run_id: str
    mcp_env_overrides: dict[str, str] = field(default_factory=dict)


def _get_run_id(environment: WorkflowEnvironment | object) -> str | None:
    """Return the workflow run id when available."""
    return getattr(environment, "run_id", None)


def ensure_openai_api_key(settings) -> None:
    """Raise when the OpenAI API key is missing."""
    if not settings.openai_api_key:
        raise typer.BadParameter("OPENAI_API_KEY is not set.")


def _build_agent_factory(root_dir: Path, settings, model_specs=None):
    """Build a provider-aware agent factory."""
    return AgentFactory(root_dir, model_specs=model_specs, settings=settings)


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
    env_overrides = getattr(environment, "mcp_env_overrides", {}) or {}
    servers = [
        environment.runtime.build_server(server_specs[server_id], env_overrides=env_overrides)
        if env_overrides
        else environment.runtime.build_server(server_specs[server_id])
        for server_id in server_ids
        if server_id in server_specs
    ]
    async with MultiServerContext(servers) as active_servers:
        yield {
            server_id: server
            for server_id, server in zip((server_id for server_id in server_ids if server_id in server_specs), active_servers, strict=False)
        }


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
    agent_servers = (
        [active_servers[server_id] for server_id in getattr(spec, "allowed_servers", []) if server_id in active_servers]
        if isinstance(active_servers, dict)
        else active_servers
    )
    agent = environment.factory.build_agent(spec, agent_servers)
    result = await runner(ui_agent_id, agent, prompt)
    append_trace(
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
    append_trace(
        environment.trace_file,
        stage,
        content,
        run_id=_get_run_id(environment),
        event_type=event_type,
        agent_id=agent_id,
        metadata=metadata,
    )
