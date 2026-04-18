from __future__ import annotations

import types
from pathlib import Path

import pytest
import typer

from crisai.registry import AgentSpec
import crisai.cli.pipelines as pipelines


class DummyAsyncContext:
    def __init__(self, servers):
        self.servers = servers

    async def __aenter__(self):
        return self.servers

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeFactory:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def build_agent(self, spec, active_servers):
        return types.SimpleNamespace(id=spec.id, active_servers=active_servers)


class FakeRuntimeManager:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def build_server(self, spec):
        return f"server:{spec.id}"


class FakeResult:
    def __init__(self, text: str) -> None:
        self.final_output = text


@pytest.fixture
def fake_specs():
    server_specs = {
        "workspace": types.SimpleNamespace(id="workspace"),
        "document": types.SimpleNamespace(id="document"),
    }
    agent_specs = {
        "discovery": AgentSpec("discovery", "Discovery", "m", "p", ["workspace"]),
        "design": AgentSpec("design", "Design", "m", "p", ["document"]),
        "review": AgentSpec("review", "Review", "m", "p", ["document"]),
        "orchestrator": AgentSpec("orchestrator", "Orchestrator", "m", "p", ["workspace"]),
        "design_author": AgentSpec("design_author", "Design Author", "m", "p", ["workspace"]),
        "design_challenger": AgentSpec("design_challenger", "Design Challenger", "m", "p", ["workspace"]),
        "design_refiner": AgentSpec("design_refiner", "Design Refiner", "m", "p", ["workspace"]),
        "judge": AgentSpec("judge", "Judge", "m", "p", ["workspace"]),
    }
    return server_specs, agent_specs


@pytest.fixture
def fake_settings(tmp_path: Path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return types.SimpleNamespace(openai_api_key="test-key", log_dir=log_dir)


@pytest.fixture
def patch_pipeline_runtime(monkeypatch):
    monkeypatch.setattr(pipelines, "RuntimeManager", FakeRuntimeManager)
    monkeypatch.setattr(pipelines, "AgentFactory", FakeFactory)
    monkeypatch.setattr(pipelines, "MultiServerContext", DummyAsyncContext)
    monkeypatch.setattr(pipelines, "append_trace", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipelines, "print_stage", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipelines, "print_markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipelines, "build_discovery_prompt", lambda message: f"DISCOVERY::{message}")
    monkeypatch.setattr(pipelines, "build_design_prompt", lambda message, discovery: f"DESIGN::{message}::{discovery}")
    monkeypatch.setattr(pipelines, "build_review_prompt", lambda message, discovery, design: f"REVIEW::{message}::{design}")
    monkeypatch.setattr(pipelines, "build_pipeline_final_prompt", lambda message, discovery, design, review: f"FINAL::{message}::{review}")
    monkeypatch.setattr(pipelines, "build_author_prompt", lambda message, discovery: f"AUTHOR::{message}")
    monkeypatch.setattr(pipelines, "build_challenger_prompt", lambda message, discovery, author: f"CHALLENGER::{message}")
    monkeypatch.setattr(pipelines, "build_refiner_prompt", lambda message, discovery, author, challenger: f"REFINER::{message}")
    monkeypatch.setattr(pipelines, "build_judge_prompt", lambda message, discovery, challenger, refiner: f"JUDGE::{message}")
    monkeypatch.setattr(pipelines, "build_peer_final_prompt", lambda message, discovery, author, challenger, refiner, judge: f"PEER_FINAL::{message}")


@pytest.mark.asyncio
async def test_run_single_uses_selected_agent(monkeypatch, fake_specs, fake_settings, patch_pipeline_runtime):
    server_specs, agent_specs = fake_specs
    calls: list[str] = []

    async def fake_run(agent, message):
        calls.append(agent.id)
        return FakeResult(f"OUT::{agent.id}::{message}")

    monkeypatch.setattr(pipelines.Runner, "run", fake_run)

    result = await pipelines.run_single(
        "hello",
        "design",
        settings=fake_settings,
        server_specs=server_specs,
        agent_specs=agent_specs,
    )

    assert result == "OUT::design::hello"
    assert calls == ["design"]


@pytest.mark.asyncio
async def test_run_single_raises_for_unknown_agent(fake_specs, fake_settings, patch_pipeline_runtime):
    server_specs, agent_specs = fake_specs
    with pytest.raises(typer.BadParameter):
        await pipelines.run_single(
            "hello",
            "missing",
            settings=fake_settings,
            server_specs=server_specs,
            agent_specs=agent_specs,
        )


@pytest.mark.asyncio
async def test_pipeline_runs_expected_stage_order_when_review_off(monkeypatch, fake_specs, fake_settings, patch_pipeline_runtime):
    server_specs, agent_specs = fake_specs
    calls: list[str] = []

    async def fake_run(agent, message):
        calls.append(agent.id)
        return FakeResult(f"{agent.id.upper()} OUTPUT")

    monkeypatch.setattr(pipelines.Runner, "run", fake_run)

    result = await pipelines.run_pipeline(
        "draft something",
        verbose=False,
        review=False,
        settings=fake_settings,
        server_specs=server_specs,
        agent_specs=agent_specs,
    )

    assert calls == ["discovery", "design", "orchestrator"]
    assert result == "ORCHESTRATOR OUTPUT"


@pytest.mark.asyncio
async def test_pipeline_runs_expected_stage_order_when_review_on(monkeypatch, fake_specs, fake_settings, patch_pipeline_runtime):
    server_specs, agent_specs = fake_specs
    calls: list[str] = []

    async def fake_run(agent, message):
        calls.append(agent.id)
        return FakeResult(f"{agent.id.upper()} OUTPUT")

    monkeypatch.setattr(pipelines.Runner, "run", fake_run)

    result = await pipelines.run_pipeline(
        "draft something",
        verbose=False,
        review=True,
        settings=fake_settings,
        server_specs=server_specs,
        agent_specs=agent_specs,
    )

    assert calls == ["discovery", "design", "review", "orchestrator"]
    assert result == "ORCHESTRATOR OUTPUT"
