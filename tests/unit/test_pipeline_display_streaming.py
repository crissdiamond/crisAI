from __future__ import annotations

from types import SimpleNamespace

import pytest

from crisai.cli import pipeline_display
from crisai.cli.pipeline_display import (
    _emit_stage_observability,
    _provider_usage_metadata,
    _stream_event_delta,
    _streaming_fallback_metadata,
    reset_stage_observability_agent_id,
    reset_stage_observability_callback,
    set_stage_observability_agent_id,
    set_stage_observability_callback,
)


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
    observability: list[tuple[str, str, dict[str, object]]] = []

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
    agent_token = set_stage_observability_agent_id("agent_id")
    callback_token = set_stage_observability_callback(
        lambda agent_id, event_type, metadata: observability.append((agent_id, event_type, metadata))
    )

    try:
        result = await pipeline_display._run_agent_streamed_silently("agent_id", "agent", "prompt", callback)
    finally:
        reset_stage_observability_callback(callback_token)
        reset_stage_observability_agent_id(agent_token)

    assert result == "final"
    assert called == {"callback": False, "run_streamed": False}
    assert observability[0][0] == "agent_id"
    assert observability[0][1] == "streaming_fallback"
    assert observability[0][2]["streaming"]["fallback"] is True
    assert observability[0][2]["streaming"]["fallback_reason"] == "openai_streaming_construct_type_incompatible"


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


def test_provider_usage_metadata_is_absent_without_raw_usage() -> None:
    assert _provider_usage_metadata(SimpleNamespace(raw_responses=[])) == {}
    assert _provider_usage_metadata(SimpleNamespace(raw_responses=[SimpleNamespace(usage=None)])) == {}
    assert _provider_usage_metadata(SimpleNamespace(raw_responses=[SimpleNamespace(usage=SimpleNamespace())])) == {}


def test_streaming_fallback_metadata_excludes_raw_provider_payloads() -> None:
    metadata = _streaming_fallback_metadata()

    assert metadata["streaming"]["attempted"] is True
    assert metadata["streaming"]["fallback"] is True
    assert metadata["streaming"]["fallback_reason"] == "openai_streaming_construct_type_incompatible"
    assert "raw" not in metadata["streaming"]
    assert "payload" not in metadata["streaming"]


def test_stage_observability_requires_callback_and_agent_context() -> None:
    observed: list[tuple[str, str, dict[str, object]]] = []

    _emit_stage_observability("provider_usage", {"provider_usage": {"total_tokens": 1}})
    callback_token = set_stage_observability_callback(
        lambda agent_id, event_type, metadata: observed.append((agent_id, event_type, metadata))
    )
    try:
        _emit_stage_observability("provider_usage", {"provider_usage": {"total_tokens": 2}})
        agent_token = set_stage_observability_agent_id("summary")
        try:
            _emit_stage_observability("provider_usage", {"provider_usage": {"total_tokens": 3}})
        finally:
            reset_stage_observability_agent_id(agent_token)
        _emit_stage_observability("provider_usage", {"provider_usage": {"total_tokens": 4}})
    finally:
        reset_stage_observability_callback(callback_token)

    assert observed == [("summary", "provider_usage", {"provider_usage": {"total_tokens": 3}})]


def test_provider_usage_metadata_includes_only_returned_counters() -> None:
    usage = SimpleNamespace(
        requests=1,
        input_tokens=12,
        output_tokens=5,
        total_tokens=17,
        input_tokens_details=SimpleNamespace(cached_tokens=3),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )

    assert _provider_usage_metadata(SimpleNamespace(raw_responses=[SimpleNamespace(usage=usage)])) == {
        "provider_usage": {
            "requests": 1,
            "input_tokens": 12,
            "output_tokens": 5,
            "total_tokens": 17,
            "cached_tokens": 3,
        }
    }
