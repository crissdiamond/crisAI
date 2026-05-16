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
    rel = "workspace/knowledge_staging/patterns/consumer-pattern-1-acme.md"
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
    a = "workspace/knowledge_staging/patterns/ingestion-pattern-3-one.md"
    b = "workspace/knowledge_staging/patterns/ingestion-pattern-3-two.md"
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
    rel = "workspace/knowledge/designs/campus-network-hld.md"
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


def test_generated_task_artefact_conforms_to_declared_markdown_template(
    registry_dir: Path,
    tmp_path: Path,
):
    root = tmp_path
    headings = [
        "Situation",
        "Assessment",
        "Decision",
        "Actions",
    ]
    template_rel = "workspace/knowledge/reference/template/custom-deliverable.md"
    _write(
        root / template_rel,
        (
            "---\n"
            "id: REF-TPL-CUSTOM-001\n"
            "title: Custom deliverable template\n"
            "type: custom_deliverable\n"
            "status: approved\n"
            "template_conformance:\n"
            "  placeholder_policy: error\n"
            "---\n\n"
            + "\n\n".join(f"## {heading}\nTemplate guidance." for heading in headings)
            + "\n"
        ),
    )
    rel = "workspace/tasks/custom/artefacts/custom-deliverable.md"
    body = "\n\n".join(f"## {heading}\nContent." for heading in headings)
    _write(
        root / rel,
        (
            "---\n"
            "id: CUSTOM-1\n"
            "title: Custom Deliverable\n"
            "type: custom_deliverable\n"
            "status: draft\n"
            "template_id: REF-TPL-CUSTOM-001\n"
            f"template_path: {template_rel}\n"
            "---\n\n"
            f"{body}\n"
        ),
    )

    result = validate_workspace_artefact_paths(
        root_dir=root,
        relative_paths=[rel],
        registry_dir=registry_dir,
    )

    assert result.ok


def test_template_declared_rules_are_applied_without_type_specific_profiles(
    registry_dir: Path,
    tmp_path: Path,
):
    root = tmp_path
    template_rel = "workspace/knowledge/reference/template/diagrammed-brief.md"
    _write(
        root / template_rel,
        (
            "---\n"
            "id: REF-TPL-DIAGRAMMED-001\n"
            "title: Diagrammed brief template\n"
            "type: diagrammed_brief\n"
            "status: approved\n"
            "template_conformance:\n"
            "  require_mermaid: true\n"
            "  placeholder_policy: error\n"
            "---\n\n"
            "## Overview\nDescribe the situation.\n\n"
            "## Flow\nShow the flow.\n"
        ),
    )
    rel = "workspace/tasks/custom/artefacts/diagrammed-brief.md"
    _write(
        root / rel,
        (
            "---\n"
            "id: BRIEF-1\n"
            "title: Diagrammed Brief\n"
            "type: diagrammed_brief\n"
            "status: draft\n"
            "template_id: REF-TPL-DIAGRAMMED-001\n"
            f"template_path: {template_rel}\n"
            "---\n\n"
            "## Overview\nContent.\n\n"
            "## Flow\nContent.\n"
        ),
    )

    result = validate_workspace_artefact_paths(
        root_dir=root,
        relative_paths=[rel],
        registry_dir=registry_dir,
    )

    assert any("Mermaid" in violation for violation in result.violations)


def test_generated_task_artefact_fails_template_conformance(registry_dir: Path, tmp_path: Path):
    root = tmp_path
    template_rel = "workspace/knowledge/reference/template/custom-review.md"
    _write(
        root / template_rel,
        (
            "---\n"
            "id: REF-TPL-REVIEW-001\n"
            "title: Custom review template\n"
            "type: custom_review\n"
            "status: approved\n"
            "template_conformance:\n"
            "  placeholder_policy: error\n"
            "---\n\n"
            "## Summary\nContent.\n\n"
            "## Findings\nContent.\n\n"
            "## Actions\nContent.\n"
        ),
    )
    rel = "workspace/tasks/custom/artefacts/custom-review.md"
    _write(
        root / rel,
        (
            "---\n"
            "id: REVIEW-1\n"
            "title: Custom Review\n"
            "type: custom_review\n"
            "status: draft\n"
            "template_id: REF-TPL-REVIEW-001\n"
            f"template_path: {template_rel}\n"
            "---\n\n"
            "## Summary\n[system] placeholder remains.\n"
        ),
    )

    result = validate_workspace_artefact_paths(
        root_dir=root,
        relative_paths=[rel],
        registry_dir=registry_dir,
    )

    assert any("Findings" in violation for violation in result.violations)
    assert any("placeholder" in violation for violation in result.violations)


def test_template_manifest_required_sections_are_used(registry_dir: Path, tmp_path: Path):
    root = tmp_path
    manifest = "workspace/knowledge/templates/custom/custom-export.template.yaml"
    _write(
        root / manifest,
        "template_id: custom_export\nrequired_sections:\n  - Opening\n  - Decision\n",
    )
    rel = "workspace/tasks/custom/artefacts/custom-export.md"
    _write(
        root / rel,
        (
            "---\n"
            "id: EXPORT-1\n"
            "title: Custom Export\n"
            "type: custom_export\n"
            "status: draft\n"
            "template_id: custom_export\n"
            f"template_path: {manifest}\n"
            "---\n\n"
            "## Opening\nContent.\n"
        ),
    )

    result = validate_workspace_artefact_paths(
        root_dir=root,
        relative_paths=[rel],
        registry_dir=registry_dir,
    )

    assert any("Decision" in violation for violation in result.violations)


def test_readme_relaxed_metadata(registry_dir: Path, tmp_path: Path):
    root = tmp_path
    rel = "workspace/knowledge/standards/sub/README.md"
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
