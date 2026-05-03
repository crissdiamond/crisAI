from __future__ import annotations

from pathlib import Path

from crisai.registry import Registry


def test_retrieval_planner_agent_has_retrieval_servers_enabled():
    repo_root = Path(__file__).resolve().parents[2]
    registry = Registry(repo_root / "registry")
    agents = {agent.id: agent for agent in registry.load_agents()}

    planner = agents["retrieval_planner"]
    assert "workspace" in planner.allowed_servers
    assert "documents" in planner.allowed_servers
    assert "sharepoint_docs" in planner.allowed_servers
