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
    "reset_stage_stream_callback",
    "set_stage_stream_callback",
    "print_agent_output",
    "sanitize_user_visible_text",
]

logger = get_logger(__name__)

_DEFAULT_AGENT_MAX_TURNS = 30
StageStreamCallback = Callable[[str, str], None]
_STAGE_STREAM_CALLBACK: ContextVar[StageStreamCallback | None] = ContextVar(
    "crisai_stage_stream_callback",
    default=None,
)


def set_stage_stream_callback(callback: StageStreamCallback) -> Token[StageStreamCallback | None]:
    """Install a per-task callback for user-visible stage text deltas."""
    return _STAGE_STREAM_CALLBACK.set(callback)


def reset_stage_stream_callback(token: Token[StageStreamCallback | None]) -> None:
    """Restore the previous stage streaming callback."""
    _STAGE_STREAM_CALLBACK.reset(token)


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


async def _run_agent_streamed_silently(agent_id: str, agent, prompt: str, callback: StageStreamCallback) -> str:
    """Run an agent with token deltas forwarded to a UI callback."""
    if _openai_streaming_construct_type_incompatible():
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
