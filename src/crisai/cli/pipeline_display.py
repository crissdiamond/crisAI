"""Display wiring for the pipeline execution layer.

Isolates all direct display.py dependencies so that pipelines.py
can be import-tested and unit-tested without a terminal or Rich console.
"""

from __future__ import annotations

import io
import os
from contextlib import redirect_stderr, redirect_stdout

from agents import Runner

from crisai.logging_utils import get_logger

from .display import AgentDisplayManager, print_agent_output, sanitize_user_visible_text

__all__ = [
    "_DEFAULT_AGENT_MAX_TURNS",
    "_resolve_agent_max_turns",
    "_run_agent_silently",
    "_run_agent_with_progress",
    "print_agent_output",
    "sanitize_user_visible_text",
]

logger = get_logger(__name__)

_DEFAULT_AGENT_MAX_TURNS = 30


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


async def _run_agent_with_progress(agent_id: str, agent, prompt: str, topic: str = "Working...") -> str:
    """Run an agent and render its transient progress box."""
    with AgentDisplayManager(agent_id) as manager:
        manager.update(topic)
        result = await _run_agent_silently(agent, prompt)
    return result
