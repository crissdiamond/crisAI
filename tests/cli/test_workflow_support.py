from __future__ import annotations

from types import SimpleNamespace

import pytest
import typer

from crisai.cli.workflow_support import (
    append_trace_entry,
    collect_server_ids,
    create_workflow_environment,
    ensure_openai_api_key,
    resolve_required_agents,
    run_traced_stage,
)


class DummyRuntimeManager:
    def __init__(self, root_dir):
        self.root_dir = root_dir


class DummyAgentFactory:
    def __init__(self, root_dir):
        self.root_dir = root_dir


def test_ensure_openai_api_key_raises_when_missing():
    settings = SimpleNamespace(openai_api_key="")
    with pytest.raises(typer.BadParameter):
        ensure_openai_api_key(settings)


def test_resolve_required_agents_returns_requested_specs():
    agent_specs = {"a": object(), "b": object()}
    resolved = resolve_required_agents(agent_specs, ["a", "b"], mode_name="Peer mode")
    assert resolved == {"a": agent_specs["a"], "b": agent_specs["b"]}


def test_resolve_required_agents_raises_for_missing_entries():
    with pytest.raises(typer.BadParameter) as exc:
        resolve_required_agents({"a": object()}, ["a", "b"], mode_name="Peer mode")
    assert "Peer mode requires these agents" in str(exc.value)
    assert "b" in str(exc.value)


def test_collect_server_ids_returns_sorted_unique_ids():
    specs = [
        SimpleNamespace(allowed_servers=["z", "a"]),
        SimpleNamespace(allowed_servers=["a", "b"]),
    ]
    assert collect_server_ids(specs) == ["a", "b", "z"]


def test_create_workflow_environment_uses_cwd(monkeypatch, tmp_path):
    monkeypatch.setattr("crisai.cli.workflow_support.RuntimeManager", DummyRuntimeManager)
    monkeypatch.setattr("crisai.cli.workflow_support.AgentFactory", DummyAgentFactory)
    monkeypatch.chdir(tmp_path)

    settings = SimpleNamespace(log_dir=tmp_path / "logs")
    environment = create_workflow_environment(settings)

    assert environment.root_dir == tmp_path
    assert isinstance(environment.runtime, DummyRuntimeManager)
    assert isinstance(environment.factory, DummyAgentFactory)
    assert environment.trace_file == tmp_path / "logs" / "agent_trace.jsonl"


@pytest.mark.anyio
async def test_run_traced_stage_builds_runs_traces_and_prints(monkeypatch, tmp_path):
    built = []
    traces = []
    printed = []

    async def fake_runner(agent_id, agent, prompt):
        assert agent_id == "design"
        assert agent == "built-agent"
        assert prompt == "hello"
        return "result"

    def fake_append_trace(path, stage, content):
        traces.append((path, stage, content))

    def fake_print_agent_output(agent_id, body, *, verbose):
        printed.append((agent_id, body, verbose))

    class DummyFactory:
        def build_agent(self, spec, active_servers):
            built.append((spec, active_servers))
            return "built-agent"

    monkeypatch.setattr("crisai.cli.workflow_support.append_trace", fake_append_trace)
    monkeypatch.setattr("crisai.cli.workflow_support.print_agent_output", fake_print_agent_output)

    environment = SimpleNamespace(
        factory=DummyFactory(),
        trace_file=tmp_path / "trace.log",
    )

    spec = SimpleNamespace(id="design")
    active_servers = ["server-a"]

    result = await run_traced_stage(
        environment=environment,
        active_servers=active_servers,
        spec=spec,
        ui_agent_id="design",
        prompt="hello",
        trace_label="DESIGN OUTPUT",
        verbose=True,
        runner=fake_runner,
    )

    assert result == "result"
    assert built == [(spec, active_servers)]
    assert traces == [(tmp_path / "trace.log", "DESIGN OUTPUT", "result")]
    assert printed == [("design", "result", True)]


def test_append_trace_entry_delegates(monkeypatch, tmp_path):
    calls = []

    def fake_append_trace(path, stage, content):
        calls.append((path, stage, content))

    monkeypatch.setattr("crisai.cli.workflow_support.append_trace", fake_append_trace)
    environment = SimpleNamespace(trace_file=tmp_path / "trace.log")

    append_trace_entry(environment, "USER INPUT", "hello")

    assert calls == [(tmp_path / "trace.log", "USER INPUT", "hello")]
