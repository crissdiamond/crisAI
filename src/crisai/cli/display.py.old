from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from .peer_transcript import PeerMessage

console = Console()

_ICONS = {
    "discovery": "🔎",
    "design_author": "✍",
    "design_challenger": "⚔",
    "design_refiner": "🛠",
    "judge": "⚖",
    "orchestrator": "🧭",
}

_STYLES = {
    "discovery": "cyan",
    "design_author": "bright_blue",
    "design_challenger": "yellow",
    "design_refiner": "green",
    "judge": "magenta",
    "orchestrator": "bright_white",
}


def print_stage(title: str, style: str) -> None:
    console.print(Panel.fit(title, style=style))

def print_markdown(title: str, body: str) -> None:
    console.print(Markdown(f"## {title}\n\n{body}"))

def print_history(history: list[tuple[str, str]], limit: int = 20) -> None:
    if not history:
        console.print("[yellow]No history in this session.[/yellow]")
        return

    console.print(Markdown("### Session history"))
    for idx, (role, content) in enumerate(history[-limit:], start=1):
        label = "User" if role == "user" else "Assistant"
        console.print(f"[bold]{idx}. {label}[/bold]: {content[:500]}")


def render_peer_message(message: PeerMessage) -> Panel:
    icon = _ICONS.get(message.speaker, "🧠")
    style = _STYLES.get(message.speaker, "white")
    title = Text(f"{icon} {message.speaker}", style=f"bold {style}")
    body = Text(message.content or "[empty]", style="white")
    return Panel(body, title=title, border_style=style)


def print_peer_message(message: PeerMessage) -> None:
    console.print(render_peer_message(message))
