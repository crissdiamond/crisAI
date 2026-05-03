from __future__ import annotations

from types import SimpleNamespace

import pytest

from crisai.cli.pipeline_engine import WorkflowEngine


class DummyServerContext:
    """Minimal async context manager used to validate lifecycle behavior."""

    def __init__(self, active_servers: list[str], lifecycle_events: list[str]) -> None:
        self._active_servers = active_servers
        self._lifecycle_events = lifecycle_events

    async def __aenter__(self) -> list[str]:
        self._lifecycle_events.append("enter")
        return self._active_servers

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self._lifecycle_events.append("exit")
        return False


@pytest.fixture
def engine_fixture():
    active_servers = ["server:document", "server:workspace"]
    lifecycle_events: list[str] = []
    trace_calls: list[tuple[str, str, dict]] = []
    output_calls: list[tuple[str, str, bool]] = []
    runner_calls: list[tuple[str, str, str]] = []
    build_calls: list[tuple[str, list[str]]] = []
    context_calls: list[tuple[object, list[object], dict]] = []

    class FakeFactory:
        def build_agent(self, spec, servers):
            build_calls.append((spec.id, list(servers)))
            return SimpleNamespace(id=spec.id, servers=list(servers))

    environment = SimpleNamespace(factory=FakeFactory())
    server_specs = {"workspace": object(), "document": object()}
    retrieval_planner_spec = SimpleNamespace(id="retrieval_planner", allowed_servers=["document"])

    def server_context_factory(environment_arg, agent_specs_arg, server_specs_arg):
        context_calls.append((environment_arg, list(agent_specs_arg), server_specs_arg))
        return DummyServerContext(active_servers, lifecycle_events)

    async def stage_runner(agent_id, agent, prompt):
        runner_calls.append((agent_id, agent.id, prompt))
        return f"{agent_id}::{prompt}"

    def trace_writer(stage, content, **kwargs):
        trace_calls.append((stage, content, kwargs))

    def output_printer(agent_id, result, *, verbose):
        output_calls.append((agent_id, result, verbose))

    engine = WorkflowEngine(
        environment=environment,
        server_specs=server_specs,
        server_context_factory=server_context_factory,
        stage_runner=stage_runner,
        trace_writer=trace_writer,
        output_printer=output_printer,
    )

    return SimpleNamespace(
        engine=engine,
        environment=environment,
        server_specs=server_specs,
        retrieval_planner_spec=retrieval_planner_spec,
        active_servers=active_servers,
        lifecycle_events=lifecycle_events,
        trace_calls=trace_calls,
        output_calls=output_calls,
        runner_calls=runner_calls,
        build_calls=build_calls,
        context_calls=context_calls,
    )


@pytest.mark.anyio
async def test_workflow_engine_opens_and_closes_shared_server_context(engine_fixture):
    fixture = engine_fixture

    async with fixture.engine.session([fixture.retrieval_planner_spec]) as workflow:
        result = await workflow.run_stage(
            spec=fixture.retrieval_planner_spec,
            ui_agent_id="retrieval_planner",
            prompt="find context",
            trace_label="RETRIEVAL_PLANNER OUTPUT",
            verbose=False,
        )

    assert result == "retrieval_planner::find context"
    assert fixture.lifecycle_events == ["enter", "exit"]
    assert fixture.context_calls == [
        (
            fixture.environment,
            [fixture.retrieval_planner_spec],
            fixture.server_specs,
        )
    ]
    assert fixture.build_calls == [("retrieval_planner", fixture.active_servers)]
    assert fixture.runner_calls == [("retrieval_planner", "retrieval_planner", "find context")]


@pytest.mark.anyio
async def test_workflow_session_traces_stage_lifecycle_and_prints_output(engine_fixture):
    fixture = engine_fixture

    async with fixture.engine.session([fixture.retrieval_planner_spec]) as workflow:
        result = await workflow.run_stage(
            spec=fixture.retrieval_planner_spec,
            ui_agent_id="retrieval_planner",
            prompt="find context",
            trace_label="RETRIEVAL_PLANNER OUTPUT",
            verbose=True,
        )

    assert result == "retrieval_planner::find context"
    assert fixture.trace_calls == [
        (
            "RETRIEVAL_PLANNER OUTPUT_START",
            "Starting stage for retrieval_planner.",
            {"event_type": "stage_start", "agent_id": "retrieval_planner", "metadata": None},
        ),
        (
            "RETRIEVAL_PLANNER OUTPUT",
            "retrieval_planner::find context",
            {"event_type": "stage_output", "agent_id": "retrieval_planner", "metadata": None},
        ),
        (
            "RETRIEVAL_PLANNER OUTPUT_END",
            "Completed stage for retrieval_planner.",
            {"event_type": "stage_end", "agent_id": "retrieval_planner", "metadata": None},
        ),
    ]
    assert fixture.output_calls == [("retrieval_planner", "retrieval_planner::find context", True)]


@pytest.mark.anyio
async def test_workflow_session_records_workflow_events_and_skipped_stages(engine_fixture):
    fixture = engine_fixture

    async with fixture.engine.session([fixture.retrieval_planner_spec]) as workflow:
        workflow.start_workflow("Starting pipeline workflow.", metadata={"mode": "pipeline"})
        workflow.trace_user_input("hello")
        skipped_message = workflow.skip_stage(
            "REVIEW OUTPUT",
            "Review stage skipped because review is disabled.",
            agent_id="review",
        )
        await workflow.run_stage(
            spec=fixture.retrieval_planner_spec,
            ui_agent_id="retrieval_planner",
            prompt="find context",
            trace_label="RETRIEVAL_PLANNER OUTPUT",
            verbose=False,
            print_output=False,
        )
        workflow.finish_workflow("Pipeline workflow completed.", metadata={"mode": "pipeline"})

    assert skipped_message == "Review stage skipped because review is disabled."
    assert fixture.output_calls == []
    assert fixture.trace_calls[:3] == [
        (
            "WORKFLOW_START",
            "Starting pipeline workflow.",
            {"event_type": "workflow_event", "agent_id": None, "metadata": {"mode": "pipeline"}},
        ),
        (
            "USER INPUT",
            "hello",
            {"event_type": "workflow_input", "agent_id": None, "metadata": None},
        ),
        (
            "REVIEW OUTPUT",
            "Review stage skipped because review is disabled.",
            {"event_type": "stage_skipped", "agent_id": "review", "metadata": None},
        ),
    ]
    assert fixture.trace_calls[-1] == (
        "WORKFLOW_END",
        "Pipeline workflow completed.",
        {"event_type": "workflow_event", "agent_id": None, "metadata": {"mode": "pipeline"}},
    )
