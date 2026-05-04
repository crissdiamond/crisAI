from __future__ import annotations

import types
from pathlib import Path

import pytest

from crisai.registry import AgentSpec
import crisai.cli.pipelines as pipelines
from crisai.cli.peer_transcript import peer_speakers


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
    server_specs = {"workspace": types.SimpleNamespace(id="workspace")}
    agent_specs = {
        "retrieval_planner": AgentSpec(
            id="retrieval_planner",
            name="Retrieval Planner",
            prompt_file="prompts/retrieval_planner_agent.md",
            allowed_servers=["workspace"],
        ),
        "context_retrieval": AgentSpec(
            id="context_retrieval",
            name="Context Retrieval",
            prompt_file="prompts/context_retrieval.md",
            allowed_servers=["workspace"],
        ),
        "context_synthesizer": AgentSpec(
            id="context_synthesizer",
            name="Context Synthesizer",
            prompt_file="prompts/context_synthesizer_agent.md",
            allowed_servers=["workspace"],
        ),
        "design_author": AgentSpec(
            id="design_author",
            name="Design Author",
            prompt_file="prompts/design_author.md",
            allowed_servers=["workspace"],
        ),
        "design_challenger": AgentSpec(
            id="design_challenger",
            name="Design Challenger",
            prompt_file="prompts/design_challenger.md",
            allowed_servers=["workspace"],
        ),
        "design_refiner": AgentSpec(
            id="design_refiner",
            name="Design Refiner",
            prompt_file="prompts/design_refiner.md",
            allowed_servers=["workspace"],
        ),
        "judge": AgentSpec(
            id="judge",
            name="Judge",
            prompt_file="prompts/judge.md",
            allowed_servers=["workspace"],
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
def patch_peer_runtime(monkeypatch):
    monkeypatch.setattr(pipelines, "RuntimeManager", FakeRuntimeManager)
    monkeypatch.setattr(pipelines, "AgentFactory", FakeFactory)
    monkeypatch.setattr(pipelines, "MultiServerContext", DummyAsyncContext)
    monkeypatch.setattr(pipelines, "append_trace", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipelines, "print_agent_output", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipelines, "build_retrieval_planner_prompt", lambda message: f"RETRIEVAL_PLANNER::{message}")
    monkeypatch.setattr(pipelines, "build_author_prompt", lambda message, discovery: f"AUTHOR::{message}")
    monkeypatch.setattr(pipelines, "build_challenger_prompt", lambda message, discovery, author: f"CHALLENGER::{message}")
    monkeypatch.setattr(pipelines, "build_refiner_prompt", lambda message, discovery, author, challenger: f"REFINER::{message}")
    monkeypatch.setattr(pipelines, "build_judge_prompt", lambda message, discovery, challenger, refiner: f"JUDGE::{message}")
    monkeypatch.setattr(pipelines, "build_peer_final_prompt", lambda message, discovery, author, challenger, refiner, judge: f"PEER_FINAL::{message}")


@pytest.mark.anyio
async def test_peer_mode_runs_expected_stage_order_when_retrieval_is_needed(monkeypatch, fake_specs, fake_settings, patch_peer_runtime):
    server_specs, agent_specs = fake_specs
    calls: list[str] = []

    async def fake_run_with_transient_box(agent_id, agent, prompt):
        calls.append(agent.id)
        if agent.id == "orchestrator":
            return "Final recommendation\nORCHESTRATOR OUTPUT"
        return f"{agent.id.upper()} OUTPUT"

    monkeypatch.setattr(pipelines, "_run_agent_with_transient_box", fake_run_with_transient_box)

    result = await pipelines.run_peer_pipeline(
        "debate this design",
        verbose=False,
        review=True,
        settings=fake_settings,
        server_specs=server_specs,
        agent_specs=agent_specs,
        needs_retrieval=True,
    )

    assert calls == [
        "retrieval_planner",
        "context_retrieval",
        "context_synthesizer",
        "design_author",
        "design_challenger",
        "design_refiner",
        "judge",
        "orchestrator",
    ]
    assert result == "Final recommendation\nORCHESTRATOR OUTPUT"


@pytest.mark.anyio
async def test_peer_mode_runs_all_peer_stages_even_when_review_off(monkeypatch, fake_specs, fake_settings, patch_peer_runtime):
    server_specs, agent_specs = fake_specs
    calls: list[str] = []

    async def fake_run_with_transient_box(agent_id, agent, prompt):
        calls.append(agent.id)
        if agent.id == "orchestrator":
            return "Final recommendation\nORCHESTRATOR OUTPUT"
        return f"{agent.id.upper()} OUTPUT"

    monkeypatch.setattr(pipelines, "_run_agent_with_transient_box", fake_run_with_transient_box)

    result = await pipelines.run_peer_pipeline(
        "debate this design",
        verbose=False,
        review=False,
        settings=fake_settings,
        server_specs=server_specs,
        agent_specs=agent_specs,
        needs_retrieval=True,
    )

    assert calls == [
        "retrieval_planner",
        "context_retrieval",
        "context_synthesizer",
        "design_author",
        "design_challenger",
        "design_refiner",
        "judge",
        "orchestrator",
    ]
    assert result == "Final recommendation\nORCHESTRATOR OUTPUT"


@pytest.mark.anyio
async def test_peer_mode_skips_retrieval_planner_when_retrieval_not_needed(monkeypatch, fake_specs, fake_settings, patch_peer_runtime):
    server_specs, agent_specs = fake_specs
    calls: list[str] = []

    async def fake_run_with_transient_box(agent_id, agent, prompt):
        calls.append(agent.id)
        if agent.id == "orchestrator":
            return "Final recommendation\nORCHESTRATOR OUTPUT"
        return f"{agent.id.upper()} OUTPUT"

    monkeypatch.setattr(pipelines, "_run_agent_with_transient_box", fake_run_with_transient_box)

    result = await pipelines.run_peer_pipeline(
        "propose a simple CLI design",
        verbose=False,
        review=False,
        settings=fake_settings,
        server_specs=server_specs,
        agent_specs=agent_specs,
        needs_retrieval=False,
    )

    assert calls == [
        "design_author",
        "design_challenger",
        "design_refiner",
        "judge",
        "orchestrator",
    ]
    assert result == "Final recommendation\nORCHESTRATOR OUTPUT"


def test_build_peer_run_result_contains_expected_speakers() -> None:
    run_result = pipelines.build_peer_run_result(
        discovery_text="Found docs",
        author_text="Draft",
        challenger_text="Challenge",
        refiner_text="Refined draft",
        judge_text="Decision",
        final_text="Final answer",
    )
    assert peer_speakers(run_result.transcript) == [
        "retrieval_planner",
        "design_author",
        "design_challenger",
        "design_refiner",
        "judge",
        "orchestrator",
    ]
    assert run_result.final_text == "Final answer"
