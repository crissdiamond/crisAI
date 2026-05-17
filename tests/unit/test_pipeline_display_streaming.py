from __future__ import annotations

from types import SimpleNamespace

from crisai.cli.pipeline_display import _stream_event_delta


def test_stream_event_delta_extracts_visible_output_text() -> None:
    event = SimpleNamespace(
        data=SimpleNamespace(type="response.output_text.delta", delta="hello")
    )

    assert _stream_event_delta(event) == "hello"


def test_stream_event_delta_ignores_reasoning_text() -> None:
    event = SimpleNamespace(
        data=SimpleNamespace(type="response.reasoning_text.delta", delta="hidden")
    )

    assert _stream_event_delta(event) == ""
