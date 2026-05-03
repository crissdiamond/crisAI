from __future__ import annotations

from rich.markdown import Markdown
from rich.panel import Panel

from crisai.cli import display
from crisai.cli.display import render_peer_message
from crisai.cli.peer_transcript import make_peer_message


def test_render_peer_message_returns_panel() -> None:
    msg = make_peer_message("design_challenger", "I disagree with this assumption.")
    panel = render_peer_message(msg)
    assert isinstance(panel, Panel)


def test_print_agent_output_non_verbose_uses_markdown_panel(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))

    display.print_agent_output("design", "**Bold** rollout with `gates`.", verbose=False)

    assert len(captured) == 1
    assert isinstance(captured[0], Panel)
    panel = captured[0]
    assert isinstance(panel.renderable, Markdown)


def test_print_agent_output_verbose_uses_markdown_panel(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))

    display.print_agent_output("design", "- one\n- two", verbose=True)

    assert len(captured) == 1
    panel = captured[0]
    assert isinstance(panel.renderable, Markdown)


def test_print_agent_output_non_verbose_markdown_is_short_summary_not_full_body(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))

    long_body = "## Report\n\n" + ("First finding supports the compromise. " * 15)
    display.print_agent_output("context_synthesizer", long_body, verbose=False)

    panel = captured[0]
    md = panel.renderable
    assert isinstance(md, Markdown)
    assert md.markup.startswith("**Summary:**")
    assert len(md.markup) < len(long_body) * 0.6


def test_print_status_message_keeps_router_literal_text(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(display.console, "print", lambda value: captured.append(value))

    display.print_status_message("router:auto • pipeline • retrieval_planner", title="🧭 Routing decision")

    assert len(captured) == 1
