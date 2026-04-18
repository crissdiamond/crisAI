from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from crisai.config import load_settings

HistoryEntry = tuple[str, str]


@dataclass
class ChatSession:
    name: str
    history: list[HistoryEntry] = field(default_factory=list)

    @property
    def file_path(self) -> Path:
        return session_file(self.name)

    def save(self) -> None:
        save_history(self.name, self.history)

    def clear(self) -> None:
        self.history.clear()
        self.save()

    def switch(self, new_name: str) -> None:
        self.name = sanitize_session_name(new_name)
        self.history = load_history(self.name)

    def append_user_message(self, content: str) -> None:
        self.history.append(("user", content))

    def append_assistant_message(self, content: str) -> None:
        self.history.append(("assistant", content))

    def build_chat_input(self, user_input: str, max_entries: int = 12) -> str:
        return build_chat_input(user_input, self.history, max_entries=max_entries)


def cli_history_file() -> Path:
    settings = load_settings()
    path = settings.workspace_dir / ".cli_history"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def session_dir() -> Path:
    settings = load_settings()
    path = settings.workspace_dir / "chat_sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_session_name(session_name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in session_name.strip())
    return safe or "default"


def session_file(session_name: str) -> Path:
    return session_dir() / f"{sanitize_session_name(session_name)}.json"


def load_history(session_name: str) -> list[HistoryEntry]:
    path = session_file(session_name)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    history: list[HistoryEntry] = []
    for item in data:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            history.append((role, content))
    return history


def save_history(session_name: str, history: list[HistoryEntry]) -> None:
    payload = [
        {
            "role": role,
            "content": content,
            "saved_at": datetime.utcnow().isoformat() + "Z",
        }
        for role, content in history
    ]
    session_file(session_name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def render_history(history: list[HistoryEntry]) -> str:
    if not history:
        return ""

    lines: list[str] = []
    for role, content in history:
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {content}")
    return "\n\n".join(lines)


def build_chat_input(user_input: str, history: list[HistoryEntry], max_entries: int = 12) -> str:
    if not history:
        return user_input

    transcript = render_history(history[-max_entries:])
    return f"""Conversation so far:
{transcript}

Latest user message:
{user_input}

Please answer consistently with the conversation so far."""


def open_session(name: str) -> ChatSession:
    safe_name = sanitize_session_name(name)
    return ChatSession(name=safe_name, history=load_history(safe_name))
