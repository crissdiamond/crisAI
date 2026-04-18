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

_LABELS = {
    "discovery": "Discovery",
    "design_author": "Author",
    "design_challenger": "Challenger",
    "design_refiner": "Refiner",
    "judge": "Judge",
    "orchestrator": "Final recommendation",
}

_STYLES = {
    "discovery": "cyan",
    "design_author": "bright_blue",
    "design_challenger": "yellow",
    "design_refiner": "green",
    "judge": "magenta",
    "orchestrator": "bright_white",
}


def print_stage(title: str, style: str = "cyan") -> None:
    title_text = Text(title, style=f"bold {style}")
    console.print(Panel.fit(title_text, border_style=style, padding=(0, 2)))


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
    speaker = message.speaker
    icon = _ICONS.get(speaker, "🧠")
    label = _LABELS.get(speaker, speaker.replace("_", " ").title())
    style = _STYLES.get(speaker, "white")

    title = Text(f"{icon} {label}", style=f"bold {style}")
    subtitle = None
    if getattr(message, "step", ""):
        subtitle = Text(str(message.step), style=f"italic {style}")

    content = (message.content or "").strip() or "_empty_"

    return Panel(
        Markdown(content),
        title=title,
        subtitle=subtitle,
        border_style=style,
        padding=(0, 1),
        expand=True,
    )

def print_final_recommendation(body: str) -> None:
    title = Text("🧭 Final recommendation", style="bold bright_white")
    console.print(
        Panel(
            Markdown(body.strip() or "_empty_"),
            title=title,
            border_style="bright_white",
            padding=(0, 1),
            expand=True,
        )
    )

def print_peer_message(message: PeerMessage) -> None:
    console.print(render_peer_message(message))
