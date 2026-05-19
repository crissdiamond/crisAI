"""Workflow engine for shared multi-agent pipeline lifecycle management."""
from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from .pipeline_display import (
    reset_stage_observability_agent_id,
    reset_stage_observability_callback,
    set_stage_observability_agent_id,
    set_stage_observability_callback,
)
from .workflow_support import WorkflowEnvironment

StageRunner = Callable[[str, Any, str], Awaitable[str]]
TraceWriter = Callable[..., None]
OutputPrinter = Callable[..., None]
ServerContextFactory = Callable[..., Any]
StageOutputProcessor = Callable[[str], tuple[str, dict[str, Any] | None]]
_DEFAULT_STAGE_TIMEOUT_SECONDS = 300.0
_OBSERVABILITY_SCHEMA_VERSION = "ui_stage_observability_v1"


def _resolve_stage_timeout_seconds() -> float:
    """Return the maximum duration allowed for one agent stage."""
    raw = os.getenv("CRISAI_AGENT_STAGE_TIMEOUT_SECONDS", str(_DEFAULT_STAGE_TIMEOUT_SECONDS))
    try:
        parsed = float(raw)
    except ValueError:
        return _DEFAULT_STAGE_TIMEOUT_SECONDS
    return parsed if parsed > 0 else _DEFAULT_STAGE_TIMEOUT_SECONDS


class WorkflowSession:
    """Execute traced workflow stages against a shared MCP server context.

    The session intentionally owns only execution mechanics that are common
    across workflows: structured tracing, agent construction, stage execution,
    and optional UI rendering. Pipeline-specific prompt wiring remains in
    ``pipelines.py``.
    """

    def __init__(
        self,
        *,
        environment: WorkflowEnvironment,
        active_servers: list | Mapping[str, object],
        stage_runner: StageRunner,
        trace_writer: TraceWriter,
        output_printer: OutputPrinter,
    ) -> None:
        """Initialise a workflow session.

        Args:
            environment: Shared workflow runtime objects.
            active_servers: MCP servers opened for this workflow run.
            stage_runner: Callable used to execute an agent for a prompt.
            trace_writer: Callable used to emit structured workflow events.
            output_printer: Callable used to render non-final stage output.
        """
        self._environment = environment
        self._active_servers = active_servers
        self._stage_runner = stage_runner
        self._trace_writer = trace_writer
        self._output_printer = output_printer

    def trace_event(
        self,
        stage: str,
        content: str,
        *,
        event_type: str = "workflow_event",
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Emit a structured workflow event.

        Args:
            stage: Logical stage label.
            content: Event payload.
            event_type: Semantic event category.
            agent_id: Optional agent responsible for the event.
            metadata: Optional structured metadata payload.
        """
        self._trace_writer(
            stage,
            content,
            event_type=event_type,
            agent_id=agent_id,
            metadata=metadata,
        )

    def start_workflow(self, content: str, *, metadata: dict[str, Any] | None = None) -> None:
        """Trace the start of a workflow run."""
        self.trace_event("WORKFLOW_START", content, metadata=metadata)

    def trace_user_input(self, content: str, *, metadata: dict[str, Any] | None = None) -> None:
        """Trace the user input that initiated the workflow."""
        self.trace_event("USER INPUT", content, event_type="workflow_input", metadata=metadata)

    def finish_workflow(self, content: str, *, metadata: dict[str, Any] | None = None) -> None:
        """Trace the successful completion of a workflow run."""
        self.trace_event("WORKFLOW_END", content, metadata=metadata)

    def skip_stage(self, trace_label: str, content: str, *, agent_id: str | None = None) -> str:
        """Trace a skipped stage and return the recorded content.

        Args:
            trace_label: Label of the skipped stage.
            content: Human-readable reason for the skip.
            agent_id: Optional agent identifier for the skipped stage.

        Returns:
            The provided ``content`` to simplify caller control flow.
        """
        self.trace_event(
            trace_label,
            content,
            event_type="stage_skipped",
            agent_id=agent_id,
        )
        return content

    async def run_stage(
        self,
        *,
        spec: Any,
        ui_agent_id: str,
        prompt: str,
        trace_label: str,
        verbose: bool,
        print_output: bool = True,
        output_processor: StageOutputProcessor | None = None,
    ) -> str:
        """Build, run, trace, and optionally render a workflow stage.

        Args:
            spec: Agent spec to build.
            ui_agent_id: Stable agent identifier used by the UI and tracing.
            prompt: Fully rendered prompt for this stage.
            trace_label: Output label written to the trace log.
            verbose: Whether stage output should be printed verbosely.
            print_output: Whether to render the stage output to the console.
            output_processor: Optional sanitizer/extractor for trace and UI text.

        Returns:
            The final text emitted by the agent.
        """
        agent = self._environment.factory.build_agent(spec, self._servers_for_spec(spec))
        self.trace_event(
            f"{trace_label}_START",
            f"Starting stage for {ui_agent_id}.",
            event_type="stage_start",
            agent_id=ui_agent_id,
        )
        observability_events: list[tuple[str, dict[str, object]]] = []

        def _record_observability(agent_id: str, event_type: str, metadata: dict[str, object]) -> None:
            if agent_id == ui_agent_id and metadata:
                observability_events.append((event_type, metadata))

        observability_agent_token = set_stage_observability_agent_id(ui_agent_id)
        observability_callback_token = set_stage_observability_callback(_record_observability)
        timeout_seconds = _resolve_stage_timeout_seconds()
        started_at = _utc_now_iso()
        started_monotonic = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                self._stage_runner(ui_agent_id, agent, prompt),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            message = (
                f"Stage {ui_agent_id} timed out after {timeout_seconds:g}s. "
                "Set CRISAI_AGENT_STAGE_TIMEOUT_SECONDS to tune this limit."
            )
            self.trace_event(
                f"{trace_label}_ERROR",
                message,
                event_type="stage_error",
                agent_id=ui_agent_id,
                metadata=_merge_stage_observability_metadata(
                    {"timeout_seconds": timeout_seconds},
                    observability_events,
                    execution_time=_execution_time_metadata(started_at, started_monotonic),
                ),
            )
            raise TimeoutError(message) from None
        except Exception as exc:
            message = f"Stage {ui_agent_id} failed: {type(exc).__name__}: {exc}"
            self.trace_event(
                f"{trace_label}_ERROR",
                message,
                event_type="stage_error",
                agent_id=ui_agent_id,
                metadata=_merge_stage_observability_metadata(
                    {"error_type": type(exc).__name__},
                    observability_events,
                    execution_time=_execution_time_metadata(started_at, started_monotonic),
                ),
            )
            raise
        finally:
            reset_stage_observability_callback(observability_callback_token)
            reset_stage_observability_agent_id(observability_agent_token)
        if not str(result or "").strip():
            message = (
                f"Stage {ui_agent_id} returned empty output. "
                "This stage is required to produce a handoff or answer."
            )
            self.trace_event(
                f"{trace_label}_ERROR",
                message,
                event_type="stage_error",
                agent_id=ui_agent_id,
                metadata=_merge_stage_observability_metadata(
                    {"output_length": 0},
                    observability_events,
                    execution_time=_execution_time_metadata(started_at, started_monotonic),
                ),
            )
            raise RuntimeError(message)
        trace_content = result
        trace_metadata: dict[str, Any] | None = None
        if output_processor is not None:
            trace_content, trace_metadata = output_processor(result)
        trace_metadata = _merge_stage_observability_metadata(
            trace_metadata,
            observability_events,
            execution_time=_execution_time_metadata(started_at, started_monotonic),
        )
        self.trace_event(
            trace_label,
            trace_content,
            event_type="stage_output",
            agent_id=ui_agent_id,
            metadata=trace_metadata,
        )
        self.trace_event(
            f"{trace_label}_END",
            f"Completed stage for {ui_agent_id}.",
            event_type="stage_end",
            agent_id=ui_agent_id,
        )
        if print_output:
            self._output_printer(ui_agent_id, trace_content, verbose=verbose)
        return result

    def _servers_for_spec(self, spec: Any) -> list:
        """Return only the active MCP servers configured for this agent."""
        if not isinstance(self._active_servers, Mapping):
            return list(self._active_servers)
        allowed = list(getattr(spec, "allowed_servers", []) or [])
        return [self._active_servers[server_id] for server_id in allowed if server_id in self._active_servers]


class WorkflowEngine:
    """Manage the shared workflow lifecycle used by pipeline and peer modes."""

    def __init__(
        self,
        *,
        environment: WorkflowEnvironment,
        server_specs,
        server_context_factory: ServerContextFactory,
        stage_runner: StageRunner,
        trace_writer: TraceWriter,
        output_printer: OutputPrinter,
    ) -> None:
        """Initialise the workflow engine.

        Args:
            environment: Shared workflow runtime objects.
            server_specs: Registry server specs indexed by id.
            server_context_factory: Factory that opens the required MCP servers.
            stage_runner: Callable used to execute an agent for a prompt.
            trace_writer: Callable used to emit structured workflow events.
            output_printer: Callable used to render non-final stage output.
        """
        self._environment = environment
        self._server_specs = server_specs
        self._server_context_factory = server_context_factory
        self._stage_runner = stage_runner
        self._trace_writer = trace_writer
        self._output_printer = output_printer

    @asynccontextmanager
    async def session(self, agent_specs: Iterable[object]) -> AsyncIterator[WorkflowSession]:
        """Open the shared MCP context required for the provided agent specs.

        Args:
            agent_specs: Agent specs participating in the workflow run.

        Yields:
            A ``WorkflowSession`` bound to the active server set.
        """
        async with self._server_context_factory(
            self._environment,
            agent_specs,
            self._server_specs,
        ) as active_servers:
            yield WorkflowSession(
                environment=self._environment,
                active_servers=active_servers,
                stage_runner=self._stage_runner,
                trace_writer=self._trace_writer,
                output_printer=self._output_printer,
            )


def _merge_stage_observability_metadata(
    metadata: dict[str, Any] | None,
    observability_events: list[tuple[str, dict[str, object]]],
    *,
    execution_time: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Attach trace-safe stage observability to existing stage metadata."""
    if not observability_events and execution_time is None:
        return metadata
    merged: dict[str, Any] = dict(metadata or {})
    existing_observability = merged.get("observability")
    observability: dict[str, Any] = (
        dict(existing_observability) if isinstance(existing_observability, dict) else {}
    )
    observability["schema_version"] = _OBSERVABILITY_SCHEMA_VERSION
    for event_type, payload in observability_events:
        if event_type in {"streaming_fallback", "provider_usage"}:
            observability.update(payload)
        else:
            observability[event_type] = payload
    if execution_time is not None:
        observability["execution_time"] = execution_time
    merged["observability"] = observability
    return merged


def _utc_now_iso() -> str:
    """Return a UTC timestamp for stage observability metadata."""
    return datetime.now(timezone.utc).isoformat()


def _execution_time_metadata(started_at: str, started_monotonic: float) -> dict[str, Any]:
    """Return wall-clock timing metadata for one stage execution."""
    ended_at = _utc_now_iso()
    duration_ms = max(0, round((time.perf_counter() - started_monotonic) * 1000))
    return {
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": duration_ms,
    }
