from __future__ import annotations

from rich.panel import Panel

from crisai.cli import display
from crisai.cli.display import render_peer_message
from crisai.cli.peer_transcript import make_peer_message


def test_render_peer_message_returns_panel() -> None:
    msg = make_peer_message("design_challenger", "I disagree with this assumption.")
    panel = render_peer_message(msg)
    assert isinstance(panel, Panel)


def test_print_agent_output_compact_mode_uses_single_line(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))

    display.print_agent_output("design", "Use a staged rollout with validation gates.", verbose=False)

    assert len(captured) == 1
    assert isinstance(captured[0], Panel)


def test_print_status_message_keeps_router_literal_text(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))

    display.print_status_message("router:auto • pipeline • retrieval_planner", title="🧭 Routing decision")

    assert len(captured) == 1
