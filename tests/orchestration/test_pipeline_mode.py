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


@pytest.fixture
def fake_specs():
    server_specs = {
        "workspace": types.SimpleNamespace(id="workspace"),
        "document": types.SimpleNamespace(id="document"),
    }
    agent_specs = {
        "discovery": AgentSpec(id="discovery", name="Discovery", prompt_file="prompts/discovery.md", allowed_servers=[]),
        "context_retrieval": AgentSpec(
            id="context_retrieval",
            name="Context Retrieval",
            prompt_file="prompts/context_retrieval.md",
            allowed_servers=["workspace", "document"],
        ),
        "context": AgentSpec(
            id="context",
            name="Context",
            prompt_file="prompts/context.md",
            allowed_servers=["workspace", "document"],
        ),
        "design": AgentSpec(
            id="design",
            name="Design",
            prompt_file="prompts/design.md",
            allowed_servers=["document"],
        ),
        "review": AgentSpec(
            id="review",
            name="Review",
            prompt_file="prompts/review.md",
            allowed_servers=["document"],
        ),
        "orchestrator": AgentSpec(
            id="orchestrator",
            name="Orchestrator",
            prompt_file="prompts/orchestrator.md",
            allowed_servers=["workspace"],
        ),
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
    monkeypatch.setattr(pipelines, "print_agent_output", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipelines, "build_discovery_prompt", lambda message: f"DISCOVERY::{message}")
    monkeypatch.setattr(pipelines, "build_context_prompt", lambda message, discovery: f"CONTEXT::{message}::{discovery}")
    monkeypatch.setattr(pipelines, "build_design_prompt", lambda message, context: f"DESIGN::{message}::{context}")
    monkeypatch.setattr(pipelines, "build_review_prompt", lambda message, discovery, design: f"REVIEW::{message}::{design}")
    monkeypatch.setattr(pipelines, "build_pipeline_final_prompt", lambda message, discovery, design, review: f"FINAL::{message}::{review}")


@pytest.mark.anyio
async def test_run_single_uses_selected_agent(monkeypatch, fake_specs, fake_settings, patch_pipeline_runtime):
    server_specs, agent_specs = fake_specs
    calls: list[str] = []

    async def fake_run_agent_silently(agent, prompt):
        calls.append(agent.id)
        return f"OUT::{agent.id}::{prompt}"

    monkeypatch.setattr(pipelines, "_run_agent_silently", fake_run_agent_silently)

    result = await pipelines.run_single(
        "hello",
        "design",
        settings=fake_settings,
        server_specs=server_specs,
        agent_specs=agent_specs,
    )

    assert result == "OUT::design::hello"
    assert calls == ["design"]


@pytest.mark.anyio
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


@pytest.mark.anyio
async def test_pipeline_runs_expected_stage_order_when_review_off(monkeypatch, fake_specs, fake_settings, patch_pipeline_runtime):
    server_specs, agent_specs = fake_specs
    calls: list[str] = []

    async def fake_run_with_transient_box(agent_id, agent, prompt):
        calls.append(agent.id)
        return f"{agent.id.upper()} OUTPUT"

    monkeypatch.setattr(pipelines, "_run_agent_with_transient_box", fake_run_with_transient_box)

    result = await pipelines.run_pipeline(
        "draft something",
        verbose=False,
        review=False,
        settings=fake_settings,
        server_specs=server_specs,
        agent_specs=agent_specs,
    )

    assert calls == [
        "discovery",
        "context_retrieval",
        "context",
        "design",
        "orchestrator",
    ]
    assert result == "ORCHESTRATOR OUTPUT"


@pytest.mark.anyio
async def test_pipeline_runs_expected_stage_order_when_review_on(monkeypatch, fake_specs, fake_settings, patch_pipeline_runtime):
    server_specs, agent_specs = fake_specs
    calls: list[str] = []

    async def fake_run_with_transient_box(agent_id, agent, prompt):
        calls.append(agent.id)
        return f"{agent.id.upper()} OUTPUT"

    monkeypatch.setattr(pipelines, "_run_agent_with_transient_box", fake_run_with_transient_box)

    result = await pipelines.run_pipeline(
        "draft something",
        verbose=False,
        review=True,
        settings=fake_settings,
        server_specs=server_specs,
        agent_specs=agent_specs,
    )

    assert calls == [
        "discovery",
        "context_retrieval",
        "context",
        "design",
        "review",
        "orchestrator",
    ]
    assert result == "ORCHESTRATOR OUTPUT"
