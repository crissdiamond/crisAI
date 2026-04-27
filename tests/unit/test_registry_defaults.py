from __future__ import annotations

from pathlib import Path

from crisai.registry import Registry


def test_discovery_agent_has_retrieval_servers_enabled():
    repo_root = Path(__file__).resolve().parents[2]
    registry = Registry(repo_root / "registry")
    agents = {agent.id: agent for agent in registry.load_agents()}

    discovery = agents["discovery"]
    assert "workspace" in discovery.allowed_servers
    assert "documents" in discovery.allowed_servers
    assert "sharepoint_docs" in discovery.allowed_servers
