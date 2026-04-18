from __future__ import annotations

import types
from pathlib import Path

from crisai.agents.factory import AgentFactory
from crisai.registry import AgentSpec


def test_load_prompt_reads_prompt_file(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    prompt_file = prompts_dir / "design.md"
    prompt_file.write_text("You are the design agent.", encoding="utf-8")

    factory = AgentFactory(tmp_path)
    assert factory.load_prompt("prompts/design.md") == "You are the design agent."


def test_build_agent_uses_spec_and_loaded_prompt(monkeypatch, tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "discovery.md").write_text("Discovery instructions", encoding="utf-8")

    captured: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("crisai.agents.factory.Agent", FakeAgent)

    factory = AgentFactory(tmp_path)
    spec = AgentSpec(
        id="discovery",
        name="Discovery",
        model="gpt-test",
        prompt_file="prompts/discovery.md",
        allowed_servers=["workspace"],
    )

    agent = factory.build_agent(spec, mcp_servers=["srv-1"])
    assert isinstance(agent, FakeAgent)
    assert captured["name"] == "Discovery"
    assert captured["instructions"] == "Discovery instructions"
    assert captured["model"] == "gpt-test"
    assert captured["mcp_servers"] == ["srv-1"]
