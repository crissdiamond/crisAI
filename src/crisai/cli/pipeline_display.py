"""Display wiring for the pipeline execution layer.

Isolates all direct display.py dependencies so that pipelines.py
can be import-tested and unit-tested without a terminal or Rich console.
"""

from __future__ import annotations

import io
import os
import sys
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from contextvars import ContextVar, Token
from importlib.metadata import PackageNotFoundError, version

from agents import Runner

from crisai.logging_utils import get_logger

from .display import AgentDisplayManager, print_agent_output, sanitize_user_visible_text

__all__ = [
    "_DEFAULT_AGENT_MAX_TURNS",
    "_resolve_agent_max_turns",
    "_run_agent_silently",
    "_run_agent_with_progress",
    "reset_stage_observability_agent_id",
    "reset_stage_observability_callback",
    "reset_stage_stream_callback",
    "set_stage_observability_agent_id",
    "set_stage_observability_callback",
    "set_stage_stream_callback",
    "print_agent_output",
    "sanitize_user_visible_text",
]

logger = get_logger(__name__)

_DEFAULT_AGENT_MAX_TURNS = 30
StageStreamCallback = Callable[[str, str], None]
StageObservabilityCallback = Callable[[str, str, dict[str, object]], None]
_STAGE_STREAM_CALLBACK: ContextVar[StageStreamCallback | None] = ContextVar(
    "crisai_stage_stream_callback",
    default=None,
)
_STAGE_OBSERVABILITY_CALLBACK: ContextVar[StageObservabilityCallback | None] = ContextVar(
    "crisai_stage_observability_callback",
    default=None,
)
_STAGE_OBSERVABILITY_AGENT_ID: ContextVar[str | None] = ContextVar(
    "crisai_stage_observability_agent_id",
    default=None,
)


def set_stage_stream_callback(callback: StageStreamCallback) -> Token[StageStreamCallback | None]:
    """Install a per-task callback for user-visible stage text deltas."""
    return _STAGE_STREAM_CALLBACK.set(callback)


def reset_stage_stream_callback(token: Token[StageStreamCallback | None]) -> None:
    """Restore the previous stage streaming callback."""
    _STAGE_STREAM_CALLBACK.reset(token)


def set_stage_observability_callback(
    callback: StageObservabilityCallback,
) -> Token[StageObservabilityCallback | None]:
    """Install a per-stage callback for structured observability metadata."""
    return _STAGE_OBSERVABILITY_CALLBACK.set(callback)


def reset_stage_observability_callback(token: Token[StageObservabilityCallback | None]) -> None:
    """Restore the previous stage observability callback."""
    _STAGE_OBSERVABILITY_CALLBACK.reset(token)


def set_stage_observability_agent_id(agent_id: str) -> Token[str | None]:
    """Record the currently executing stage for observability callbacks."""
    return _STAGE_OBSERVABILITY_AGENT_ID.set(agent_id)


def reset_stage_observability_agent_id(token: Token[str | None]) -> None:
    """Restore the previous stage observability agent id."""
    _STAGE_OBSERVABILITY_AGENT_ID.reset(token)


def _emit_stage_observability(event_type: str, metadata: dict[str, object]) -> None:
    """Emit structured stage observability if the runtime installed a callback."""
    callback = _STAGE_OBSERVABILITY_CALLBACK.get()
    agent_id = _STAGE_OBSERVABILITY_AGENT_ID.get()
    if callback is None or not agent_id or not metadata:
        return
    try:
        callback(agent_id, event_type, metadata)
    except Exception:
        logger.debug("Stage observability callback failed; continuing agent run.", exc_info=True)


def _resolve_agent_max_turns() -> int:
    """Return the max turns used for each agent run.

    The OpenAI Agents SDK defaults to 10 turns, which can interrupt longer
    multi-step prompts. This resolver provides a safer default while allowing
    environment overrides.

    Returns:
        A positive integer max-turn value.
    """
    raw_value = os.getenv("CRISAI_AGENT_MAX_TURNS", str(_DEFAULT_AGENT_MAX_TURNS))
    try:
        parsed = int(raw_value)
    except ValueError:
        return _DEFAULT_AGENT_MAX_TURNS
    return parsed if parsed > 0 else _DEFAULT_AGENT_MAX_TURNS


async def _run_agent_silently(agent, prompt: str) -> str:
    """Run an agent while suppressing direct stdout/stderr noise only.

    Logging is handled centrally by the application logging configuration.
    """
    result = None
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = await Runner.run(
                agent,
                prompt,
                max_turns=_resolve_agent_max_turns(),
            )
    except Exception:
        logger.exception("Agent execution failed.")
        raise
    _emit_stage_observability("provider_usage", _provider_usage_metadata(result))
    return str(result.final_output)


def _stream_event_delta(event: object) -> str:
    """Extract visible assistant text from an Agents SDK stream event."""
    data = getattr(event, "data", None)
    event_type = str(getattr(data, "type", ""))
    if event_type not in {"response.output_text.delta", "response.refusal.delta"}:
        return ""
    delta = getattr(data, "delta", "")
    return delta if isinstance(delta, str) else ""


def _parse_version(value: str) -> tuple[int, int, int]:
    """Return the first three numeric version parts from a package version."""
    parts: list[int] = []
    for raw_part in value.split("."):
        digits = ""
        for char in raw_part:
            if not char.isdigit():
                break
            digits += char
        if digits == "":
            break
        parts.append(int(digits))
        if len(parts) == 3:
            break
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def _openai_streaming_construct_type_incompatible() -> bool:
    """Return whether OpenAI streaming response parsing is known to fail."""
    if sys.version_info < (3, 14):
        return False
    try:
        openai_version = version("openai")
    except PackageNotFoundError:
        return False
    return _parse_version(openai_version) <= (1, 109, 1)


def _streaming_fallback_metadata() -> dict[str, object]:
    """Return trace-safe metadata for the known streaming fallback path."""
    try:
        openai_version = version("openai")
    except PackageNotFoundError:
        openai_version = ""
    return {
        "streaming": {
            "attempted": True,
            "fallback": True,
            "fallback_reason": "openai_streaming_construct_type_incompatible",
            "provider": "openai",
            "openai_version": openai_version,
            "python_version": ".".join(str(part) for part in sys.version_info[:3]),
        }
    }


def _provider_usage_metadata(result: object) -> dict[str, object]:
    """Extract provider usage counters only when the SDK returned usage data."""
    raw_responses = getattr(result, "raw_responses", None)
    if not isinstance(raw_responses, list) or not raw_responses:
        return {}
    totals = {
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
        "reasoning_tokens": 0,
    }
    has_usage = False
    for response in raw_responses:
        usage = getattr(response, "usage", None)
        if usage is None:
            continue
        has_usage = True
        totals["requests"] += int(getattr(usage, "requests", 0) or 0)
        totals["input_tokens"] += int(getattr(usage, "input_tokens", 0) or 0)
        totals["output_tokens"] += int(getattr(usage, "output_tokens", 0) or 0)
        totals["total_tokens"] += int(getattr(usage, "total_tokens", 0) or 0)
        input_details = getattr(usage, "input_tokens_details", None)
        output_details = getattr(usage, "output_tokens_details", None)
        totals["cached_tokens"] += int(getattr(input_details, "cached_tokens", 0) or 0)
        totals["reasoning_tokens"] += int(getattr(output_details, "reasoning_tokens", 0) or 0)
    if not has_usage:
        return {}
    provider_usage = {key: value for key, value in totals.items() if value > 0}
    return {"provider_usage": provider_usage} if provider_usage else {}


async def _run_agent_streamed_silently(agent_id: str, agent, prompt: str, callback: StageStreamCallback) -> str:
    """Run an agent with token deltas forwarded to a UI callback."""
    if _openai_streaming_construct_type_incompatible():
        _emit_stage_observability("streaming_fallback", _streaming_fallback_metadata())
        logger.warning(
            "OpenAI streamed response parsing is incompatible with this Python/OpenAI SDK combination; "
            "falling back to non-streamed agent execution."
        )
        return await _run_agent_silently(agent, prompt)

    result = None
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = Runner.run_streamed(
                agent,
                prompt,
                max_turns=_resolve_agent_max_turns(),
            )
            async for event in result.stream_events():
                delta = _stream_event_delta(event)
                if not delta:
                    continue
                try:
                    callback(agent_id, delta)
                except Exception:
                    logger.debug("Stage stream callback failed; continuing agent run.", exc_info=True)
    except Exception:
        logger.exception("Agent execution failed.")
        raise
    _emit_stage_observability("provider_usage", _provider_usage_metadata(result))
    return str(result.final_output)


async def _run_agent_with_progress(agent_id: str, agent, prompt: str, topic: str = "Working...") -> str:
    """Run an agent and render its transient progress box."""
    with AgentDisplayManager(agent_id) as manager:
        manager.update(topic)
        callback = _STAGE_STREAM_CALLBACK.get()
        if callback is None:
            result = await _run_agent_silently(agent, prompt)
        else:
            result = await _run_agent_streamed_silently(agent_id, agent, prompt, callback)
    return result
