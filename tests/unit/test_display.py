from __future__ import annotations

from rich.panel import Panel

from crisai.cli.display import render_peer_message
from crisai.cli.peer_transcript import make_peer_message


def test_render_peer_message_returns_panel() -> None:
    msg = make_peer_message("design_challenger", "I disagree with this assumption.")
    panel = render_peer_message(msg)
    assert isinstance(panel, Panel)
