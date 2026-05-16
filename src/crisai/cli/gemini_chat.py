from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from crisai.cli.display import get_bottom_toolbar, sanitize_user_visible_text


@dataclass(slots=True)
class GeminiChatStatus:
    """Runtime fields shown in the persistent chat footer."""

    session: str
    mode: str
    agent: str
    model: str
    verbose: bool
    review: bool
    retrieval_checkpoint: bool
    mode_pinned: bool
    agent_pinned: bool
    activity: str = "idle"
    current_stage: str | None = None


class GeminiChatDisplay:
    """Live transcript and footer for the Gemini-style interactive chat.

    This class is intentionally a display sink, not a workflow controller. The
    chat loop and pipeline keep their existing responsibilities while rendering
    calls are redirected here during interactive execution.
    """

    def __init__(self, *, console: Console | None = None, max_entries: int = 80) -> None:
        self.console = console or Console()
        self.max_entries = max_entries
        self.status_state: GeminiChatStatus | None = None
        self.entries: list[tuple[str, str]] = []
        self._live: Live | None = None

    def update_status(self, status: GeminiChatStatus) -> None:
        """Replace footer status fields and refresh the live view if active."""
        self.status_state = status
        self._refresh()

    def status(self, body: str, *, title: str | None = None) -> None:
        """Append a user-visible status block to the transcript."""
        self.append(title or "Status", body)

    def stage_output(self, agent_id: str, body: str, *, verbose: bool) -> None:
        """Append a completed agent-stage block to the transcript."""
        del verbose
        self.append(agent_id.replace("_", " ").title(), body)

    def final(self, body: str, *, title: str | None = None) -> None:
        """Append the final answer to the transcript."""
        self.append(title or "Final answer", sanitize_user_visible_text(body))

    def agent_started(self, agent_id: str, topic: str) -> None:
        """Mark an agent as active in the footer."""
        del topic
        self._set_activity("working", agent_id)

    def agent_progress(self, agent_id: str, topic: str) -> None:
        """Update the active agent state without appending noisy output."""
        del topic
        self._set_activity("working", agent_id)

    def agent_finished(self, agent_id: str) -> None:
        """Clear the active agent state when a stage completes."""
        del agent_id
        self._set_activity("idle", None)

    def append(self, title: str, body: str) -> None:
        """Append a transcript entry and refresh the live view."""
        cleaned = sanitize_user_visible_text(body).strip() or "_empty_"
        self.entries.append((title, cleaned))
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]
        self._refresh()

    @contextmanager
    def live(self) -> Iterator[None]:
        """Run a persistent live display for one chat turn."""
        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=6,
            transient=False,
        )
        self._live.start()
        try:
            yield
        finally:
            self._set_activity("idle", None)
            if self._live is not None:
                self._live.stop()
            self._live = None

    def _set_activity(self, activity: str, stage: str | None) -> None:
        if self.status_state is None:
            return
        self.status_state.activity = activity
        self.status_state.current_stage = stage
        self._refresh()

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render())

    def _render(self):
        transcript = self._render_transcript()
        footer = self._render_footer()
        return Group(transcript, footer)

    def _render_transcript(self) -> Panel:
        visible = self.entries[-12:]
        content: Any
        if not visible:
            content = Text("No output yet.", style="dim")
        else:
            chunks: list[Any] = []
            for title, body in visible:
                chunks.append(Text(f"{title}\n", style="bold cyan"))
                chunks.append(Markdown(body))
                chunks.append(Text("\n"))
            content = Group(*chunks)
        return Panel(content, title="crisAI", border_style="bright_blue", padding=(0, 1))

    def _render_footer(self) -> Panel:
        if self.status_state is None:
            text = " crisAI | idle "
        else:
            base = get_bottom_toolbar(
                session=self.status_state.session,
                mode=self.status_state.mode,
                agent=self.status_state.agent,
                model=self.status_state.model,
                verbose=self.status_state.verbose,
                review=self.status_state.review,
                retrieval_checkpoint=self.status_state.retrieval_checkpoint,
                mode_pinned=self.status_state.mode_pinned,
                agent_pinned=self.status_state.agent_pinned,
            )
            suffix = f"| {self.status_state.activity}"
            if self.status_state.current_stage:
                suffix += f":{self.status_state.current_stage}"
            text = f"{base}{suffix} "
        return Panel(Text(text, style="reverse"), border_style="bright_black", padding=(0, 0))
