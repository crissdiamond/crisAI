from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from crisai.config import load_settings
from crisai.workspace.spaces import load_workspace_spaces

HistoryEntry = tuple[str, str]


def _workspace_spaces():
    settings = load_settings()
    return load_workspace_spaces(getattr(settings, "registry_dir", None))


@dataclass(frozen=True, slots=True)
class SessionMemory:
    """Compact task memory persisted beside raw chat history."""

    schema_version: str = "session_memory_v1"
    task_goal: str = ""
    current_state: str = ""
    important_decisions: list[str] = field(default_factory=list)
    known_sources: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    last_outputs: list[str] = field(default_factory=list)
    do_not_repeat: list[str] = field(default_factory=list)
    updated_at: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SessionMemory:
        """Build memory from persisted JSON, tolerating missing fields."""
        return cls(
            schema_version=str(payload.get("schema_version") or "session_memory_v1"),
            task_goal=str(payload.get("task_goal") or ""),
            current_state=str(payload.get("current_state") or ""),
            important_decisions=_string_list(payload.get("important_decisions")),
            known_sources=_string_list(payload.get("known_sources")),
            open_questions=_string_list(payload.get("open_questions")),
            last_outputs=_string_list(payload.get("last_outputs")),
            do_not_repeat=_string_list(payload.get("do_not_repeat")),
            updated_at=str(payload.get("updated_at") or ""),
        )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


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
        path = task_metadata_dir(safe) / f".cli_history_{safe}"
    else:
        path = settings.workspace_dir / ".cli_history"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def session_dir() -> Path:
    """Returns the legacy directory used to persist named chat sessions."""
    settings = load_settings()
    path = settings.workspace_dir / "chat_sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def tasks_dir() -> Path:
    """Return the root directory for task-backed sessions."""
    settings = load_settings()
    spaces = _workspace_spaces()
    path = settings.workspace_dir / spaces.tasks_root
    path.mkdir(parents=True, exist_ok=True)
    return path


def task_dir(session_name: str) -> Path:
    """Return the task folder for a session name."""
    path = tasks_dir() / sanitize_session_name(session_name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def task_metadata_dir(session_name: str) -> Path:
    """Return the task metadata folder that owns history and memory."""
    path = task_dir(session_name) / ".crisai"
    path.mkdir(parents=True, exist_ok=True)
    return path


def task_manifest_file(session_name: str) -> Path:
    """Return the task manifest path."""
    return task_metadata_dir(session_name) / "task.json"


def session_file(session_name: str) -> Path:
    """Builds a safe file path for a named chat session.

    Args:
        session_name: User-provided session name.

    Returns:
        Path to the JSON file used for that session.
    """
    return task_metadata_dir(session_name) / "history.json"


def legacy_session_file(session_name: str) -> Path:
    """Build the pre-task session history path."""
    return session_dir() / f"{sanitize_session_name(session_name)}.json"


def session_memory_file(session_name: str) -> Path:
    """Build the compact-memory path for a named session."""
    return task_metadata_dir(session_name) / "memory.json"


def legacy_session_memory_file(session_name: str) -> Path:
    """Build the pre-task compact-memory path."""
    return session_dir() / f"{sanitize_session_name(session_name)}.memory.json"


def load_history(session_name: str) -> list[HistoryEntry]:
    """Loads persisted history for a session.

    Invalid or unreadable files fall back to an empty history.
    """
    path = session_file(session_name)
    if not path.exists():
        legacy = legacy_session_file(session_name)
        if legacy.exists():
            path = legacy
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
    ensure_task_manifest(session_name)
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


def load_session_memory(session_name: str) -> SessionMemory:
    """Load compact memory for a session, returning empty memory on failure."""
    path = session_memory_file(session_name)
    if not path.exists():
        legacy = legacy_session_memory_file(session_name)
        if legacy.exists():
            path = legacy
    if not path.exists():
        return SessionMemory()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return SessionMemory.from_dict(payload)
    except (json.JSONDecodeError, OSError, TypeError):
        return SessionMemory()
    return SessionMemory()


def save_session_memory(session_name: str, memory: SessionMemory) -> None:
    """Persist compact session memory as JSON."""
    ensure_task_manifest(session_name)
    path = session_memory_file(session_name)
    payload = asdict(memory)
    payload["updated_at"] = datetime.utcnow().isoformat() + "Z"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def clear_session_memory(session_name: str) -> None:
    """Clear compact memory for a session while preserving raw transcript."""
    save_session_memory(session_name, SessionMemory())


def clear_history(session_name: str) -> None:
    """Clears persisted history for a session.

    The session file is rewritten to an empty JSON array instead of being
    deleted. This keeps the cleared session as a concrete, newest session file
    so chat startup does not silently resume a different older session.
    """
    ensure_task_manifest(session_name)
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


def ensure_task_manifest(session_name: str) -> Path:
    """Create a minimal task manifest for a task-backed session."""
    safe = sanitize_session_name(session_name)
    path = task_manifest_file(safe)
    if path.exists():
        return path
    spaces = _workspace_spaces()
    now = datetime.utcnow().isoformat() + "Z"
    root = task_dir(safe)
    for subdir in spaces.task_subdirs.values():
        (root / subdir).mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "crisai_task_v1",
        "slug": safe,
        "title": session_name.strip() or safe,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "artefact_paths": [],
        "promoted_knowledge_paths": [],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def list_task_names() -> list[str]:
    """List task-backed session names."""
    if not tasks_dir().exists():
        return []
    return sorted(path.name for path in tasks_dir().iterdir() if path.is_dir())
