from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest

from crisai.cli import pipeline_display
from crisai.cli.pipeline_engine import WorkflowEngine, _resolve_stage_timeout_seconds


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


def test_resolve_stage_timeout_from_env(monkeypatch):
    monkeypatch.setenv("CRISAI_AGENT_STAGE_TIMEOUT_SECONDS", "12.5")

    assert _resolve_stage_timeout_seconds() == 12.5


def test_resolve_stage_timeout_falls_back_for_invalid_env(monkeypatch):
    monkeypatch.setenv("CRISAI_AGENT_STAGE_TIMEOUT_SECONDS", "invalid")

    assert _resolve_stage_timeout_seconds() == 300.0


def _assert_execution_time(observability: dict) -> None:
    assert observability["schema_version"] == "ui_stage_observability_v1"
    execution_time = observability["execution_time"]
    assert execution_time["started_at"]
    assert execution_time["ended_at"]
    assert isinstance(execution_time["duration_ms"], int)
    assert execution_time["duration_ms"] >= 0


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
async def test_workflow_session_filters_servers_per_agent(engine_fixture):
    fixture = engine_fixture
    active_servers = {
        "document": "server:document",
        "workspace": "server:workspace",
    }

    def server_context_factory(environment_arg, agent_specs_arg, server_specs_arg):
        fixture.context_calls.append((environment_arg, list(agent_specs_arg), server_specs_arg))
        return DummyServerContext(active_servers, fixture.lifecycle_events)

    fixture.engine._server_context_factory = server_context_factory

    async with fixture.engine.session([fixture.retrieval_planner_spec]) as workflow:
        await workflow.run_stage(
            spec=fixture.retrieval_planner_spec,
            ui_agent_id="retrieval_planner",
            prompt="find context",
            trace_label="RETRIEVAL_PLANNER OUTPUT",
            verbose=False,
        )

    assert fixture.build_calls == [("retrieval_planner", ["server:document"])]


@pytest.mark.anyio
async def test_workflow_session_traces_timeout(monkeypatch, engine_fixture):
    fixture = engine_fixture
    monkeypatch.setenv("CRISAI_AGENT_STAGE_TIMEOUT_SECONDS", "0.01")

    async def slow_stage_runner(agent_id, agent, prompt):
        del agent_id, agent, prompt
        await asyncio.sleep(1)
        return "late"

    fixture.engine._stage_runner = slow_stage_runner

    async with fixture.engine.session([fixture.retrieval_planner_spec]) as workflow:
        with pytest.raises(TimeoutError, match="retrieval_planner timed out"):
            await workflow.run_stage(
                spec=fixture.retrieval_planner_spec,
                ui_agent_id="retrieval_planner",
                prompt="find context",
                trace_label="RETRIEVAL_PLANNER OUTPUT",
                verbose=False,
            )

    error = fixture.trace_calls[-1]
    assert error[0] == "RETRIEVAL_PLANNER OUTPUT_ERROR"
    assert error[1] == (
        "Stage retrieval_planner timed out after 0.01s. Set CRISAI_AGENT_STAGE_TIMEOUT_SECONDS to tune this limit."
    )
    assert error[2]["event_type"] == "stage_error"
    assert error[2]["agent_id"] == "retrieval_planner"
    assert error[2]["metadata"]["timeout_seconds"] == 0.01
    _assert_execution_time(error[2]["metadata"]["observability"])
    assert fixture.output_calls == []


@pytest.mark.anyio
async def test_workflow_session_traces_stage_error_on_runner_exception(engine_fixture):
    fixture = engine_fixture

    async def failing_stage_runner(agent_id, agent, prompt):
        del agent_id, agent, prompt
        raise TypeError("bad model settings")

    fixture.engine._stage_runner = failing_stage_runner

    async with fixture.engine.session([fixture.retrieval_planner_spec]) as workflow:
        with pytest.raises(TypeError, match="bad model settings"):
            await workflow.run_stage(
                spec=fixture.retrieval_planner_spec,
                ui_agent_id="retrieval_planner",
                prompt="find context",
                trace_label="RETRIEVAL_PLANNER OUTPUT",
                verbose=False,
            )

    error = fixture.trace_calls[-1]
    assert error[0] == "RETRIEVAL_PLANNER OUTPUT_ERROR"
    assert error[1] == "Stage retrieval_planner failed: TypeError: bad model settings"
    assert error[2]["event_type"] == "stage_error"
    assert error[2]["agent_id"] == "retrieval_planner"
    assert error[2]["metadata"]["error_type"] == "TypeError"
    _assert_execution_time(error[2]["metadata"]["observability"])
    assert fixture.output_calls == []


@pytest.mark.anyio
async def test_workflow_session_fails_closed_on_empty_stage_output(engine_fixture):
    fixture = engine_fixture

    async def empty_stage_runner(agent_id, agent, prompt):
        del agent_id, agent, prompt
        return "   "

    fixture.engine._stage_runner = empty_stage_runner

    async with fixture.engine.session([fixture.retrieval_planner_spec]) as workflow:
        with pytest.raises(RuntimeError, match="returned empty output"):
            await workflow.run_stage(
                spec=fixture.retrieval_planner_spec,
                ui_agent_id="retrieval_planner",
                prompt="find context",
                trace_label="RETRIEVAL_PLANNER OUTPUT",
                verbose=False,
            )

    error = fixture.trace_calls[-1]
    assert error[0] == "RETRIEVAL_PLANNER OUTPUT_ERROR"
    assert error[1] == "Stage retrieval_planner returned empty output. This stage is required to produce a handoff or answer."
    assert error[2]["event_type"] == "stage_error"
    assert error[2]["agent_id"] == "retrieval_planner"
    assert error[2]["metadata"]["output_length"] == 0
    _assert_execution_time(error[2]["metadata"]["observability"])
    assert fixture.output_calls == []


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
    assert fixture.trace_calls[0] == (
        "RETRIEVAL_PLANNER OUTPUT_START",
        "Starting stage for retrieval_planner.",
        {"event_type": "stage_start", "agent_id": "retrieval_planner", "metadata": None},
    )
    assert fixture.trace_calls[1][0] == "RETRIEVAL_PLANNER OUTPUT"
    assert fixture.trace_calls[1][1] == "retrieval_planner::find context"
    assert fixture.trace_calls[1][2]["event_type"] == "stage_output"
    assert fixture.trace_calls[1][2]["agent_id"] == "retrieval_planner"
    _assert_execution_time(fixture.trace_calls[1][2]["metadata"]["observability"])
    assert fixture.trace_calls[2] == (
        "RETRIEVAL_PLANNER OUTPUT_END",
        "Completed stage for retrieval_planner.",
        {"event_type": "stage_end", "agent_id": "retrieval_planner", "metadata": None},
    )
    assert fixture.output_calls == [("retrieval_planner", "retrieval_planner::find context", True)]


@pytest.mark.anyio
async def test_workflow_session_processes_stage_output_before_trace_and_print(engine_fixture):
    fixture = engine_fixture

    async with fixture.engine.session([fixture.retrieval_planner_spec]) as workflow:
        result = await workflow.run_stage(
            spec=fixture.retrieval_planner_spec,
            ui_agent_id="retrieval_planner",
            prompt="find context",
            trace_label="RETRIEVAL_PLANNER OUTPUT",
            verbose=True,
            output_processor=lambda raw: ("clean stage output", {"artifacts": {"raw_length": len(raw)}}),
        )

    assert result == "retrieval_planner::find context"
    stage_output = fixture.trace_calls[1]
    assert stage_output[0] == "RETRIEVAL_PLANNER OUTPUT"
    assert stage_output[1] == "clean stage output"
    assert stage_output[2]["event_type"] == "stage_output"
    assert stage_output[2]["agent_id"] == "retrieval_planner"
    assert stage_output[2]["metadata"]["artifacts"] == {"raw_length": len("retrieval_planner::find context")}
    _assert_execution_time(stage_output[2]["metadata"]["observability"])
    assert fixture.output_calls == [("retrieval_planner", "clean stage output", True)]

@pytest.mark.anyio
async def test_workflow_session_adds_observability_to_stage_output_metadata(engine_fixture, caplog):
    fixture = engine_fixture

    async def observability_stage_runner(agent_id, agent, prompt):
        del agent_id, agent, prompt
        pipeline_display._emit_stage_observability(
            "streaming_fallback",
            {"streaming": {"attempted": True, "fallback": True, "fallback_reason": "sdk_incompatible"}},
        )
        pipeline_display._emit_stage_observability(
            "provider_usage",
            {"provider_usage": {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10}},
        )
        return "stage output"

    fixture.engine._stage_runner = observability_stage_runner

    with caplog.at_level(logging.INFO, logger="crisai.cli.pipeline_engine"):
        async with fixture.engine.session([fixture.retrieval_planner_spec]) as workflow:
            await workflow.run_stage(
                spec=fixture.retrieval_planner_spec,
                ui_agent_id="retrieval_planner",
                prompt="find context",
                trace_label="RETRIEVAL_PLANNER OUTPUT",
                verbose=False,
            )

    stage_output = fixture.trace_calls[1]
    assert stage_output[0] == "RETRIEVAL_PLANNER OUTPUT"
    observability = stage_output[2]["metadata"]["observability"]
    assert observability["streaming"] == {"attempted": True, "fallback": True, "fallback_reason": "sdk_incompatible"}
    assert observability["provider_usage"] == {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10}
    _assert_execution_time(observability)
    log_record = next(
        record for record in caplog.records if getattr(record, "event_type", None) == "agent_stage_observability"
    )
    assert log_record.run_id is None
    assert log_record.agent_id == "retrieval_planner"
    assert log_record.stage == "retrieval_planner"
    assert log_record.trace_label == "RETRIEVAL_PLANNER OUTPUT"
    assert log_record.provider_usage == {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10}
    assert log_record.execution_time == observability["execution_time"]
    assert "stage output" not in log_record.getMessage()


@pytest.mark.anyio
async def test_workflow_session_adds_model_cost_when_pricing_and_usage_exist(engine_fixture, caplog):
    fixture = engine_fixture

    class FakeResolver:
        def resolve_for_agent(self, spec):
            assert spec.id == "retrieval_planner"
            return SimpleNamespace(
                provider="openai",
                model_name="gpt-example",
                source="model_ref:openai_fast",
                extra={
                    "pricing": {
                        "currency": "USD",
                        "unit": "per_1m_tokens",
                        "input": "10",
                        "output": "20",
                    }
                },
            )

    fixture.environment.factory.model_resolver = FakeResolver()

    async def usage_stage_runner(agent_id, agent, prompt):
        del agent_id, agent, prompt
        pipeline_display._emit_stage_observability(
            "provider_usage",
            {"provider_usage": {"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500}},
        )
        return "stage output"

    fixture.engine._stage_runner = usage_stage_runner

    with caplog.at_level(logging.INFO, logger="crisai.cli.pipeline_engine"):
        async with fixture.engine.session([fixture.retrieval_planner_spec]) as workflow:
            await workflow.run_stage(
                spec=fixture.retrieval_planner_spec,
                ui_agent_id="retrieval_planner",
                prompt="find context",
                trace_label="RETRIEVAL_PLANNER OUTPUT",
                verbose=False,
            )

    observability = fixture.trace_calls[1][2]["metadata"]["observability"]
    assert observability["model"] == {
        "schema_version": "model_observability_v1",
        "provider": "openai",
        "model_name": "gpt-example",
        "source": "model_ref:openai_fast",
        "model_ref": "openai_fast",
    }
    assert observability["cost"] == {
        "schema_version": "usage_cost_v1",
        "currency": "USD",
        "estimated": True,
        "pricing_source": "model_ref:openai_fast",
        "pricing_unit": "per_1m_tokens",
        "input_cost_usd": 0.01,
        "output_cost_usd": 0.01,
        "total_cost_usd": 0.02,
    }
    log_record = next(
        record for record in caplog.records if getattr(record, "event_type", None) == "agent_stage_observability"
    )
    assert log_record.usage_cost == observability["cost"]
    assert log_record.model == observability["model"]


@pytest.mark.anyio
async def test_workflow_session_omits_cost_when_pricing_absent(engine_fixture):
    fixture = engine_fixture

    class FakeResolver:
        def resolve_for_agent(self, spec):
            return SimpleNamespace(
                provider="openai",
                model_name="gpt-example",
                source=f"model_ref:{spec.id}",
                extra={},
            )

    fixture.environment.factory.model_resolver = FakeResolver()

    async def usage_stage_runner(agent_id, agent, prompt):
        del agent_id, agent, prompt
        pipeline_display._emit_stage_observability(
            "provider_usage",
            {"provider_usage": {"input_tokens": 1000, "output_tokens": 500}},
        )
        return "stage output"

    fixture.engine._stage_runner = usage_stage_runner

    async with fixture.engine.session([fixture.retrieval_planner_spec]) as workflow:
        await workflow.run_stage(
            spec=fixture.retrieval_planner_spec,
            ui_agent_id="retrieval_planner",
            prompt="find context",
            trace_label="RETRIEVAL_PLANNER OUTPUT",
            verbose=False,
        )

    observability = fixture.trace_calls[1][2]["metadata"]["observability"]
    assert observability["model"]["model_ref"] == "retrieval_planner"
    assert "cost" not in observability


@pytest.mark.anyio
async def test_workflow_session_overwrites_stale_observability_schema(engine_fixture):
    fixture = engine_fixture

    async with fixture.engine.session([fixture.retrieval_planner_spec]) as workflow:
        await workflow.run_stage(
            spec=fixture.retrieval_planner_spec,
            ui_agent_id="retrieval_planner",
            prompt="find context",
            trace_label="RETRIEVAL_PLANNER OUTPUT",
            verbose=False,
            output_processor=lambda raw: (
                raw,
                {"observability": {"schema_version": "old_schema", "provider_usage": {"total_tokens": 2}}},
            ),
        )

    observability = fixture.trace_calls[1][2]["metadata"]["observability"]
    assert observability["schema_version"] == "ui_stage_observability_v1"
    assert observability["provider_usage"] == {"total_tokens": 2}
    _assert_execution_time(observability)


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
