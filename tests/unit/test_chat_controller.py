from __future__ import annotations

import pytest

from crisai.cli.chat_controller import ChatRuntimeState, handle_chat_command


@pytest.fixture
def state() -> ChatRuntimeState:
    return ChatRuntimeState(
        current_session="default",
        history=[("user", "hello"), ("assistant", "hi")],
        current_mode="single",
        current_agent="orchestrator",
        current_review=False,
        current_verbose=False,
        mode_pinned=False,
        agent_pinned=False,
    )


def test_non_command_returns_false(state):
    assert handle_chat_command("hello", state) is False


def test_exit_raises_eoferror(state):
    with pytest.raises(EOFError):
        handle_chat_command("/exit", state)


def test_help_uses_help_template(monkeypatch, state):
    captured = {}

    monkeypatch.setattr("crisai.cli.chat_controller.load_cli_text", lambda path: f"loaded:{path}")
    monkeypatch.setattr(
        "crisai.cli.chat_controller.print_final_answer",
        lambda body, title=None: captured.update({"body": body, "title": title}),
    )

    assert handle_chat_command("/help", state) is True
    assert captured == {"body": "loaded:help.md", "title": "📘 CLI help"}


def test_clear_empties_history_and_persists(monkeypatch, state):
    saved = {}
    notices = []

    monkeypatch.setattr(
        "crisai.cli.chat_controller.save_history",
        lambda session, history: saved.update({"session": session, "history": list(history)}),
    )
    monkeypatch.setattr(
        "crisai.cli.chat_controller.print_status_message",
        lambda body, title=None: notices.append((title, body)),
    )

    assert handle_chat_command("/clear", state) is True
    assert state.history == []
    assert saved == {"session": "default", "history": []}
    assert notices[-1][0] == "🧹 Session cleared"


def test_switch_session_loads_new_history_and_prints_state(monkeypatch, state):
    notices = []

    monkeypatch.setattr(
        "crisai.cli.chat_controller.load_history",
        lambda session: [("user", f"loaded:{session}")],
    )
    monkeypatch.setattr(
        "crisai.cli.chat_controller.print_status_message",
        lambda body, title=None: notices.append((title, body)),
    )
    assert handle_chat_command("/session project-a", state) is True
    assert state.current_session == "project-a"
    assert state.history == [("user", "loaded:project-a")]
    assert notices[-1][0] == "🔁 Session switched"


def test_set_mode_auto_clears_pin(monkeypatch, state):
    notices = []
    state.current_mode = "pipeline"
    state.mode_pinned = True

    monkeypatch.setattr(
        "crisai.cli.chat_controller.print_status_message",
        lambda body, title=None: notices.append((title, body)),
    )
    assert handle_chat_command("/mode auto", state) is True
    assert state.current_mode == "single"
    assert state.mode_pinned is False
    assert notices[-1][0] == "🧭 Routing mode"


def test_set_mode_peer_pins_mode(monkeypatch, state):
    monkeypatch.setattr("crisai.cli.chat_controller.print_status_message", lambda *args, **kwargs: None)

    assert handle_chat_command("/mode peer", state) is True
    assert state.current_mode == "peer"
    assert state.mode_pinned is True


def test_set_review_updates_state(monkeypatch, state):
    monkeypatch.setattr("crisai.cli.chat_controller.print_status_message", lambda *args, **kwargs: None)

    assert handle_chat_command("/review on", state) is True
    assert state.current_review is True


def test_set_verbose_updates_state(monkeypatch, state):
    monkeypatch.setattr("crisai.cli.chat_controller.print_status_message", lambda *args, **kwargs: None)

    assert handle_chat_command("/verbose on", state) is True
    assert state.current_verbose is True


def test_set_agent_auto_clears_pin(monkeypatch, state):
    state.current_agent = "design"
    state.agent_pinned = True
    monkeypatch.setattr("crisai.cli.chat_controller.print_status_message", lambda *args, **kwargs: None)

    assert handle_chat_command("/agent auto", state) is True
    assert state.current_agent == "orchestrator"
    assert state.agent_pinned is False


def test_set_agent_specific_value_pins(monkeypatch, state):
    monkeypatch.setattr("crisai.cli.chat_controller.print_status_message", lambda *args, **kwargs: None)

    assert handle_chat_command("/agent design_author", state) is True
    assert state.current_agent == "design_author"
    assert state.agent_pinned is True


def test_status_command_prints_current_state(monkeypatch, state):
    calls = []
    monkeypatch.setattr("crisai.cli.chat_controller.print_chat_state", lambda **kwargs: calls.append(kwargs))

    assert handle_chat_command("/status", state) is True
    assert calls[-1]["current_session"] == "default"


def test_invalid_command_shows_notice(monkeypatch, state):
    notices = []
    monkeypatch.setattr(
        "crisai.cli.chat_controller.print_status_message",
        lambda body, title=None: notices.append((title, body)),
    )

    assert handle_chat_command("/unknown", state) is True
    assert notices[-1][0] == "⚠ Command notice"
    assert "Unknown command" in notices[-1][1]


def test_list_commands_delegate_to_view_helpers(monkeypatch, state):
    calls = []
    monkeypatch.setattr("crisai.cli.chat_controller.print_servers_table", lambda: calls.append("servers"))
    monkeypatch.setattr("crisai.cli.chat_controller.print_agents_table", lambda: calls.append("agents"))
    monkeypatch.setattr("crisai.cli.chat_controller.print_session_history", lambda history: calls.append(("history", list(history))))

    assert handle_chat_command("/list-servers", state) is True
    assert handle_chat_command("/list-agents", state) is True
    assert handle_chat_command("/history", state) is True
    assert calls == ["servers", "agents", ("history", [("user", "hello"), ("assistant", "hi")])]
