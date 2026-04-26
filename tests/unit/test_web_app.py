from __future__ import annotations

from fastapi.testclient import TestClient

from crisai.web.app import _collect_stage_outputs, _select_latest_run, app


def test_select_latest_run_filters_by_last_run_id():
    entries = [
        {"run_id": "run-1", "event_type": "stage_output", "stage": "DISCOVERY", "content": "a"},
        {"run_id": "run-2", "event_type": "stage_output", "stage": "DESIGN", "content": "b"},
        {"run_id": "run-2", "event_type": "stage_output", "stage": "FINAL", "content": "c"},
    ]

    selected = _select_latest_run(entries)

    assert len(selected) == 2
    assert all(item.get("run_id") == "run-2" for item in selected)


def test_collect_stage_outputs_keeps_only_renderable_stage_events():
    entries = [
        {"event_type": "workflow_event", "stage": "WORKFLOW_START", "content": "start"},
        {"event_type": "stage_output", "stage": "DISCOVERY_OUTPUT", "content": "discovery", "agent_id": "discovery"},
        {"event_type": "stage_skipped", "stage": "REVIEW_OUTPUT", "content": "skipped", "agent_id": "review"},
    ]

    result = _collect_stage_outputs(entries)

    assert result == [
        {
            "agent_id": "discovery",
            "stage": "DISCOVERY_OUTPUT",
            "event_type": "stage_output",
            "content": "discovery",
        },
        {
            "agent_id": "review",
            "stage": "REVIEW_OUTPUT",
            "event_type": "stage_skipped",
            "content": "skipped",
        },
    ]


def test_run_endpoint_returns_execution_payload(monkeypatch):
    async def fake_execute(_payload):
        return {
            "decision": {"mode": "pipeline", "agent": "discovery"},
            "final_output": "ok",
            "stage_outputs": [{"agent_id": "discovery", "stage": "DISCOVERY_OUTPUT", "event_type": "stage_output", "content": "x"}],
        }

    monkeypatch.setattr("crisai.web.app._execute", fake_execute)
    client = TestClient(app)

    response = client.post(
        "/api/run",
        json={
            "message": "hello",
            "mode": "auto",
            "agent": "auto",
            "review": False,
            "verbose": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["final_output"] == "ok"

