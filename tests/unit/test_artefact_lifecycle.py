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
    template = tmp_path / "workspace/knowledge/reference/template/custom-template.md"
    template.parent.mkdir(parents=True)
    template.write_text(
        (
            "---\n"
            "id: REF-TPL-CUSTOM-001\n"
            "title: Custom template\n"
            "type: custom_deliverable\n"
            "status: approved\n"
            "template_conformance:\n"
            "  placeholder_policy: error\n"
            "---\n\n"
            "## Summary\nContent.\n\n"
            "## Evidence\nContent.\n\n"
            "## Decision\nContent.\n"
        ),
        encoding="utf-8",
    )
    path = tmp_path / "workspace/tasks/demo/artefacts/custom-deliverable.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        (
            "---\n"
            "id: CUSTOM-1\n"
            "title: Demo Custom Deliverable\n"
            "type: custom_deliverable\n"
            "status: draft\n"
            "template_id: REF-TPL-CUSTOM-001\n"
            "template_path: workspace/knowledge/reference/template/custom-template.md\n"
            "---\n\n"
            "## Summary\n\n[value] placeholder remains.\n"
        ),
        encoding="utf-8",
    )

    warnings = artefact_lifecycle.validate_task_artefacts_for_request(
        user_input="Create a templated deliverable.",
        paths=["workspace/tasks/demo/artefacts/custom-deliverable.md"],
        root_dir=tmp_path,
    )

    assert any("Evidence" in warning for warning in warnings)
    assert any("placeholder" in warning for warning in warnings)
