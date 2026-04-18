from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()

HELP_MARKDOWN = """
### Commands
- `/exit` or `/quit` — leave chat
- `/mode single` — use single-agent mode
- `/mode pipeline` — use pipeline mode
- `/mode peer` — use peer mode
- `/review on` — enable review
- `/review off` — disable review
- `/history` — show saved conversation history in this session
- `/clear` — clear conversation history for this session
- `/session <name>` — switch to another persistent session
- `/agent <id>` — set single-agent target
- `/help` — show this help
"""


def print_stage(title: str, style: str) -> None:
    console.print(Panel.fit(title, style=style))


def print_markdown(title: str, body: str) -> None:
    console.print(Markdown(f"## {title}\n\n{body}"))


def print_help() -> None:
    console.print(Markdown(HELP_MARKDOWN))


def print_history(history: list[tuple[str, str]], limit: int = 20) -> None:
    if not history:
        console.print("[yellow]No history in this session.[/yellow]")
        return

    console.print(Markdown("### Session history"))
    for idx, (role, content) in enumerate(history[-limit:], start=1):
        label = "User" if role == "user" else "Assistant"
        console.print(f"[bold]{idx}. {label}[/bold]: {content[:500]}")
