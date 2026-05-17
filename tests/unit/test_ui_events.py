from __future__ import annotations

from crisai.ui_events import make_ui_event


def test_make_ui_event_returns_shared_contract_payload() -> None:
    event = make_ui_event(
        "stage_output",
        run_id="run-1",
        session="default",
        status="running",
        title="Context retrieval",
        summary="Read sources.",
        content="Read two sources.",
        mode="pipeline",
        agent_id="context_retrieval",
        stage="CONTEXT OUTPUT",
        metadata={"source": "trace"},
    )

    payload = event.to_dict()

    assert payload["schema_version"] == "ui_event_v1"
    assert payload["event_type"] == "stage_output"
    assert payload["run_id"] == "run-1"
    assert payload["session"] == "default"
    assert payload["mode"] == "pipeline"
    assert payload["agent_id"] == "context_retrieval"
    assert payload["metadata"] == {"source": "trace"}
