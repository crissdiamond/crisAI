from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from crisai.config import load_settings


HistoryEntry = tuple[str, str]


def sanitize_session_name(session_name: str) -> str:
    """Return a filesystem-safe session name."""
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in session_name.strip())
    return safe or "default"


def cli_history_file(session_name: str | None = None) -> Path:
    """Returns the prompt-toolkit history file path for the CLI.

    When a session name is provided, command history is isolated per session.
    """
    settings = load_settings()
    if session_name:
        safe = sanitize_session_name(session_name)
        path = settings.workspace_dir / "chat_sessions" / f".cli_history_{safe}"
    else:
        path = settings.workspace_dir / ".cli_history"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def session_dir() -> Path:
    """Returns the directory used to persist named chat sessions."""
    settings = load_settings()
    path = settings.workspace_dir / "chat_sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def session_file(session_name: str) -> Path:
    """Builds a safe file path for a named chat session.

    Args:
        session_name: User-provided session name.

    Returns:
        Path to the JSON file used for that session.
    """
    return session_dir() / f"{sanitize_session_name(session_name)}.json"


def load_history(session_name: str) -> list[HistoryEntry]:
    """Loads persisted history for a session.

    Invalid or unreadable files fall back to an empty history.
    """
    path = session_file(session_name)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        history: list[HistoryEntry] = []
        for item in data:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                history.append((role, content))
        return history
    except (json.JSONDecodeError, OSError, TypeError):
        return []


def save_history(session_name: str, history: list[HistoryEntry]) -> None:
    """Persists session history as JSON."""
    path = session_file(session_name)
    payload = [
        {
            "role": role,
            "content": content,
            "saved_at": datetime.utcnow().isoformat() + "Z",
        }
        for role, content in history
    ]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def clear_history(session_name: str) -> None:
    """Clears persisted history for a session.

    The session file is rewritten to an empty JSON array instead of being
    deleted. This keeps the cleared session as a concrete, newest session file
    so chat startup does not silently resume a different older session.
    """
    path = session_file(session_name)
    try:
        path.write_text("[]", encoding="utf-8")
    except OSError:
        # Keep command flow resilient; unreadable/locked files can be safely
        # ignored because load_history falls back to [].
        pass


def clear_cli_history(session_name: str) -> None:
    """Clears prompt-toolkit command history for a named session."""
    path = cli_history_file(session_name)
    try:
        path.write_text("", encoding="utf-8")
    except OSError:
        pass
