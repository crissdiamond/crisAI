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
    # Clipboard: plans retrieval handoff before Context Retrieval fetches sources.
    "retrieval_planner": "📋",
    "context_retrieval": "📚",
    # Puzzle: assembles retrieved facts into a brief for design.
    "context_synthesizer": "🧩",
    "design": "✍",
    "design_author": "✍",
    "design_challenger": "⚔",
    "design_refiner": "🛠",
    "review": "🛡",
    "judge": "⚖",
    "orchestrator": "🧭",
    # Wrench: local tooling, debugging, and environment fixes.
    "operations": "🔧",
    # Package: templates and formal artefacts.
    "publisher": "📦",
}

_LABELS = {
    "retrieval_planner": "Retrieval planner",
    "context_retrieval": "Context Retrieval",
    "context_synthesizer": "Context Synthesizer",
    "design": "Design",
    "design_author": "Author",
    "design_challenger": "Challenger",
    "design_refiner": "Refiner",
    "review": "Review",
    "judge": "Judge",
    "orchestrator": "Orchestrator",
    "operations": "Operations",
    "publisher": "Publisher",
}

_STYLES = {
    "retrieval_planner": "yellow",
    "context_retrieval": "cyan",
    "context_synthesizer": "magenta",
    "design": "green",
    "design_author": "green",
    "design_challenger": "blue",
    "design_refiner": "red",
    "review": "yellow",
    "judge": "white",
    "orchestrator": "bright_black",
    "operations": "blue",
    "publisher": "magenta",
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


def _substantive_sentence_list(
    text: str,
    *,
    max_count: int = 4,
    max_chars: int = 1100,
    min_sentence_len: int = 22,
) -> list[str]:
    """Pick several substantive sentences plus optional bullet/line chunks for compact recaps.

    Pipeline agents often emit bullets or headings without sentence-ending punctuation; in
    that case we fall back to non-empty lines long enough to carry meaning.

    Args:
        text: Already-cleaned plain text (e.g. after ``_clean_agent_text``).
        max_count: Maximum sentences or line chunks to keep.
        max_chars: Soft cap on total characters for the joined recap.
        min_sentence_len: Minimum length for a sentence to count as substantive.

    Returns:
        Ordered fragments suitable to join with spaces for a readable summary.
    """
    clean = (text or "").strip()
    if not clean:
        return []

    sentences = [s.strip() for s in _sentences(clean) if len(s.strip()) >= min_sentence_len]
    out: list[str] = []
    total = 0
    for s in sentences:
        if out and total + len(s) + 1 > max_chars:
            break
        out.append(s)
        total += len(s) + 1
        if len(out) >= max_count:
            return out

    if len(out) >= 2:
        return out

    # Fallback: long lines (bullets, numbered lists, run-on paragraphs).
    seen_lower = {x.lower() for x in out}
    for raw in clean.splitlines():
        ln = raw.strip()
        ln = re.sub(r"^[\-\*•]+\s*", "", ln)
        ln = re.sub(r"^\d+[.)]\s*", "", ln).strip()
        if len(ln) < min_sentence_len:
            continue
        key = ln.lower()
        if key in seen_lower:
            continue
        if out and key in " ".join(out).lower():
            continue
        out.append(ln)
        seen_lower.add(key)
        total += len(ln) + 1
        if len(out) >= max_count:
            break
        if total >= max_chars:
            break

    if out:
        return out

    # Last resort: first chunk of the cleaned body.
    fallback = clean[:max_chars].strip()
    return [fallback] if fallback else []


def _join_recap_sentences(parts: list[str], *, max_chars: int = 1100) -> str:
    """Join recap fragments and apply a single trailing ellipsis if needed."""
    if not parts:
        return ""
    joined = " ".join(parts).strip()
    if len(joined) <= max_chars:
        return joined
    trimmed = joined[: max_chars - 1].rstrip()
    if not trimmed.endswith("…"):
        trimmed += "…"
    return trimmed


def _normalise_fragment(text: str) -> str:
    fragment = text.strip()
    fragment = fragment.rstrip(" .!?:;,-")
    if fragment and fragment[0].isupper():
        fragment = fragment[:1].lower() + fragment[1:]
    return fragment


def _author_like_summary(agent_id: str, text: str) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean)
    if not parts:
        return "The Author proposes reviewing the full stage output above."
    sentence = parts[0]
    remainder = parts[1:]

    leading_verbs = [
        "use ", "keep ", "add ", "introduce ", "create ", "split ", "move ",
        "make ", "treat ", "store ", "validate ", "separate ", "route ",
    ]
    lowered = sentence.lower()
    for verb in leading_verbs:
        if lowered.startswith(verb):
            action = _normalise_fragment(sentence)
            if agent_id == "design_refiner":
                base = f"The Refiner suggests we {action}."
            else:
                base = f"The Author proposes we {action}."
            if remainder:
                return base + " " + _join_recap_sentences(remainder)
            return base

    action = _normalise_fragment(sentence)
    if agent_id == "design_refiner":
        base = f"The Refiner suggests {action}."
    else:
        base = f"The Author proposes {action}."
    if remainder:
        return base + " " + _join_recap_sentences(remainder)
    return base


def _challenger_summary(text: str) -> str:
    clean = _clean_agent_text(text)

    weakness_match = re.search(
        r"(weakness(?:es)?|concerns?|gaps?)\s*[:\-]?\s*(.*)",
        clean,
        flags=re.IGNORECASE,
    )
    if weakness_match and weakness_match.group(2).strip():
        tail = weakness_match.group(2).strip()
        parts = _substantive_sentence_list(tail)
        if parts:
            head = f"The Challenger highlights that {_normalise_fragment(parts[0])}."
            if len(parts) > 1:
                return head + " " + _join_recap_sentences(parts[1:])
            return head

    parts = _substantive_sentence_list(clean)
    if not parts:
        return "The Challenger highlights trade-offs worth reviewing in the full output."
    head = f"The Challenger highlights that {_normalise_fragment(parts[0])}."
    if len(parts) > 1:
        return head + " " + _join_recap_sentences(parts[1:])
    return head


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

    parts = _substantive_sentence_list(clean)
    if parts:
        head = f"The Judge concludes that {_normalise_fragment(parts[0])}."
        if len(parts) > 1:
            return head + " " + _join_recap_sentences(parts[1:])
        return head
    fragment = _pick_first_substantive_sentence(clean)
    return f"The Judge concludes that {_normalise_fragment(fragment)}."


def _retrieval_planner_summary(text: str) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean)
    if not parts:
        return "The Retrieval planner produced no substantive handoff text; see verbose output."
    recap = _join_recap_sentences(parts)
    return f"The Retrieval planner: {recap}"


def _context_retrieval_summary(text: str) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean)
    if not parts:
        return "Context Retrieval returned little text; expand with /verbose on if needed."
    recap = _join_recap_sentences(parts)
    return f"Context Retrieval: {recap}"


def _context_synthesizer_summary(text: str) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean)
    if not parts:
        return "Context Synthesizer produced no brief; check verbose output."
    recap = _join_recap_sentences(parts)
    return f"Context Synthesizer: {recap}"


def _review_summary(text: str) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean)
    if not parts:
        return "The Review notes points worth reading in the full stage output."
    recap = _join_recap_sentences(parts)
    return f"The Review notes: {recap}"


def _operations_summary(text: str) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean)
    if not parts:
        return "Operations suggests checking the full output for tool and environment detail."
    recap = _join_recap_sentences(parts)
    return f"Operations: {recap}"


def _orchestrator_summary(text: str) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean)
    if not parts:
        return "The Orchestrator recommends reading the full final answer."
    recap = _join_recap_sentences(parts)
    return f"The Orchestrator: {recap}"


def _role_led_summary(agent_id: str, body: str, width: int = 100) -> str:
    if agent_id in {"design", "design_author", "design_refiner"}:
        summary = _author_like_summary(agent_id, body) if agent_id != "design_refiner" else _author_like_summary("design_refiner", body)
    elif agent_id == "design_challenger":
        summary = _challenger_summary(body)
    elif agent_id == "judge":
        summary = _judge_summary(body)
    elif agent_id == "retrieval_planner":
        summary = _retrieval_planner_summary(body)
    elif agent_id == "context_retrieval":
        summary = _context_retrieval_summary(body)
    elif agent_id == "context_synthesizer":
        summary = _context_synthesizer_summary(body)
    elif agent_id == "review":
        summary = _review_summary(body)
    elif agent_id == "operations":
        summary = _operations_summary(body)
    elif agent_id == "orchestrator":
        summary = _orchestrator_summary(body)
    else:
        clean = _clean_agent_text(body)
        parts = _substantive_sentence_list(clean)
        if parts:
            recap = _join_recap_sentences(parts)
            summary = f"{_label(agent_id)}: {recap}"
        else:
            summary = f"{_label(agent_id)}: (no recap; use verbose output)"

    wrapped = textwrap.wrap(summary, width=width, break_long_words=False, break_on_hyphens=False)
    max_lines = 14
    if len(wrapped) <= max_lines:
        return "\n".join(wrapped)

    trimmed = wrapped[:max_lines]
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
            Text(body.strip() or "_empty_"),
            title=panel_title,
            border_style=_RENDER_STYLES["status"],
            padding=(0, 1),
            expand=True,
        )
    )


def print_agent_output(agent_id: str, body: str, *, verbose: bool) -> None:
    """Print one agent stage result in a bordered panel.

    The body is always rendered with Rich ``Markdown`` so lists, headings, code
    fences, and emphasis stay structured in the terminal—whether or not the user
    enabled verbose mode elsewhere in the session.

    Args:
        agent_id: Registry agent identifier for icons and styling.
        body: Stage text (Markdown-friendly) from the model.
        verbose: Reserved for callers (e.g. pipeline engine); stage panels use the
            same Markdown rendering regardless so output stays readable with
            ``/verbose off``.
    """
    _ = verbose
    icon = _icon(agent_id)
    label = _label(agent_id)
    style = _style(agent_id)
    title = Text(f"{icon} {label}", style=f"bold {style}")
    rendered_body = Markdown(body.strip() or "_empty_")
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
