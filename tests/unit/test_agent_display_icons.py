from __future__ import annotations

from pathlib import Path

from crisai.cli import display
from crisai.registry import Registry


def test_every_registry_agent_has_display_icon_and_label() -> None:
    """Guardrail: flow tabs and status views expect icons for each registered agent."""
    repo_root = Path(__file__).resolve().parents[2]
    registry = Registry(repo_root / "registry")
    agent_ids = {agent.id for agent in registry.load_agents()}

    missing_icons = sorted(agent_ids - set(display._ICONS.keys()))
    missing_labels = sorted(agent_ids - set(display._LABELS.keys()))

    assert not missing_icons, f"Add _ICONS entries for: {missing_icons}"
    assert not missing_labels, f"Add _LABELS entries for: {missing_labels}"
