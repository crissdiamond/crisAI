from __future__ import annotations

from crisai.cli import chat_context


def test_render_history_formats_roles():
    history = [("user", "hello"), ("assistant", "hi")]

    result = chat_context.render_history(history)

    assert result == "User: hello\n\nAssistant: hi"


def test_build_chat_input_returns_plain_input_without_history():
    assert chat_context.build_chat_input("hello", []) == "hello"


def test_build_chat_input_wraps_last_twelve_entries(monkeypatch):
    captured = {}

    def fake_render_cli_text(template: str, **kwargs):
        captured["template"] = template
        captured["kwargs"] = kwargs
        return "wrapped"

    monkeypatch.setattr(chat_context, "render_cli_text", fake_render_cli_text)

    history = [("user" if i % 2 == 0 else "assistant", f"message-{i}") for i in range(14)]

    result = chat_context.build_chat_input("latest", history)

    assert result == "wrapped"
    assert captured["template"] == "chat/history_wrapper.md"
    assert captured["kwargs"]["user_input"] == "latest"
    transcript = captured["kwargs"]["transcript"]
    entries = transcript.split("\n\n")
    assert len(entries) == 12
    assert entries[0] == "User: message-2"
    assert entries[-1] == "Assistant: message-13"
