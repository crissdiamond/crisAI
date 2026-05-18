from __future__ import annotations

from types import SimpleNamespace

import pytest

from crisai.cli import pipeline_display
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


@pytest.mark.anyio
async def test_streamed_agent_falls_back_when_openai_streaming_is_incompatible(monkeypatch) -> None:
    called = {"callback": False, "run_streamed": False}

    async def fake_run_agent_silently(agent, prompt: str) -> str:
        assert agent == "agent"
        assert prompt == "prompt"
        return "final"

    def fake_run_streamed(*args, **kwargs):
        called["run_streamed"] = True
        raise AssertionError("streaming should not be used")

    def callback(agent_id: str, delta: str) -> None:
        called["callback"] = True

    monkeypatch.setattr(pipeline_display, "_openai_streaming_construct_type_incompatible", lambda: True)
    monkeypatch.setattr(pipeline_display, "_run_agent_silently", fake_run_agent_silently)
    monkeypatch.setattr(pipeline_display.Runner, "run_streamed", fake_run_streamed)

    result = await pipeline_display._run_agent_streamed_silently("agent_id", "agent", "prompt", callback)

    assert result == "final"
    assert called == {"callback": False, "run_streamed": False}


@pytest.mark.anyio
async def test_streamed_agent_forwards_visible_deltas(monkeypatch) -> None:
    callbacks: list[tuple[str, str]] = []

    class FakeStreamedResult:
        final_output = "final"

        async def stream_events(self):
            yield SimpleNamespace(data=SimpleNamespace(type="response.output_text.delta", delta="hello"))
            yield SimpleNamespace(data=SimpleNamespace(type="response.reasoning_text.delta", delta="hidden"))

    def fake_run_streamed(agent, prompt: str, *, max_turns: int):
        assert agent == "agent"
        assert prompt == "prompt"
        assert max_turns > 0
        return FakeStreamedResult()

    monkeypatch.setattr(pipeline_display, "_openai_streaming_construct_type_incompatible", lambda: False)
    monkeypatch.setattr(pipeline_display.Runner, "run_streamed", fake_run_streamed)

    result = await pipeline_display._run_agent_streamed_silently(
        "agent_id",
        "agent",
        "prompt",
        lambda agent_id, delta: callbacks.append((agent_id, delta)),
    )

    assert result == "final"
    assert callbacks == [("agent_id", "hello")]
