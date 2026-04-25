"""Workflow engine for shared multi-agent pipeline lifecycle management."""
from __future__ import annotations

from collections.abc import Iterable
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable

from .workflow_support import WorkflowEnvironment

StageRunner = Callable[[str, Any, str], Awaitable[str]]
TraceWriter = Callable[..., None]
OutputPrinter = Callable[..., None]
ServerContextFactory = Callable[..., Any]


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
        active_servers: list,
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
    ) -> str:
        """Build, run, trace, and optionally render a workflow stage.

        Args:
            spec: Agent spec to build.
            ui_agent_id: Stable agent identifier used by the UI and tracing.
            prompt: Fully rendered prompt for this stage.
            trace_label: Output label written to the trace log.
            verbose: Whether stage output should be printed verbosely.
            print_output: Whether to render the stage output to the console.

        Returns:
            The final text emitted by the agent.
        """
        agent = self._environment.factory.build_agent(spec, self._active_servers)
        self.trace_event(
            f"{trace_label}_START",
            f"Starting stage for {ui_agent_id}.",
            event_type="stage_start",
            agent_id=ui_agent_id,
        )
        result = await self._stage_runner(ui_agent_id, agent, prompt)
        self.trace_event(
            trace_label,
            result,
            event_type="stage_output",
            agent_id=ui_agent_id,
        )
        self.trace_event(
            f"{trace_label}_END",
            f"Completed stage for {ui_agent_id}.",
            event_type="stage_end",
            agent_id=ui_agent_id,
        )
        if print_output:
            self._output_printer(ui_agent_id, result, verbose=verbose)
        return result


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

