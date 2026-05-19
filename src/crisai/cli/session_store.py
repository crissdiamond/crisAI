from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from crisai.config import load_settings
from crisai.orchestration.session_anchors import AnchorRegistry, SessionSourceCandidate
from crisai.workspace.spaces import load_workspace_spaces

HistoryEntry = tuple[str, str]


def _workspace_spaces():
    settings = load_settings()
    return load_workspace_spaces(getattr(settings, "registry_dir", None))


@dataclass(frozen=True, slots=True)
class SessionMemory:
    """Compact task memory persisted beside raw chat history."""

    schema_version: str = "session_memory_v2"
    task_goal: str = ""
    current_state: str = ""
    scope: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    important_decisions: list[str] = field(default_factory=list)
    rejected_options: list[str] = field(default_factory=list)
    source_findings: list[str] = field(default_factory=list)
    known_sources: list[str] = field(default_factory=list)
    source_candidates: list[SessionSourceCandidate] = field(default_factory=list)
    active_artefacts: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    last_outputs: list[str] = field(default_factory=list)
    do_not_repeat: list[str] = field(default_factory=list)
    updated_at: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SessionMemory:
        """Build memory from persisted JSON, tolerating missing fields."""
        return cls(
            schema_version="session_memory_v2",
            task_goal=str(payload.get("task_goal") or ""),
            current_state=str(payload.get("current_state") or ""),
            scope=_string_list(payload.get("scope")),
            assumptions=_string_list(payload.get("assumptions")),
            constraints=_string_list(payload.get("constraints")),
            important_decisions=_string_list(payload.get("important_decisions")),
            rejected_options=_string_list(payload.get("rejected_options")),
            source_findings=_string_list(payload.get("source_findings")),
            known_sources=_string_list(payload.get("known_sources")),
            source_candidates=_source_candidate_list(payload.get("source_candidates")),
            active_artefacts=_string_list(payload.get("active_artefacts")),
            open_questions=_string_list(payload.get("open_questions")),
            next_actions=_string_list(payload.get("next_actions")),
            last_outputs=_string_list(payload.get("last_outputs")),
            do_not_repeat=_string_list(payload.get("do_not_repeat")),
            updated_at=str(payload.get("updated_at") or ""),
        )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _source_candidate_list(value: Any) -> list[SessionSourceCandidate]:
    if not isinstance(value, list):
        return []
    return [
        SessionSourceCandidate.from_dict(item)
        for item in value
        if isinstance(item, dict) and str(item.get("title") or "").strip()
    ]


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


def task_metadata_path(session_name: str) -> Path:
    """Return the task metadata folder path without creating it."""
    settings = load_settings()
    spaces = _workspace_spaces()
    return settings.workspace_dir / spaces.tasks_root / sanitize_session_name(session_name) / ".crisai"


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


def legacy_session_path(session_name: str) -> Path:
    """Build the pre-task session history path without creating directories."""
    settings = load_settings()
    return settings.workspace_dir / "chat_sessions" / f"{sanitize_session_name(session_name)}.json"


def session_memory_file(session_name: str) -> Path:
    """Build the compact-memory path for a named session."""
    return task_metadata_dir(session_name) / "memory.json"


def session_memory_path(session_name: str) -> Path:
    """Build the compact-memory path without creating directories."""
    return task_metadata_path(session_name) / "memory.json"


def session_anchors_file(session_name: str) -> Path:
    """Build the deterministic anchor registry path for a named session."""
    return task_metadata_dir(session_name) / "anchors.json"


def legacy_session_memory_file(session_name: str) -> Path:
    """Build the pre-task compact-memory path."""
    return session_dir() / f"{sanitize_session_name(session_name)}.memory.json"


def legacy_session_memory_path(session_name: str) -> Path:
    """Build the pre-task compact-memory path without creating directories."""
    settings = load_settings()
    return settings.workspace_dir / "chat_sessions" / f"{sanitize_session_name(session_name)}.memory.json"


def load_history(session_name: str) -> list[HistoryEntry]:
    """Loads persisted history for a session.

    Invalid or unreadable files fall back to an empty history.
    """
    path = task_metadata_path(session_name) / "history.json"
    if not path.exists():
        legacy = legacy_session_path(session_name)
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
    path = session_memory_path(session_name)
    if not path.exists():
        legacy = legacy_session_memory_path(session_name)
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


def load_session_anchors(session_name: str) -> AnchorRegistry:
    """Load deterministic session anchors, returning an empty registry on failure."""
    path = session_anchors_file(session_name)
    if not path.exists():
        return AnchorRegistry()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return AnchorRegistry.from_dict(payload)
    except (json.JSONDecodeError, OSError, TypeError):
        return AnchorRegistry()
    return AnchorRegistry()


def save_session_anchors(session_name: str, anchors: AnchorRegistry) -> None:
    """Persist deterministic session anchors as JSON."""
    ensure_task_manifest(session_name)
    path = session_anchors_file(session_name)
    path.write_text(json.dumps(anchors.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def clear_session_memory(session_name: str) -> None:
    """Clear compact memory for a session while preserving raw transcript."""
    save_session_memory(session_name, SessionMemory())
    save_session_anchors(session_name, AnchorRegistry())


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


def register_task_artefacts(
    session_name: str,
    paths: list[str],
    *,
    request: str = "",
    deliverable_type: str = "",
    root_dir: Path | None = None,
) -> None:
    """Register generated task artefacts in the task manifest."""
    safe = sanitize_session_name(session_name)
    manifest_path = ensure_task_manifest(safe)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            payload = {}
    except (json.JSONDecodeError, OSError):
        payload = {}
    payload.setdefault("schema_version", "crisai_task_v1")
    payload.setdefault("slug", safe)
    payload.setdefault("title", session_name.strip() or safe)
    payload.setdefault("status", "active")
    payload.setdefault("created_at", datetime.utcnow().isoformat() + "Z")
    existing_paths = _string_list(payload.get("artefact_paths"))
    existing_entries = payload.get("artefacts")
    if not isinstance(existing_entries, list):
        existing_entries = []
    existing_by_path = {
        str(item.get("path") or "").strip(): item
        for item in existing_entries
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    }
    now = datetime.utcnow().isoformat() + "Z"
    for path in paths:
        rel = _normalise_task_artefact_path(path, root_dir=root_dir)
        if not rel or f"{safe}/artefacts/" not in rel:
            continue
        if rel not in existing_paths:
            existing_paths.append(rel)
        entry = dict(existing_by_path.get(rel) or {})
        entry.update(
            {
                "path": rel,
                "title": _artefact_title_from_path(rel),
                "type": deliverable_type or entry.get("type") or "artifact",
                "updated_at": now,
            }
        )
        if "created_at" not in entry:
            entry["created_at"] = now
        if request:
            entry["source_request"] = request
        existing_by_path[rel] = entry
    payload["artefact_paths"] = sorted(dict.fromkeys(existing_paths))
    payload["artefacts"] = [existing_by_path[path] for path in payload["artefact_paths"] if path in existing_by_path]
    payload["updated_at"] = now
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _normalise_task_artefact_path(path: str, *, root_dir: Path | None = None) -> str:
    raw = str(path or "").strip().strip("`").strip()
    if not raw:
        return ""
    if raw.startswith("file://"):
        raw = raw[len("file://") :]
    if root_dir is not None:
        try:
            raw_path = Path(raw)
            if raw_path.is_absolute():
                raw = raw_path.resolve().relative_to(root_dir.resolve()).as_posix()
        except (OSError, ValueError):
            pass
    raw = raw.strip("/")
    if raw.startswith("workspace/"):
        return raw
    if raw.startswith("tasks/"):
        return f"workspace/{raw}"
    return raw


def _artefact_title_from_path(path: str) -> str:
    stem = Path(path).stem
    return stem.replace("-", " ").replace("_", " ").strip().title() or Path(path).name


def list_task_names() -> list[str]:
    """List task-backed session names."""
    if not tasks_dir().exists():
        return []
    return sorted(path.name for path in tasks_dir().iterdir() if path.is_dir())
