from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_mono_provider_agent_examples_match_live_agent_ids_and_model_refs() -> None:
    """Keep mono-provider examples aligned with the live agent/model registry."""
    registry_dir = REPO_ROOT / "registry"
    live_agents = yaml.safe_load((registry_dir / "agents.yaml").read_text(encoding="utf-8"))["agents"]
    live_agent_ids = {agent["id"] for agent in live_agents}
    model_ids = {
        model["id"]
        for model in yaml.safe_load((registry_dir / "models.yaml").read_text(encoding="utf-8"))["models"]
    }

    for path in sorted((registry_dir / "examples").glob("agents.*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        agents = payload["agents"]
        assert {agent["id"] for agent in agents} == live_agent_ids, path
        assert all(agent["model_ref"] in model_ids for agent in agents), path


def test_mono_provider_agent_examples_use_expected_provider_families() -> None:
    """Ensure each example only references models from its advertised provider."""
    expected_prefixes = {
        "agents.openai.yaml": "openai_",
        "agents.deepseek.yaml": "deepseek_",
        "agents.gemini.yaml": "gemini_",
        "agents.anthropic.yaml": "anthropic_",
    }

    for filename, prefix in expected_prefixes.items():
        payload = yaml.safe_load((REPO_ROOT / "registry" / "examples" / filename).read_text(encoding="utf-8"))
        assert all(agent["model_ref"].startswith(prefix) for agent in payload["agents"])
