from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from crisai.config import load_settings


HistoryEntry = tuple[str, str]


def cli_history_file() -> Path:
    """Returns the prompt-toolkit history file path for the CLI."""
    settings = load_settings()
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
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in session_name.strip())
    if not safe:
        safe = "default"
    return session_dir() / f"{safe}.json"


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
    except Exception:
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
