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
