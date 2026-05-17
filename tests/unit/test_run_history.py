from __future__ import annotations

from pathlib import Path

import pytest

from crisai.apps import run_history


def _settings(tmp_path: Path):
    return type("S", (), {"workspace_dir": tmp_path / "workspace", "registry_dir": tmp_path})()


@pytest.fixture()
def run_history_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("crisai.cli.session_store.load_settings", lambda: _settings(tmp_path))
    return tmp_path / "workspace"


def _snapshot(run_id: str, *, session: str = "demo", updated_at: str = "2026-05-17T10:00:00Z") -> dict:
    return {
        "schema_version": "ui_run_state_v1",
        "run_id": run_id,
        "session": session,
        "status": "completed",
        "decision": {"mode": "single", "agent": "design"},
        "expected_stages": [{"key": "design", "label": "Design"}],
        "events": [
            {
                "schema_version": "ui_event_v1",
                "event_type": "stage_output",
                "run_id": run_id,
                "timestamp": "2026-05-17T09:59:00Z",
                "session": session,
                "status": "completed",
                "title": "Design",
                "summary": "Drafted",
                "content": "Drafted output",
                "verbose_content": "Drafted output",
                "mode": "single",
                "agent_id": "design",
                "stage": "design",
                "metadata": {},
            }
        ],
        "final_output": "Final recommendation\nKeep it simple.",
        "error": "",
        "metadata": {
            "created_at": "2026-05-17T09:58:00Z",
            "updated_at": updated_at,
            "completed_at": updated_at,
            "message_summary": "propose a design",
            "request_contract": {"primary_intent": "design"},
        },
    }


def test_persist_run_snapshot_writes_detail_and_lists_newest_first(run_history_workspace: Path) -> None:
    run_history.persist_run_snapshot(_snapshot("older", updated_at="2026-05-17T10:00:00Z"))
    run_history.persist_run_snapshot(_snapshot("newer", updated_at="2026-05-17T11:00:00Z"))

    response = run_history.build_run_history_response("demo", limit=20)

    assert response["schema_version"] == "ui_run_history_v1"
    assert response["session"] == "demo"
    assert [item["run_id"] for item in response["runs"]] == ["newer", "older"]
    assert [item["display_order"] for item in response["runs"]] == [1, 2]
    assert response["runs"][0]["stage_count"] == 1
    assert response["runs"][0]["final_answer_summary"] == "Final recommendation"
    detail = run_history.load_run_detail("demo", "newer")
    assert detail is not None
    assert detail["metadata"]["request_contract"]["primary_intent"] == "design"
    assert detail["events"][0]["event_type"] == "stage_output"


def test_run_history_retains_latest_fifty_terminal_runs(run_history_workspace: Path) -> None:
    for index in range(55):
        run_history.persist_run_snapshot(
            _snapshot(f"run{index}", updated_at=f"2026-05-17T10:{index:02d}:00Z")
        )

    response = run_history.build_run_history_response("demo", limit=50)

    assert len(response["runs"]) == 50
    assert response["runs"][0]["run_id"] == "run54"
    assert response["runs"][-1]["run_id"] == "run5"
    assert run_history.load_run_detail("demo", "run0") is None
    assert run_history.load_run_detail("demo", "run54") is not None


def test_run_history_rejects_unsafe_run_ids(run_history_workspace: Path) -> None:
    assert run_history.is_safe_run_id("abc123") is True
    assert run_history.is_safe_run_id("abc-123") is False
    assert run_history.is_safe_run_id("../abc") is False
    assert run_history.load_run_detail("demo", "../abc") is None
    with pytest.raises(ValueError):
        run_history.run_detail_file("demo", "../abc")


def test_run_history_rejects_non_terminal_snapshots(run_history_workspace: Path) -> None:
    snapshot = _snapshot("running")
    snapshot["status"] = "running"

    with pytest.raises(ValueError):
        run_history.persist_run_snapshot(snapshot)

    assert run_history.build_run_history_response("demo")["runs"] == []
    assert run_history.load_run_detail("demo", "running") is None


def test_run_history_reads_do_not_create_session_dirs(run_history_workspace: Path) -> None:
    response = run_history.build_run_history_response("missing session")
    detail = run_history.load_run_detail("missing session", "missing-run")

    assert response["runs"] == []
    assert detail is None
    assert not (run_history_workspace / "tasks" / "missing_session").exists()


def test_run_history_caps_persisted_content(run_history_workspace: Path) -> None:
    snapshot = _snapshot("large")
    snapshot["final_output"] = "x" * (run_history.MAX_FINAL_OUTPUT_CHARS + 100)
    snapshot["events"][0]["content"] = "y" * (run_history.MAX_EVENT_CONTENT_CHARS + 100)

    run_history.persist_run_snapshot(snapshot)
    detail = run_history.load_run_detail("demo", "large")

    assert detail is not None
    assert len(detail["final_output"]) == run_history.MAX_FINAL_OUTPUT_CHARS
    assert len(detail["events"][0]["content"]) == run_history.MAX_EVENT_CONTENT_CHARS


def test_run_history_caps_persisted_event_count(run_history_workspace: Path) -> None:
    snapshot = _snapshot("manyevents")
    base_event = snapshot["events"][0]
    snapshot["events"] = [
        {**base_event, "stage": f"stage{index}", "content": f"event {index}"}
        for index in range(run_history.MAX_EVENTS_PER_RUN + 5)
    ]

    run_history.persist_run_snapshot(snapshot)
    detail = run_history.load_run_detail("demo", "manyevents")

    assert detail is not None
    assert len(detail["events"]) == run_history.MAX_EVENTS_PER_RUN
    assert run_history.stage_count(detail["events"]) == run_history.MAX_EVENTS_PER_RUN


def test_atomic_write_failure_leaves_existing_detail_intact(
    run_history_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_history.persist_run_snapshot(_snapshot("atomic"))
    original = run_history.load_run_detail("demo", "atomic")
    assert original is not None

    def _fail_replace(self: Path, target: Path) -> None:
        raise OSError("replace failed")

    next_snapshot = _snapshot("atomic", updated_at="2026-05-17T11:00:00Z")
    next_snapshot["final_output"] = "changed"
    monkeypatch.setattr(Path, "replace", _fail_replace)

    with pytest.raises(OSError):
        run_history.persist_run_snapshot(next_snapshot)

    assert run_history.load_run_detail("demo", "atomic") == original
