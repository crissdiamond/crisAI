from __future__ import annotations

import os
import time
from dataclasses import dataclass

import pytest
from fastapi import HTTPException

from crisai.apps.web import (
    RunRequest,
    SessionCreateRequest,
    WorkspaceFileSaveRequest,
    _collect_stage_outputs,
    _evict_old_jobs,
    _select_latest_run,
    _to_http_exception,
    _trace_line_to_stage_output,
    create_session,
    get_session,
    list_sessions,
    run,
    save_workspace_file,
    workspace_file,
    workspace_tree,
)


@pytest.fixture(autouse=True)
def clear_run_jobs():
    from crisai.apps import web as web_mod

    web_mod._RUN_JOBS.clear()
    yield
    web_mod._RUN_JOBS.clear()


def test_select_latest_run_filters_by_last_run_id():
    entries = [
        {"run_id": "run-1", "event_type": "stage_output", "stage": "RETRIEVAL_PLANNER OUTPUT", "content": "a"},
        {"run_id": "run-2", "event_type": "stage_output", "stage": "DESIGN", "content": "b"},
        {"run_id": "run-2", "event_type": "stage_output", "stage": "FINAL", "content": "c"},
    ]

    selected = _select_latest_run(entries)

    assert len(selected) == 2
    assert all(item.get("run_id") == "run-2" for item in selected)


def test_trace_line_maps_single_agent_workflow_output_to_agent_tab():
    """Single-agent runs trace FINAL_OUTPUT as workflow_output; UI needs a stage row."""
    entry = {
        "event_type": "workflow_output",
        "stage": "FINAL_OUTPUT",
        "agent_id": "retrieval_planner",
        "content": "Listed 3 matching files.",
        "run_id": "run-x",
    }
    out = _trace_line_to_stage_output(entry, verbose=True)
    assert out is not None
    assert out["key"] == "retrieval_planner"
    assert out["agent_id"] == "retrieval_planner"
    assert out["event_type"] == "stage_output"
    assert out["content"] == "Listed 3 matching files."


def test_trace_line_sanitizes_single_agent_workflow_output():
    entry = {
        "event_type": "workflow_output",
        "stage": "FINAL_OUTPUT",
        "agent_id": "retrieval_planner",
        "content": 'Found files.\n\n{"schema_version": "evidence_bundle_v1", "request": "x", "items": []}',
        "run_id": "run-x",
    }
    out = _trace_line_to_stage_output(entry, verbose=True)
    assert out is not None
    assert out["content"] == "Found files."


def test_trace_line_maps_stage_error_to_agent_tab():
    entry = {
        "event_type": "stage_error",
        "stage": "RETRIEVAL_PLANNER OUTPUT_ERROR",
        "agent_id": "retrieval_planner",
        "content": "Stage retrieval_planner returned empty output.",
        "run_id": "run-x",
    }

    out = _trace_line_to_stage_output(entry, verbose=True)

    assert out is not None
    assert out["key"] == "retrieval_planner"
    assert out["agent_id"] == "retrieval_planner"
    assert out["event_type"] == "stage_error"
    assert out["content"] == "Stage retrieval_planner returned empty output."


def test_trace_line_maps_stage_start_to_agent_tab():
    entry = {
        "event_type": "stage_start",
        "stage": "CONTEXT OUTPUT_START",
        "agent_id": "context_synthesizer",
        "content": "Starting stage for context_synthesizer.",
        "run_id": "run-x",
    }

    out = _trace_line_to_stage_output(entry, verbose=True)

    assert out is not None
    assert out["key"] == "context_synthesizer"
    assert out["agent_id"] == "context_synthesizer"
    assert out["event_type"] == "stage_start"
    assert out["content"] == "Starting stage for context_synthesizer."


def test_trace_line_ignores_unrelated_workflow_output():
    entry = {"event_type": "workflow_output", "stage": "OTHER", "agent_id": "retrieval_planner", "content": "x"}
    assert _trace_line_to_stage_output(entry) is None


def test_collect_stage_outputs_keeps_only_renderable_stage_events():
    entries = [
        {"event_type": "workflow_event", "stage": "WORKFLOW_START", "content": "start"},
        {"event_type": "stage_start", "stage": "CONTEXT OUTPUT_START", "content": "starting", "agent_id": "context_synthesizer"},
        {"event_type": "stage_output", "stage": "RETRIEVAL_PLANNER OUTPUT", "content": "plan", "agent_id": "retrieval_planner"},
        {"event_type": "stage_skipped", "stage": "REVIEW_OUTPUT", "content": "skipped", "agent_id": "review"},
        {"event_type": "stage_error", "stage": "SUMMARY OUTPUT_ERROR", "content": "empty", "agent_id": "summary"},
    ]

    result = _collect_stage_outputs(entries, verbose=True)

    assert result == [
        {
            "agent_id": "context_synthesizer",
            "stage": "CONTEXT OUTPUT_START",
            "event_type": "stage_start",
            "content": "starting",
        },
        {
            "agent_id": "retrieval_planner",
            "stage": "RETRIEVAL_PLANNER OUTPUT",
            "event_type": "stage_output",
            "content": "plan",
        },
        {
            "agent_id": "review",
            "stage": "REVIEW_OUTPUT",
            "event_type": "stage_skipped",
            "content": "skipped",
        },
        {
            "agent_id": "summary",
            "stage": "SUMMARY OUTPUT_ERROR",
            "event_type": "stage_error",
            "content": "empty",
        },
    ]


def test_collect_stage_outputs_sanitizes_machine_json():
    entries = [
        {
            "event_type": "stage_output",
            "stage": "RETRIEVAL_PLANNER OUTPUT",
            "content": 'handoff\n```json\n{"topics_activated": ["intent.summary"]}\n```',
            "agent_id": "retrieval_planner",
        },
    ]

    result = _collect_stage_outputs(entries, verbose=True)

    assert result[0]["content"] == "handoff"


def test_collect_stage_outputs_defaults_to_clean_stage_summary():
    entries = [
        {
            "event_type": "stage_output",
            "stage": "CONTEXT RETRIEVAL OUTPUT",
            "content": 'Retrieved the deck.\n```json\n{"schema_version": "evidence_bundle_v1", "request": "x", "items": []}\n```',
            "agent_id": "context_retrieval",
        },
    ]

    result = _collect_stage_outputs(entries)

    assert result[0]["content"].startswith("**Summary:**")
    assert "Retrieved the deck" in result[0]["content"]
    assert "evidence_bundle_v1" not in result[0]["content"]


def test_run_endpoint_returns_execution_payload(monkeypatch):
    saved = {}

    async def fake_execute(_payload):
        return {
            "decision": {"mode": "pipeline", "agent": "retrieval_planner"},
            "final_output": "ok",
            "stage_outputs": [{"agent_id": "retrieval_planner", "stage": "RETRIEVAL_PLANNER OUTPUT", "event_type": "stage_output", "content": "x"}],
        }

    monkeypatch.setattr("crisai.apps.web.load_history", lambda session_name: [])
    monkeypatch.setattr(
        "crisai.apps.web.save_history",
        lambda session_name, history: saved.update({"session": session_name, "history": history}),
    )
    monkeypatch.setattr("crisai.apps.web._execute", fake_execute)

    response = run(
        RunRequest(
            message="hello",
            mode="auto",
            agent="auto",
            review=False,
            verbose=False,
            session="default",
        )
    )
    from crisai.apps import web as web_mod

    payload = web_mod._run_async(response)

    assert payload["final_output"] == "ok"
    assert payload["current_session"] == "default"
    assert len(payload["history"]) == 2
    assert saved["session"] == "default"
    assert saved["history"][0] == ("user", "hello")
    assert saved["history"][1] == ("assistant", "ok")


def test_execute_wraps_message_with_session_history(monkeypatch, tmp_path):
    captured: dict[str, str] = {}

    @dataclass
    class _Decision:
        mode: str = "pipeline"
        agent: str = "retrieval_planner"
        confidence: float = 1.0
        reason: str = "test"

    monkeypatch.setattr(
        "crisai.apps.web._trace_file_path",
        lambda: tmp_path / "trace.jsonl",
    )
    monkeypatch.setattr("crisai.apps.web._resolve_decision", lambda payload: _Decision())
    monkeypatch.setattr(
        "crisai.apps.web.load_history",
        lambda session_name: [("user", "previous question"), ("assistant", "previous answer")],
    )
    monkeypatch.setattr(
        "crisai.apps.web.build_chat_input",
        lambda user_input, history, session_name=None: f"Conversation so far\\nUser: {user_input}",
    )

    async def _fake_run_with_routing(**kwargs):
        captured["message"] = kwargs["message"]
        return "ok"

    monkeypatch.setattr("crisai.apps.web._run_with_routing", _fake_run_with_routing)

    class _Payload:
        message = "new prompt"
        mode = "auto"
        agent = "auto"
        review = False
        verbose = False
        session = "default"

    from crisai.apps import web as web_mod

    result = web_mod._run_async(web_mod._execute(_Payload()))
    assert result["final_output"] == "ok"
    assert captured["message"].startswith("Conversation so far")


def test_run_job_wraps_message_with_session_history(monkeypatch):
    captured: dict[str, str] = {}
    saved: dict[str, object] = {}

    monkeypatch.setattr(
        "crisai.apps.web.load_history",
        lambda session_name: [("user", "prior user"), ("assistant", "prior assistant")],
    )
    monkeypatch.setattr(
        "crisai.apps.web.build_chat_input",
        lambda user_input, history, session_name=None: f"Wrapped history\\nUser: {user_input}",
    )
    monkeypatch.setattr(
        "crisai.apps.web.save_history",
        lambda session_name, history: saved.update({"session": session_name, "history": history}),
    )
    monkeypatch.setattr("crisai.apps.web.update_session_memory", lambda session_name, history: None)

    async def _fake_run_with_routing(**kwargs):
        captured["message"] = kwargs["message"]
        captured["intent"] = kwargs["user_intent_message"]
        return "ok"

    monkeypatch.setattr("crisai.apps.web._run_with_routing", _fake_run_with_routing)

    @dataclass
    class _Payload:
        message: str = "fresh request"
        mode: str = "auto"
        agent: str = "auto"
        review: bool = False
        verbose: bool = False
        session: str = "default"

    from crisai.apps import web as web_mod

    web_mod._RUN_JOBS.clear()
    web_mod._RUN_JOBS["job-1"] = {"status": "running"}
    result = web_mod._run_async(web_mod._run_job("job-1", _Payload(), decision=object()))

    assert result is None
    assert captured["message"].startswith("Wrapped history")
    assert captured["intent"] == "fresh request"
    assert saved["session"] == "default"
    assert saved["history"] == [
        ("user", "prior user"),
        ("assistant", "prior assistant"),
        ("user", "fresh request"),
        ("assistant", "ok"),
    ]


def test_to_http_exception_maps_max_turns_to_422():
    error = Exception("Error: Max turns (10) exceeded")
    http_error = _to_http_exception(error)

    assert isinstance(http_error, HTTPException)
    assert http_error.status_code == 422
    assert "Increase CRISAI_AGENT_MAX_TURNS" in str(http_error.detail)


def test_list_sessions_endpoint_returns_default_history(monkeypatch):
    monkeypatch.setattr("crisai.apps.web._list_session_names", lambda: ["default", "design"])
    monkeypatch.setattr("crisai.apps.web._session_name_newest_by_mtime", lambda: None)
    monkeypatch.setattr(
        "crisai.apps.web.load_history",
        lambda session_name: [("user", "u1"), ("assistant", "a1")] if session_name == "default" else [],
    )

    payload = list_sessions()
    assert payload["current_session"] == "default"
    assert payload["sessions"] == ["default", "design"]
    assert payload["history"] == [{"role": "user", "content": "u1"}, {"role": "assistant", "content": "a1"}]


def test_list_sessions_selects_session_with_newest_json_mtime(tmp_path, monkeypatch):
    monkeypatch.setattr("crisai.apps.web.session_dir", lambda: tmp_path)
    (tmp_path / "older.json").write_text("[]")
    (tmp_path / "newer.json").write_text("[]")
    base = time.time()
    os.utime(tmp_path / "older.json", (base - 200, base - 200))
    os.utime(tmp_path / "newer.json", (base, base))

    monkeypatch.setattr(
        "crisai.apps.web.load_history",
        lambda session_name: (
            [("user", "old")] if session_name == "older" else [("user", "new")]
        ),
    )

    payload = list_sessions()
    assert payload["current_session"] == "newer"
    assert "newer" in payload["sessions"]
    assert payload["history"] == [{"role": "user", "content": "new"}]


def test_create_session_endpoint_sanitizes_and_returns_session(monkeypatch):
    monkeypatch.setattr("crisai.apps.web.load_history", lambda session_name: [])
    monkeypatch.setattr("crisai.apps.web.save_history", lambda session_name, history: None)
    monkeypatch.setattr("crisai.apps.web._list_session_names", lambda: ["default", "new_session"])

    payload = create_session(SessionCreateRequest(session="new session"))
    assert payload["current_session"] == "new_session"
    assert "new_session" in payload["sessions"]


def test_get_session_endpoint_returns_specific_history(monkeypatch):
    monkeypatch.setattr("crisai.apps.web.load_history", lambda _name: [("user", "hello")])

    payload = get_session("my-session")
    assert payload["current_session"] == "my-session"
    assert payload["history"] == [{"role": "user", "content": "hello"}]


def test_evict_old_jobs_removes_oldest_completed_beyond_limit():
    from crisai.apps import web as web_mod

    for i in range(22):
        web_mod._RUN_JOBS[f"job-{i}"] = {"status": "completed"}
    web_mod._RUN_JOBS["running-1"] = {"status": "running"}

    _evict_old_jobs(max_completed=20)

    completed = [jid for jid, j in web_mod._RUN_JOBS.items() if j["status"] == "completed"]
    assert len(completed) == 20
    assert "running-1" in web_mod._RUN_JOBS
    assert "job-0" not in web_mod._RUN_JOBS
    assert "job-1" not in web_mod._RUN_JOBS
    assert "job-21" in web_mod._RUN_JOBS


def test_evict_old_jobs_noop_when_under_limit():
    from crisai.apps import web as web_mod

    for i in range(5):
        web_mod._RUN_JOBS[f"job-{i}"] = {"status": "completed" if i % 2 == 0 else "failed"}

    _evict_old_jobs(max_completed=20)

    assert len(web_mod._RUN_JOBS) == 5


def test_workspace_tree_lists_knowledge_files(tmp_path, monkeypatch):
    from crisai.apps import web as web_mod

    workspace = tmp_path / "workspace"
    knowledge = workspace / "knowledge"
    knowledge.mkdir(parents=True)
    (knowledge / "standard.md").write_text("# Standard\n", encoding="utf-8")
    monkeypatch.setattr(web_mod, "load_settings", lambda: type("S", (), {"workspace_dir": workspace, "registry_dir": tmp_path})())

    payload = workspace_tree("knowledge")

    assert payload["root"] == "knowledge"
    assert payload["files"][0]["path"] == "knowledge/standard.md"
    assert payload["files"][0]["editable"] is True


def test_workspace_file_read_and_save_markdown(tmp_path, monkeypatch):
    from crisai.apps import web as web_mod

    workspace = tmp_path / "workspace"
    path = workspace / "tasks/demo/artefacts/design.md"
    path.parent.mkdir(parents=True)
    path.write_text("# Draft\n", encoding="utf-8")
    monkeypatch.setattr(web_mod, "load_settings", lambda: type("S", (), {"workspace_dir": workspace, "registry_dir": tmp_path})())

    read_payload = workspace_file("tasks/demo/artefacts/design.md")
    assert read_payload["content"] == "# Draft\n"

    save_payload = save_workspace_file(
        WorkspaceFileSaveRequest(path="tasks/demo/artefacts/design.md", content="# Updated\n")
    )

    assert save_payload["saved"] is True
    assert path.read_text(encoding="utf-8") == "# Updated\n"


def test_workspace_file_rejects_path_traversal(tmp_path, monkeypatch):
    from crisai.apps import web as web_mod

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(web_mod, "load_settings", lambda: type("S", (), {"workspace_dir": workspace, "registry_dir": tmp_path})())

    with pytest.raises(HTTPException) as exc_info:
        workspace_file("../outside.md")

    assert exc_info.value.status_code == 400
