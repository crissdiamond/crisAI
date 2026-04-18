from __future__ import annotations

import re
import textwrap

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from .peer_transcript import PeerMessage

console = Console()

_ICONS = {
    "discovery": "🔎",
    "design": "✍",
    "design_author": "✍",
    "design_challenger": "⚔",
    "design_refiner": "🛠",
    "review": "🛡",
    "judge": "⚖",
    "orchestrator": "🧭",
    "operations": "🖧",
}

_LABELS = {
    "discovery": "Discovery",
    "design": "Design",
    "design_author": "Author",
    "design_challenger": "Challenger",
    "design_refiner": "Refiner",
    "review": "Review",
    "judge": "Judge",
    "orchestrator": "Orchestrator",
    "operations": "Operations",
}

_STYLES = {
    "discovery": "yellow",
    "design": "green",
    "design_author": "green",
    "design_challenger": "blue",
    "design_refiner": "red",
    "review": "yellow",
    "judge": "white",
    "orchestrator": "bright_black",
    "operations": "blue",
}


def _icon(agent_id: str) -> str:
    return _ICONS.get(agent_id, "🧠")


def _label(agent_id: str) -> str:
    return _LABELS.get(agent_id, agent_id.replace("_", " ").title())


def _style(agent_id: str) -> str:
    return _STYLES.get(agent_id, "white")


def _strip_markdown(text: str) -> str:
    stripped = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    stripped = re.sub(r"`([^`]*)`", r"\1", stripped)
    stripped = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", stripped)
    stripped = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
    stripped = re.sub(r"^\s{0,3}#{1,6}\s*", "", stripped, flags=re.MULTILINE)
    stripped = re.sub(r"^[\-*+]\s+", "", stripped, flags=re.MULTILINE)
    stripped = re.sub(r"^\s*>\s?", "", stripped, flags=re.MULTILINE)
    stripped = re.sub(r"[*_~]", "", stripped)
    stripped = re.sub(r"\s+", " ", stripped)
    return stripped.strip()


def _two_line_summary(body: str, width: int = 118) -> str:
    clean = _strip_markdown(body)
    if not clean:
        return "No summary available."

    sentences = re.split(r"(?<=[.!?])\s+", clean)
    summary = " ".join(sentences[:2]).strip() or clean
    wrapped = textwrap.wrap(summary, width=width)
    if not wrapped:
        return summary
    if len(wrapped) <= 2:
        return "\n".join(wrapped)
    trimmed = wrapped[:2]
    trimmed[-1] = trimmed[-1].rstrip(" .") + "…"
    return "\n".join(trimmed)


def _running_status(agent_id: str, tick: int, done: bool = False) -> Text:
    if done:
        body = f"agent: {agent_id}........ done"
        return Text(body, style="dim")
    dot_count = (tick % 8) + 1
    dots = "." * dot_count
    body = f"agent: {agent_id}{dots}"
    return Text(body, style="dim")


def render_running_panel(agent_id: str, tick: int = 0, *, done: bool = False) -> Panel:
    icon = _icon(agent_id)
    label = _label(agent_id)
    style = _style(agent_id)
    title = Text(f"{icon} {label}", style=f"bold {style}")
    return Panel(
        _running_status(agent_id, tick, done=done),
        title=title,
        border_style=style,
        padding=(0, 1),
        expand=True,
    )


def create_agent_live(agent_id: str) -> Live:
    return Live(
        render_running_panel(agent_id, 0),
        console=console,
        refresh_per_second=8,
        transient=False,
    )


def update_agent_live(live: Live, agent_id: str, tick: int, *, done: bool = False) -> None:
    live.update(render_running_panel(agent_id, tick, done=done), refresh=True)


def print_agent_output(agent_id: str, body: str, *, verbose: bool) -> None:
    icon = _icon(agent_id)
    label = _label(agent_id)
    style = _style(agent_id)
    title = Text(f"{icon} {label}", style=f"bold {style}")

    rendered_body = Markdown(body.strip() or "_empty_") if verbose else _two_line_summary(body)
    console.print(
        Panel(
            rendered_body,
            title=title,
            border_style=style,
            padding=(0, 1),
            expand=True,
        )
    )


def render_peer_message(message: PeerMessage) -> Panel:
    speaker = message.speaker
    title = Text(f"{_icon(speaker)} {_label(speaker)}", style=f"bold {_style(speaker)}")
    subtitle = None
    if getattr(message, "step", ""):
        subtitle = Text(str(message.step), style=f"italic {_style(speaker)}")

    content = (message.content or "").strip() or "_empty_"

    return Panel(
        Markdown(content),
        title=title,
        subtitle=subtitle,
        border_style=_style(speaker),
        padding=(0, 1),
        expand=True,
    )


def print_final_recommendation(body: str) -> None:
    title = Text("🧭 Final recommendation", style="bold bright_black")
    console.print(
        Panel(
            Markdown(body.strip() or "_empty_"),
            title=title,
            border_style="bright_black",
            padding=(0, 1),
            expand=True,
        )
    )


def print_peer_message(message: PeerMessage) -> None:
    console.print(render_peer_message(message))
