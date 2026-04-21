from __future__ import annotations

from crisai.cli.session_store import HistoryEntry
from crisai.cli.text_loader import render_cli_text


def render_history(history: list[HistoryEntry]) -> str:
    """Renders chat history as a transcript for prompt wrapping."""
    if not history:
        return ""

    lines: list[str] = []
    for role, content in history:
        if role == "user":
            lines.append(f"User: {content}")
        else:
            lines.append(f"Assistant: {content}")

    return "\n\n".join(lines)


def build_chat_input(user_input: str, history: list[HistoryEntry]) -> str:
    """Builds the message passed to the agent runtime.

    Recent history is wrapped through the existing CLI template so the
    runtime behaviour remains unchanged.
    """
    if not history:
        return user_input

    transcript = render_history(history[-12:])
    return render_cli_text(
        "chat/history_wrapper.md",
        transcript=transcript,
        user_input=user_input,
    )
