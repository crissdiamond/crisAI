"""Guardrails for prompt scaffolding (template + registry paths)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]

_TEMPLATE_PATH = _REPO_ROOT / "prompts" / "TEMPLATE.md"
_README_PATH = _REPO_ROOT / "prompts" / "README.md"
_AGENTS_PATH = _REPO_ROOT / "registry" / "agents.yaml"

# Headings that every new prompt should mirror (also defined in prompts/README.md).
_REQUIRED_TEMPLATE_SECTIONS: tuple[str, ...] = (
    "## Identity",
    "## Mission",
    "## Inputs",
    "## Authority",
    "## Boundaries",
    "## Tooling and data",
    "## Output contract",
    "## Quality bar",
)


@pytest.mark.parametrize("heading", _REQUIRED_TEMPLATE_SECTIONS)
def test_template_contains_all_canonical_sections(heading: str) -> None:
    text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    assert heading in text, f"TEMPLATE.md must include {heading!r}"


def test_prompt_readme_documents_template() -> None:
    body = _README_PATH.read_text(encoding="utf-8")
    assert "TEMPLATE.md" in body
    assert "agents.yaml" in body


@pytest.mark.parametrize(
    "path",
    [pytest.param(_TEMPLATE_PATH, id="template"), pytest.param(_README_PATH, id="readme")],
)
def test_scaffolding_files_exist(path: Path) -> None:
    assert path.is_file(), f"missing {path}"


def test_registry_prompt_files_exist() -> None:
    data = yaml.safe_load(_AGENTS_PATH.read_text(encoding="utf-8")) or {}
    agents = data.get("agents") or []
    assert agents, "registry/agents.yaml should list agents"

    missing: list[str] = []
    for entry in agents:
        rel = entry.get("prompt_file")
        if not rel:
            missing.append(f"agent {entry.get('id')!r} has no prompt_file")
            continue
        candidate = _REPO_ROOT / rel
        if not candidate.is_file():
            missing.append(f"{entry.get('id')!r}: {rel} -> not a file")

    assert not missing, "prompt_file paths must exist:\n" + "\n".join(missing)


def _registry_prompt_relative_paths() -> list[str]:
    data = yaml.safe_load(_AGENTS_PATH.read_text(encoding="utf-8")) or {}
    agents = data.get("agents") or []
    return [str(a["prompt_file"]) for a in agents if a.get("prompt_file")]


@pytest.mark.parametrize("rel", _registry_prompt_relative_paths())
def test_registry_agent_prompts_include_all_canonical_sections(rel: str) -> None:
    text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
    missing = [h for h in _REQUIRED_TEMPLATE_SECTIONS if h not in text]
    assert not missing, f"{rel} missing sections: {missing}"


@pytest.mark.parametrize("rel", _registry_prompt_relative_paths())
def test_registry_agent_prompts_canonical_sections_in_order(rel: str) -> None:
    text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
    positions = [text.find(h) for h in _REQUIRED_TEMPLATE_SECTIONS]
    assert all(p >= 0 for p in positions), f"{rel} missing a canonical section"
    assert positions == sorted(positions), f"{rel}: canonical ## sections must appear in template order"


def test_context_synthesizer_prompt_file_matches_registry_id() -> None:
    """Avoid regression to opaque names like context_agent.md for this id."""
    data = yaml.safe_load(_AGENTS_PATH.read_text(encoding="utf-8")) or {}
    agents = data.get("agents") or []
    synth = next((a for a in agents if a.get("id") == "context_synthesizer"), None)
    assert synth is not None
    path = str(synth.get("prompt_file", ""))
    assert "context_synthesizer" in path.replace("-", "_"), path
