from __future__ import annotations

import os
import time
from dataclasses import dataclass

from fastapi.testclient import TestClient

from fastapi import HTTPException

from crisai.apps.web import (
    _collect_stage_outputs,
    _select_latest_run,
    _to_http_exception,
    _trace_line_to_stage_output,
    app,
)


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
    out = _trace_line_to_stage_output(entry)
    assert out is not None
    assert out["key"] == "retrieval_planner"
    assert out["agent_id"] == "retrieval_planner"
    assert out["event_type"] == "stage_output"
    assert out["content"] == "Listed 3 matching files."


def test_trace_line_ignores_unrelated_workflow_output():
    entry = {"event_type": "workflow_output", "stage": "OTHER", "agent_id": "retrieval_planner", "content": "x"}
    assert _trace_line_to_stage_output(entry) is None


def test_collect_stage_outputs_keeps_only_renderable_stage_events():
    entries = [
        {"event_type": "workflow_event", "stage": "WORKFLOW_START", "content": "start"},
        {"event_type": "stage_output", "stage": "RETRIEVAL_PLANNER OUTPUT", "content": "plan", "agent_id": "retrieval_planner"},
        {"event_type": "stage_skipped", "stage": "REVIEW_OUTPUT", "content": "skipped", "agent_id": "review"},
    ]

    result = _collect_stage_outputs(entries)

    assert result == [
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
    ]


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
    client = TestClient(app)

    response = client.post(
        "/api/run",
        json={
            "message": "hello",
            "mode": "auto",
            "agent": "auto",
            "review": False,
            "verbose": False,
            "session": "default",
        },
    )

    assert response.status_code == 200
    assert response.json()["final_output"] == "ok"
    assert response.json()["current_session"] == "default"
    assert len(response.json()["history"]) == 2
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
        lambda user_input, history: f"Conversation so far\\nUser: {user_input}",
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
    client = TestClient(app)

    response = client.get("/api/sessions")

    assert response.status_code == 200
    payload = response.json()
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
    client = TestClient(app)

    response = client.get("/api/sessions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_session"] == "newer"
    assert "newer" in payload["sessions"]
    assert payload["history"] == [{"role": "user", "content": "new"}]


def test_create_session_endpoint_sanitizes_and_returns_session(monkeypatch):
    monkeypatch.setattr("crisai.apps.web.load_history", lambda session_name: [])
    monkeypatch.setattr("crisai.apps.web.save_history", lambda session_name, history: None)
    monkeypatch.setattr("crisai.apps.web._list_session_names", lambda: ["default", "new_session"])
    client = TestClient(app)

    response = client.post("/api/sessions", json={"session": "new session"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_session"] == "new_session"
    assert "new_session" in payload["sessions"]


def test_get_session_endpoint_returns_specific_history(monkeypatch):
    monkeypatch.setattr("crisai.apps.web.load_history", lambda _name: [("user", "hello")])
    client = TestClient(app)

    response = client.get("/api/sessions/my-session")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_session"] == "my-session"
    assert payload["history"] == [{"role": "user", "content": "hello"}]

