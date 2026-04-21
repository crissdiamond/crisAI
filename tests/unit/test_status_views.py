from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from crisai.cli import status_views


@dataclass
class FakeRoutingDecision:
    mode: str
    agent: str | None
    intent: str
    needs_review: bool
    needs_retrieval: bool
    reason: str


@dataclass
class FakeServerSpec:
    id: str
    enabled: bool
    transport: str
    tags: list[str]


@dataclass
class FakeAgentSpec:
    id: str
    model: str
    allowed_servers: list[str]


class FakeRegistry:
    def __init__(self, _registry_dir):
        self.registry_dir = _registry_dir

    def load_servers(self):
        return [
            FakeServerSpec("workspace_server", True, "stdio", ["local"]),
            FakeServerSpec("sharepoint_server", False, "http", []),
        ]

    def load_agents(self):
        return [
            FakeAgentSpec("orchestrator", "gpt-test", ["workspace_server"]),
            FakeAgentSpec("design_author", "gpt-test", []),
        ]


class FakeConsole:
    instances = []

    def __init__(self):
        self.print_calls = []
        FakeConsole.instances.append(self)

    def print(self, value):
        self.print_calls.append(value)


def test_server_icon_covers_known_types():
    assert status_views.server_icon("workspace_server") == "📁"
    assert status_views.server_icon("document_reader") == "📄"
    assert status_views.server_icon("diagram_tool") == "📊"
    assert status_views.server_icon("sharepoint_sync") == "☁"
    assert status_views.server_icon("other") == "⚙"


def test_agent_icon_covers_known_types():
    assert status_views.agent_icon("orchestrator") == "🧭"
    assert status_views.agent_icon("discovery") == "🔎"
    assert status_views.agent_icon("design_author") == "✍"
    assert status_views.agent_icon("design_challenger") == "⚔"
    assert status_views.agent_icon("design_refiner") == "🛠"
    assert status_views.agent_icon("design") == "🏗"
    assert status_views.agent_icon("review") == "🛡"
    assert status_views.agent_icon("judge") == "⚖"
    assert status_views.agent_icon("operations") == "🖧"
    assert status_views.agent_icon("something_else") == "🧠"


def test_route_display_formats_expected_labels():
    decision = FakeRoutingDecision(
        mode="pipeline",
        agent="design",
        intent="explicit",
        needs_review=True,
        needs_retrieval=False,
        reason="forced",
    )

    result = status_views.route_display(decision)

    assert result == "[router:pinned] pipeline • design • review:on • retrieval:off • forced"


def test_mode_and_agent_status_helpers():
    assert status_views.mode_status("single", False) == "auto"
    assert status_views.mode_status("peer", True) == "pinned:peer"
    assert status_views.agent_status("orchestrator", False) == "auto"
    assert status_views.agent_status("design", True) == "pinned:design"


def test_print_chat_state_uses_status_message(monkeypatch):
    captured = {}

    def fake_print_status_message(body: str, title: str):
        captured["body"] = body
        captured["title"] = title

    monkeypatch.setattr(status_views, "print_status_message", fake_print_status_message)

    status_views.print_chat_state(
        current_session="demo",
        current_mode="pipeline",
        current_agent="design",
        current_review=True,
        current_verbose=False,
        mode_pinned=True,
        agent_pinned=True,
        history_count=4,
    )

    assert captured["title"] == "💬 Chat state"
    assert "Session: demo" in captured["body"]
    assert "Routing: pinned:pipeline" in captured["body"]
    assert "Agent: pinned:design" in captured["body"]
    assert "Review preference: on" in captured["body"]
    assert "Verbose: off" in captured["body"]
    assert "Loaded history entries: 4" in captured["body"]


def test_print_session_history_handles_empty(monkeypatch):
    calls = []

    monkeypatch.setattr(
        status_views,
        "print_status_message",
        lambda body, title: calls.append((title, body)),
    )

    status_views.print_session_history([])

    assert calls == [("📜 Session history", "No history in this session.")]


def test_print_session_history_limits_to_last_twenty_entries(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        status_views,
        "print_status_message",
        lambda body, title: captured.update({"title": title, "body": body}),
    )

    history = [("user" if i % 2 == 0 else "assistant", f"message-{i}") for i in range(25)]
    status_views.print_session_history(history)

    assert captured["title"] == "📜 Session history"
    assert "message-0" not in captured["body"]
    assert "message-4" not in captured["body"]
    assert "message-5" in captured["body"]
    assert "message-24" in captured["body"]


def test_print_servers_table_renders_registry_content(monkeypatch):
    import rich.console

    FakeConsole.instances.clear()
    monkeypatch.setattr(status_views, "load_settings", lambda: SimpleNamespace(registry_dir="/tmp/registry"))
    monkeypatch.setattr(status_views, "Registry", FakeRegistry)
    monkeypatch.setattr(rich.console, "Console", FakeConsole)

    status_views.print_servers_table()

    console = FakeConsole.instances[-1]
    assert len(console.print_calls) == 2
    assert "/tmp/registry" in str(console.print_calls[0])
    table = console.print_calls[1]
    assert table.row_count == 2


def test_print_agents_table_renders_registry_content(monkeypatch):
    import rich.console

    FakeConsole.instances.clear()
    monkeypatch.setattr(status_views, "load_settings", lambda: SimpleNamespace(registry_dir="/tmp/registry"))
    monkeypatch.setattr(status_views, "Registry", FakeRegistry)
    monkeypatch.setattr(rich.console, "Console", FakeConsole)

    status_views.print_agents_table()

    console = FakeConsole.instances[-1]
    assert len(console.print_calls) == 1
    table = console.print_calls[0]
    assert table.row_count == 2
