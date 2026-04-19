from __future__ import annotations

import re
import textwrap
from typing import Literal

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from .peer_transcript import PeerMessage

console = Console()

RenderKind = Literal["status", "stage", "final"]

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

_RENDER_TITLES = {
    "status": "ℹ Status",
    "stage": "🧩 Stage output",
    "final": "🧭 Final answer",
}

_RENDER_STYLES = {
    "status": "cyan",
    "stage": "bright_black",
    "final": "bright_black",
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


def _clean_agent_text(text: str) -> str:
    clean = _strip_markdown(text)

    boilerplate_patterns = [
        r"^peer conversation\s+",
        r"^(author|challenger|refiner|judge|final recommendation)\s+",
        r"^(peer mode conversation)\s+",
        r"^(strengths|weaknesses|decision|reason)\s*[:\-]?\s+",
    ]
    changed = True
    while changed:
        changed = False
        for pattern in boilerplate_patterns:
            new_clean = re.sub(pattern, "", clean, flags=re.IGNORECASE).strip()
            if new_clean != clean:
                clean = new_clean
                changed = True

    clean = re.sub(r"\b(author|challenger|refiner|judge)\b\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip(" \n\t-•") for p in parts if p.strip(" \n\t-•")]


def _pick_first_substantive_sentence(text: str) -> str:
    for sentence in _sentences(text):
        if len(sentence) >= 30:
            return sentence
    return text.strip()


def _normalise_fragment(text: str) -> str:
    fragment = text.strip()
    fragment = fragment.rstrip(" .!?:;,-")
    if fragment and fragment[0].isupper():
        fragment = fragment[:1].lower() + fragment[1:]
    return fragment


def _author_like_summary(agent_id: str, text: str) -> str:
    clean = _clean_agent_text(text)
    sentence = _pick_first_substantive_sentence(clean)

    leading_verbs = [
        "use ", "keep ", "add ", "introduce ", "create ", "split ", "move ",
        "make ", "treat ", "store ", "validate ", "separate ", "route ",
    ]
    lowered = sentence.lower()
    for verb in leading_verbs:
        if lowered.startswith(verb):
            action = _normalise_fragment(sentence)
            if agent_id == "design_refiner":
                return f"The Refiner suggests we {action}."
            if agent_id in {"design", "design_author"}:
                return f"The Author proposes we {action}."

    action = _normalise_fragment(sentence)
    if agent_id == "design_refiner":
        return f"The Refiner suggests {action}."
    return f"The Author proposes {action}."


def _challenger_summary(text: str) -> str:
    clean = _clean_agent_text(text)

    weakness_match = re.search(
        r"(weakness(?:es)?|concerns?|gaps?)\s*[:\-]?\s*(.*)",
        clean,
        flags=re.IGNORECASE,
    )
    if weakness_match and weakness_match.group(2).strip():
        fragment = _pick_first_substantive_sentence(weakness_match.group(2).strip())
        return f"The Challenger highlights that {_normalise_fragment(fragment)}."

    fragment = _pick_first_substantive_sentence(clean)
    return f"The Challenger highlights that {_normalise_fragment(fragment)}."


def _judge_summary(text: str) -> str:
    clean = _clean_agent_text(text)

    decision_match = re.search(r"\bdecision\s*[:\-]?\s*(accept|acceptable|revise|reject)\b", clean, flags=re.IGNORECASE)
    reason_match = re.search(r"\breason\s*[:\-]?\s*(.*)", clean, flags=re.IGNORECASE)

    if decision_match:
        decision = decision_match.group(1).lower()
        if decision in {"accept", "acceptable"}:
            if reason_match and reason_match.group(1).strip():
                reason = _normalise_fragment(_pick_first_substantive_sentence(reason_match.group(1).strip()))
                return f"The Judge concludes that the proposal is acceptable because {reason}."
            return "The Judge concludes that the proposal is acceptable."
        if decision == "revise":
            if reason_match and reason_match.group(1).strip():
                reason = _normalise_fragment(_pick_first_substantive_sentence(reason_match.group(1).strip()))
                return f"The Judge concludes that the proposal needs revision because {reason}."
            return "The Judge concludes that the proposal needs revision."
        if decision == "reject":
            if reason_match and reason_match.group(1).strip():
                reason = _normalise_fragment(_pick_first_substantive_sentence(reason_match.group(1).strip()))
                return f"The Judge concludes that the proposal should be rejected because {reason}."
            return "The Judge concludes that the proposal should be rejected."

    fragment = _pick_first_substantive_sentence(clean)
    return f"The Judge concludes that {_normalise_fragment(fragment)}."


def _discovery_summary(text: str) -> str:
    clean = _clean_agent_text(text)
    fragment = _pick_first_substantive_sentence(clean)
    return f"Discovery finds that {_normalise_fragment(fragment)}."


def _review_summary(text: str) -> str:
    clean = _clean_agent_text(text)
    fragment = _pick_first_substantive_sentence(clean)
    return f"The Review notes that {_normalise_fragment(fragment)}."


def _operations_summary(text: str) -> str:
    clean = _clean_agent_text(text)
    fragment = _pick_first_substantive_sentence(clean)
    return f"Operations suggests that {_normalise_fragment(fragment)}."


def _orchestrator_summary(text: str) -> str:
    clean = _clean_agent_text(text)
    fragment = _pick_first_substantive_sentence(clean)
    return f"The Orchestrator recommends {_normalise_fragment(fragment)}."


def _role_led_summary(agent_id: str, body: str, width: int = 118) -> str:
    if agent_id in {"design", "design_author", "design_refiner"}:
        summary = _author_like_summary(agent_id, body) if agent_id != "design_refiner" else _author_like_summary("design_refiner", body)
    elif agent_id == "design_challenger":
        summary = _challenger_summary(body)
    elif agent_id == "judge":
        summary = _judge_summary(body)
    elif agent_id == "discovery":
        summary = _discovery_summary(body)
    elif agent_id == "review":
        summary = _review_summary(body)
    elif agent_id == "operations":
        summary = _operations_summary(body)
    elif agent_id == "orchestrator":
        summary = _orchestrator_summary(body)
    else:
        clean = _clean_agent_text(body)
        fragment = _pick_first_substantive_sentence(clean)
        summary = f"The {_label(agent_id)} says {_normalise_fragment(fragment)}."

    wrapped = textwrap.wrap(summary, width=width)
    if len(wrapped) <= 3:
        return "\n".join(wrapped)

    trimmed = wrapped[:3]
    last = trimmed[-1].rstrip(" .")
    if not last.endswith(("…", "...")):
        last += "…"
    trimmed[-1] = last
    return "\n".join(trimmed)


def render_running_panel(agent_id: str) -> Panel:
    icon = _icon(agent_id)
    label = _label(agent_id)
    style = _style(agent_id)
    title = Text(f"{icon} {label}", style=f"bold {style}")
    body = Text(f"agent: {agent_id} running", style="dim")
    return Panel(
        body,
        title=title,
        border_style=style,
        padding=(0, 1),
        expand=True,
    )


def create_agent_live(agent_id: str) -> Live:
    return Live(
        render_running_panel(agent_id),
        console=console,
        refresh_per_second=4,
        transient=True,
    )


def print_status_message(body: str, *, title: str | None = None) -> None:
    panel_title = Text(title or _RENDER_TITLES["status"], style=f"bold {_RENDER_STYLES['status']}")
    console.print(
        Panel(
            body.strip() or "_empty_",
            title=panel_title,
            border_style=_RENDER_STYLES["status"],
            padding=(0, 1),
            expand=True,
        )
    )


def print_agent_output(agent_id: str, body: str, *, verbose: bool) -> None:
    icon = _icon(agent_id)
    label = _label(agent_id)
    style = _style(agent_id)
    title = Text(f"{icon} {label}", style=f"bold {style}")

    rendered_body = Markdown(body.strip() or "_empty_") if verbose else _role_led_summary(agent_id, body)
    console.print(
        Panel(
            rendered_body,
            title=title,
            subtitle=Text(_RENDER_TITLES["stage"], style=f"italic {_RENDER_STYLES['stage']}"),
            border_style=style,
            padding=(0, 1),
            expand=True,
        )
    )


def render_peer_message(message: PeerMessage) -> Panel:
    speaker = message.speaker
    title = Text(f"{_icon(speaker)} {_label(speaker)}", style=f"bold {_style(speaker)}")
    subtitle = Text(_RENDER_TITLES["stage"], style=f"italic {_RENDER_STYLES['stage']}")
    if getattr(message, "step", ""):
        subtitle = Text(f"{_RENDER_TITLES['stage']} • {message.step}", style=f"italic {_style(speaker)}")

    content = (message.content or "").strip() or "_empty_"

    return Panel(
        Markdown(content),
        title=title,
        subtitle=subtitle,
        border_style=_style(speaker),
        padding=(0, 1),
        expand=True,
    )


def print_final_answer(body: str, *, title: str | None = None) -> None:
    panel_title = Text(title or _RENDER_TITLES["final"], style=f"bold {_RENDER_STYLES['final']}")
    console.print(
        Panel(
            Markdown(body.strip() or "_empty_"),
            title=panel_title,
            border_style=_RENDER_STYLES["final"],
            padding=(0, 1),
            expand=True,
        )
    )


def print_final_recommendation(body: str) -> None:
    print_final_answer(body, title="🧭 Final recommendation")


def print_peer_message(message: PeerMessage) -> None:
    console.print(render_peer_message(message))
