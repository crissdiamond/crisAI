from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from crisai.cli import artefact_lifecycle, session_store

REPO_ROOT = Path(__file__).resolve().parents[2]


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        workspace_dir=tmp_path / "workspace",
        registry_dir=REPO_ROOT / "registry",
        root_dir=tmp_path,
    )


def test_persist_reusable_deliverable_saves_option_paper_and_updates_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(artefact_lifecycle, "load_settings", lambda: settings)
    monkeypatch.setattr(session_store, "load_settings", lambda: settings)

    final_output = (
        "# Power BI Options Paper\n\n"
        "## Executive summary\n\n"
        + ("This options paper compares the relevant reporting implementation choices. " * 30)
    )

    result = artefact_lifecycle.persist_reusable_deliverable(
        session_name="PowerBI-2",
        user_input="Create an options paper for Power BI reporting.",
        final_output=final_output,
        registry_dir=settings.registry_dir,
    )

    artefact = settings.workspace_dir / "tasks/PowerBI-2/artefacts/option-paper.md"
    manifest = settings.workspace_dir / "tasks/PowerBI-2/.crisai/task.json"
    assert artefact.is_file()
    assert "Saved artefact" in result
    assert "workspace/tasks/PowerBI-2/artefacts/option-paper.md" in manifest.read_text(encoding="utf-8")


def test_validate_task_artefacts_reports_template_conformance_failures(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(artefact_lifecycle, "load_settings", lambda: settings)
    template_src = REPO_ROOT / "workspace/knowledge/reference/template/hld_generic.md"
    template = tmp_path / "workspace/knowledge/reference/template/hld_generic.md"
    template.parent.mkdir(parents=True)
    template.write_text(template_src.read_text(encoding="utf-8"), encoding="utf-8")
    path = tmp_path / "workspace/tasks/demo/artefacts/hld.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        (
            "---\n"
            "id: HLD-1\n"
            "title: Demo HLD\n"
            "type: high_level_design\n"
            "status: draft\n"
            "template_id: REF-TPL-HLD-GENERIC-001\n"
            "template_path: workspace/knowledge/reference/template/hld_generic.md\n"
            "---\n\n"
            "## Context\n\nOnly context.\n"
        ),
        encoding="utf-8",
    )

    warnings = artefact_lifecycle.validate_task_artefacts_for_request(
        user_input="Create a full HLD for Power BI reporting.",
        paths=["workspace/tasks/demo/artefacts/hld.md"],
        root_dir=tmp_path,
    )

    assert any("Purpose" in warning for warning in warnings)
    assert any("Mermaid" in warning for warning in warnings)
