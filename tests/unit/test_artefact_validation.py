"""Tests for registry-driven workspace artefact validation."""

from pathlib import Path

import pytest

from crisai.workspace.artefact_validation import (
    load_artefact_profiles,
    validate_workspace_artefact_paths,
)

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registry"


@pytest.fixture
def registry_dir() -> Path:
    return REGISTRY_DIR


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_load_artefact_profiles_reads_registry(registry_dir: Path):
    profiles = load_artefact_profiles(registry_dir)
    assert profiles.validate_path_prefixes
    assert any(p.get("id") == "integration_pattern_leaf" for p in profiles.profiles)


def test_validate_flags_missing_integration_pattern_section(tmp_path: Path, registry_dir: Path):
    root = tmp_path
    rel = "workspace/context_staging/patterns/consumer-pattern-1-acme.md"
    _write(
        root / rel,
        (
            "---\nid: P1\ntitle: T\ntype: pattern\nstatus: draft\nowner: Architecture\n---\n\n"
            "## Design overview\nx\n"
            "## When to use\nx\n"
            "## Implementation\nx\n"
            "## NFRS\nx\n"
            "## Anti-patterns or when not to use\nx\n"
            "## Source\n-\n"
        ),
    )
    result = validate_workspace_artefact_paths(
        root_dir=root,
        relative_paths=[rel],
        registry_dir=registry_dir,
    )
    assert any("References" in v for v in result.violations)


def test_integration_pattern_slug_dedup(registry_dir: Path, tmp_path: Path):
    root = tmp_path
    a = "workspace/context_staging/patterns/ingestion-pattern-3-one.md"
    b = "workspace/context_staging/patterns/ingestion-pattern-3-two.md"
    body = (
        "---\nid: IA\ntitle: A\ntype: pattern\nstatus: draft\nowner: Architecture\n---\n\n"
        "## Design overview\nx\n## When to use\nx\n## Implementation\nx\n"
        "## NFRS\nx\n## Anti-patterns or when not to use\nx\n## Source\n-\n## References\n-\n"
    )
    _write(root / a, body.replace("IA", "IA"))
    _write(root / b, body.replace("IA", "IB"))
    result = validate_workspace_artefact_paths(
        root_dir=root,
        relative_paths=[a, b],
        registry_dir=registry_dir,
    )
    assert any("integration_pattern_slug_dedup" in v for v in result.violations)


def test_type_alias_maps_hld(registry_dir: Path, tmp_path: Path):
    root = tmp_path
    rel = "workspace/context/designs/campus-network-hld.md"
    _write(
        root / rel,
        (
            "---\nid: H1\ntitle: H\ntype: HLD\nstatus: draft\n---\n\n"
            "## Context\nx\n## Target architecture\nx\n## Key decisions\nx\n"
        ),
    )
    result = validate_workspace_artefact_paths(
        root_dir=root,
        relative_paths=[rel],
        registry_dir=registry_dir,
    )
    assert result.ok


def test_readme_relaxed_metadata(registry_dir: Path, tmp_path: Path):
    root = tmp_path
    rel = "workspace/context/standards/sub/README.md"
    _write(root / rel, "# Folder notes\n\n## Overview\nBrief.\n")
    result = validate_workspace_artefact_paths(
        root_dir=root,
        relative_paths=[rel],
        registry_dir=registry_dir,
    )
    assert result.ok


def test_skips_paths_outside_configured_prefixes(registry_dir: Path, tmp_path: Path):
    root = tmp_path
    rel = "workspace/other-area/file.md"
    _write(root / rel, "no front matter here\n")
    result = validate_workspace_artefact_paths(
        root_dir=root,
        relative_paths=[rel],
        registry_dir=registry_dir,
    )
    assert result.ok

