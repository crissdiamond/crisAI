from __future__ import annotations

import json

from crisai.tracing import append_trace


def test_append_trace_redacts_read_handles_from_content_and_metadata(tmp_path):
    trace_file = tmp_path / "agent_trace.jsonl"

    append_trace(
        trace_file,
        "FINAL_OUTPUT",
        '{"source": {"read_handle": "sharepoint_doc:secret", "title": "Deck.pptx"}}',
        run_id="run-1",
        metadata={
            "artifacts": {
                "evidence_bundle_v1": {
                    "items": [
                        {
                            "source": {
                                "title": "Deck.pptx",
                                "read_handle": "sharepoint_doc:nested",
                            }
                        }
                    ]
                }
            }
        },
    )

    payload = json.loads(trace_file.read_text(encoding="utf-8"))

    assert "sharepoint_doc:secret" not in payload["content"]
    assert payload["metadata"]["artifacts"]["evidence_bundle_v1"]["items"][0]["source"] == {
        "title": "Deck.pptx"
    }
