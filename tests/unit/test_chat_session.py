from __future__ import annotations

from pathlib import Path

from crisai.cli import chat_session


def test_chat_session_open_append_save_clear_and_switch(monkeypatch):
    histories = {
        "default": [("user", "old")],
        "next": [("assistant", "loaded")],
    }
    saved: list[tuple[str, list[tuple[str, str]]]] = []

    monkeypatch.setattr(chat_session, "sanitize_session_name", lambda name: name.replace(" ", "_"))
    monkeypatch.setattr(chat_session, "load_history", lambda name: list(histories.get(name, [])))
    monkeypatch.setattr(chat_session, "save_history", lambda name, history: saved.append((name, list(history))))
    monkeypatch.setattr(chat_session, "session_file", lambda name: Path("/tmp") / f"{name}.json")
    monkeypatch.setattr(chat_session, "build_chat_input", lambda user_input, history, max_entries=12: f"{len(history)}::{user_input}")

    session = chat_session.open_session("default")
    assert session.file_path == Path("/tmp/default.json")
    assert session.history == [("user", "old")]

    session.append_user_message("hello")
    session.append_assistant_message("hi")
    assert session.build_chat_input("next prompt") == "3::next prompt"

    session.save()
    session.clear()
    session.switch("next")

    assert saved[0] == ("default", [("user", "old"), ("user", "hello"), ("assistant", "hi")])
    assert saved[1] == ("default", [])
    assert session.name == "next"
    assert session.history == [("assistant", "loaded")]
