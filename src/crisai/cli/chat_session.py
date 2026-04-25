from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from crisai.cli import chat_context as _chat_context
from crisai.cli import session_store as _session_store

HistoryEntry = _session_store.HistoryEntry



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
    return _session_store.cli_history_file()


def session_dir() -> Path:
    return _session_store.session_dir()


def sanitize_session_name(session_name: str) -> str:
    return _session_store.sanitize_session_name(session_name)


def session_file(session_name: str) -> Path:
    return _session_store.session_file(session_name)


def load_history(session_name: str) -> list[HistoryEntry]:
    return _session_store.load_history(session_name)


def save_history(session_name: str, history: list[HistoryEntry]) -> None:
    _session_store.save_history(session_name, history)


def render_history(history: list[HistoryEntry]) -> str:
    return _chat_context.render_history(history)


def build_chat_input(user_input: str, history: list[HistoryEntry], max_entries: int = 12) -> str:
    if not history:
        return user_input
    return _chat_context.build_chat_input(user_input, history[-max_entries:])


def open_session(name: str) -> ChatSession:
    safe_name = sanitize_session_name(name)
    return ChatSession(name=safe_name, history=load_history(safe_name))
