from __future__ import annotations

from crisai.cli.gem_events import GemEvent, GemUiState, apply_gem_event
from crisai.cli.gem_theme import GEM_CSS


def textual_available() -> bool:
    """Return whether the Textual dependency is importable in this environment."""
    try:
        import textual  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


def run_gem_app() -> int:
    """Run the crisAI Gem terminal UI.

    Returns:
        Process-style exit code. A non-zero code means the local environment is
        not ready to launch Gem yet.
    """
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.widgets import Footer, Header, Input, Label, Log, Static
    except ModuleNotFoundError:
        return 1

    class CrisaiGemApp(App):
        """Initial Gem shell with persistent layout and UCL-aligned styling."""

        CSS = GEM_CSS
        BINDINGS = [
            ("ctrl+c", "quit", "Quit"),
            ("ctrl+q", "quit", "Quit"),
        ]

        def __init__(self) -> None:
            super().__init__()
            self.state = GemUiState()

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True, id="header")
            with Horizontal(id="workspace"):
                with Vertical(id="stages"):
                    yield Static("Pipeline", classes="stage-active")
                    yield Label("○ Router", classes="stage-pending")
                    yield Label("○ Retrieval planner", classes="stage-pending")
                    yield Label("○ Context retrieval", classes="stage-pending")
                    yield Label("○ Context synthesis", classes="stage-pending")
                    yield Label("○ Draft", classes="stage-pending")
                    yield Label("○ Review", classes="stage-pending")
                    yield Label("○ Final", classes="stage-pending")
                yield Log(id="transcript", highlight=True)
            yield Input(placeholder="Type a prompt or slash command...", id="composer")
            yield Footer(id="footer")

        def on_mount(self) -> None:
            self.title = "crisAI Gem"
            self.sub_title = "full-screen architecture workstation"
            self._append_event(
                GemEvent(
                    kind="status",
                    title="Gem ready",
                    body=(
                        "Gem shell is running. Workflow execution will be wired "
                        "in the next implementation slice; use crisai classic for live work."
                    ),
                )
            )

        def _append_event(self, event: GemEvent) -> None:
            self.state = apply_gem_event(self.state, event)
            transcript = self.query_one("#transcript", Log)
            transcript.write_line(f"{event.title}: {event.body}".strip())

    CrisaiGemApp().run()
    return 0
