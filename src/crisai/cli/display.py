from __future__ import annotations

import contextvars
import os
import re
import textwrap
from typing import Literal

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from crisai.orchestration.semantic_catalog import load_semantic_catalog

from .peer_transcript import PeerMessage

console = Console()
_ACTIVE_DISPLAY_SINK: contextvars.ContextVar[object | None] = contextvars.ContextVar(
    "crisai_active_display_sink",
    default=None,
)
_ACTIVE_RUNTIME_FOOTER: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "crisai_active_runtime_footer",
    default=None,
)

RenderKind = Literal["status", "stage", "final"]

_ICONS = {
    "retrieval_planner": "🔍",
    "context_retrieval": "📖",
    "context_synthesizer": "🧬",
    "design": "🎨",
    "summary": "📑",
    "design_author": "✍️",
    "design_challenger": "🤺",
    "design_refiner": "💎",
    "review": "🔎",
    "judge": "🏛️",
    "orchestrator": "🛰️",
    "operations": "🛠️",
    "memory_summarizer": "🧠",
    "publisher": "🚢",
    "document_formatter": "🎭",
}

_LABELS = {
    "retrieval_planner": "Planner",
    "context_retrieval": "Retrieval",
    "context_synthesizer": "Synthesis",
    "design": "Design",
    "summary": "Summary",
    "design_author": "Author",
    "design_challenger": "Challenger",
    "design_refiner": "Refiner",
    "review": "Review",
    "judge": "Judge",
    "orchestrator": "Orchestrator",
    "operations": "Ops",
    "memory_summarizer": "Memory",
    "publisher": "Publisher",
    "document_formatter": "Formatter",
}

_STYLES = {
    "retrieval_planner": "bright_yellow",
    "context_retrieval": "bright_cyan",
    "context_synthesizer": "bright_magenta",
    "design": "bright_green",
    "summary": "bright_green",
    "design_author": "bright_green",
    "design_challenger": "bright_blue",
    "design_refiner": "bright_red",
    "review": "bright_yellow",
    "judge": "bright_white",
    "orchestrator": "bright_black",
    "operations": "bright_blue",
    "memory_summarizer": "bright_cyan",
    "publisher": "bright_magenta",
    "document_formatter": "bright_magenta",
}

_RENDER_TITLES = {
    "status": "◇ Status",
    "stage": "✦ Stage Output",
    "final": "📡 Final Answer",
}

_RENDER_STYLES = {
    "status": "bright_blue",
    "stage": "dim",
    "final": "bold white",
}


def update_terminal_title(status: Literal["ready", "working", "input"]):
    """Update the terminal window title with status icons."""
    if os.getenv("CRISAI_TERMINAL_TITLE_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return
    icons = {"ready": "◇", "working": "✦", "input": "✋"}
    icon = icons.get(status, "◇")
    # OSC 0; title BEL
    print(f"\033]0;{icon} crisAI\a", end="", flush=True)


class AgentDisplayManager:
    """Manages real-time progress and output for an agent stage."""

    def __init__(self, agent_id: str, console: Console = console):
        self.agent_id = agent_id
        self.console = console
        self.sink = _ACTIVE_DISPLAY_SINK.get()
        self.icon = _ICONS.get(agent_id, "🤖")
        self.label = _LABELS.get(agent_id, agent_id.capitalize())
        self.style = _STYLES.get(agent_id, "white")
        self.current_topic = "Initializing..."
        self.live = None
        if self.sink is None:
            self.live = Live(
                self._render(),
                console=self.console,
                refresh_per_second=4,
                transient=True,
            )

    def _render(self) -> Panel:
        title = Text(f"{self.icon} {self.label}", style=f"bold {self.style}")
        body_lines = [
            Text.assemble(
                ("✦ ", f"bold {self.style}"),
                (self.current_topic, "italic dim"),
            )
        ]
        footer = _ACTIVE_RUNTIME_FOOTER.get()
        if footer:
            body_lines.extend([Text(""), Text(footer, style="reverse")])
        return Panel(
            Group(*body_lines),
            title=title,
            border_style=self.style,
            padding=(0, 1),
            expand=True,
        )

    def update(self, topic: str):
        self.current_topic = topic
        if self.sink is not None and hasattr(self.sink, "agent_progress"):
            self.sink.agent_progress(self.agent_id, topic)
            return
        if self.live is not None:
            self.live.update(self._render())

    def __enter__(self):
        if self.sink is not None and hasattr(self.sink, "agent_started"):
            self.sink.agent_started(self.agent_id, self.current_topic)
        elif self.live is not None:
            self.live.start()
        update_terminal_title("working")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.sink is not None and hasattr(self.sink, "agent_finished"):
            self.sink.agent_finished(self.agent_id)
        elif self.live is not None:
            self.live.stop()
        update_terminal_title("ready")


def set_active_display_sink(sink: object | None) -> contextvars.Token:
    """Set the current display sink for context-scoped CLI rendering."""
    return _ACTIVE_DISPLAY_SINK.set(sink)


def reset_active_display_sink(token: contextvars.Token) -> None:
    """Restore the previous display sink."""
    _ACTIVE_DISPLAY_SINK.reset(token)


def set_active_runtime_footer(footer: str | None) -> contextvars.Token:
    """Set the runtime footer shown inside classic agent progress panels."""
    return _ACTIVE_RUNTIME_FOOTER.set(footer)


def reset_active_runtime_footer(token: contextvars.Token) -> None:
    """Restore the previous runtime footer."""
    _ACTIVE_RUNTIME_FOOTER.reset(token)


def get_bottom_toolbar(
    *,
    session: str,
    mode: str,
    agent: str,
    model: str,
    verbose: bool,
    review: bool,
    retrieval_checkpoint: bool,
    mode_pinned: bool,
    agent_pinned: bool,
) -> str:
    """Return the compact prompt-toolkit status bar for interactive chat."""
    mode_label = f"{mode}{'*' if mode_pinned else ''}"
    agent_label = agent if agent_pinned else "auto"
    return (
        f" ⬡ {session}"
        f" | mode:{mode_label}"
        f" | agent:{agent_label}"
        f" | model:{model}"
        f" | verbose:{_on_off(verbose)}"
        f" | review:{_on_off(review)}"
        f" | checkpoint:{_on_off(retrieval_checkpoint)} "
    )


def _on_off(value: bool) -> str:
    return "on" if value else "off"


_FENCED_CODE_BLOCK_RE = re.compile(r"```[^\n`]*\n.*?```", re.DOTALL)
_MACHINE_SCHEMA_RE = re.compile(
    r'"schema_version"\s*:\s*"(?:evidence_bundle_v1|task_contract_v1|request_contract_v1)"',
    re.IGNORECASE,
)
_MACHINE_JSON_KEY_RE = re.compile(
    r'"(?:schema_version|topics_activated|queries_expanded|source_priority)"\s*:',
    re.IGNORECASE,
)


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


def sanitize_user_visible_text(text: str) -> str:
    """Remove machine-readable JSON contracts from user-facing CLI rendering."""
    original = text or ""
    cleaned = _strip_fenced_machine_blocks(original)
    cleaned = _strip_bare_machine_objects(cleaned)
    cleaned = _strip_trailing_json_fence(cleaned)
    if cleaned != original:
        cleaned = _strip_orphan_json_fence_lines(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _hide_machine_evidence_blocks(text: str) -> str:
    """Backward-compatible wrapper for user-visible sanitization."""
    return sanitize_user_visible_text(text)


def _strip_fenced_machine_blocks(text: str) -> str:
    """Remove fenced code blocks that contain a machine schema marker."""
    parts: list[str] = []
    cursor = 0
    for match in _FENCED_CODE_BLOCK_RE.finditer(text):
        parts.append(text[cursor : match.start()])
        block = match.group(0)
        if not _MACHINE_JSON_KEY_RE.search(block):
            parts.append(block)
        cursor = match.end()
    parts.append(text[cursor:])
    return "".join(parts)


def _strip_bare_machine_objects(text: str) -> str:
    """Remove bare machine JSON objects using balanced braces instead of regex."""
    output: list[str] = []
    cursor = 0
    while True:
        marker = _MACHINE_JSON_KEY_RE.search(text, cursor)
        if marker is None:
            output.append(text[cursor:])
            break
        start = text.rfind("{", cursor, marker.start())
        if start == -1:
            output.append(text[cursor : marker.end()])
            cursor = marker.end()
            continue
        end = _find_json_object_end(text, start)
        if end is None:
            output.append(text[cursor:start])
            break
        output.append(text[cursor:start])
        cursor = end
    return "".join(output)


def _strip_trailing_json_fence(text: str) -> str:
    """Remove a dangling opening JSON fence left after machine JSON stripping."""
    return re.sub(r"\n?\s*```(?:json)?\s*$", "", text, flags=re.IGNORECASE)


def _strip_orphan_json_fence_lines(text: str) -> str:
    """Remove isolated fence markers left behind by stripped machine blocks."""
    return re.sub(r"(?im)^\s*```(?:json)?\s*$\n?", "", text)


def _find_json_object_end(text: str, start: int) -> int | None:
    """Return the index after a balanced JSON object starting at ``start``."""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def _clean_agent_text(text: str) -> str:
    clean = _strip_markdown(text)

    boilerplate_patterns = load_semantic_catalog().peer_verifier.boilerplate_strip_patterns
    changed = True
    while changed:
        changed = False
        for pattern in boilerplate_patterns:
            new_clean = pattern.sub("", clean).strip()
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


def _truncate_for_summary(text: str, limit: int) -> str:
    """Shorten *text* to *limit* characters near a word boundary, then add an ellipsis.

    Used so markdown-heavy agent output without sentence-ending punctuation cannot
    bypass ``/verbose off`` by appearing as a single giant "sentence".

    Args:
        text: Plain or stripped text to shorten.
        limit: Maximum character length including the trailing ellipsis character.

    Returns:
        Trimmed text ending with ``…`` when truncation occurred.
    """
    text = (text or "").strip()
    if limit <= 1:
        return "…"
    if len(text) <= limit:
        return text
    chunk = text[: limit - 1]
    if " " in chunk:
        chunk = chunk.rsplit(" ", 1)[0]
    # Avoid a dangling article or other 1–2 character tail before "…" (e.g. "needs a…").
    while " " in chunk:
        _head, tail = chunk.rsplit(" ", 1)
        if len(tail) >= 3:
            break
        chunk = _head
    chunk = chunk.rstrip(" ,;:")
    if not chunk:
        return text[: max(1, limit - 1)] + "…"
    return chunk + "…"


def _strip_compact_agent_prefix(agent_id: str, summary: str) -> str:
    """Remove role lead-in text when the panel title already names the agent.

    Args:
        agent_id: Registry agent id for this stage.
        summary: Plain-text line from ``_role_led_summary(..., compact=True)``.

    Returns:
        *summary* without a redundant "Agent: …" prefix when a pattern matches.
    """
    signatures = load_semantic_catalog().peer_verifier.agent_output_signatures
    pattern = signatures.get(agent_id)
    if pattern:
        stripped = pattern.sub("", summary, count=1).strip()
        return stripped if stripped else summary
    label = _label(agent_id)
    stripped = re.sub(rf"^{re.escape(label)}:\s*", "", summary, count=1, flags=re.I).strip()
    return stripped if stripped else summary


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
        space = 1 if out else 0
        room = max_chars - total - space
        if room < min_sentence_len:
            break
        if len(s) > room:
            s = _truncate_for_summary(s, room)
        if len(s) < min_sentence_len:
            continue
        total += len(s) + space
        out.append(s)
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
        space = 1 if out else 0
        room = max_chars - total - space
        if room < min_sentence_len:
            break
        if len(ln) > room:
            ln = _truncate_for_summary(ln, room)
        if len(ln) < min_sentence_len:
            continue
        total += len(ln) + space
        out.append(ln)
        seen_lower.add(key)
        if len(out) >= max_count:
            break

    if out:
        return out

    # Last resort: excerpt only (model output may lack ``.?!`` so never return unbounded text).
    if len(clean) <= max_chars:
        return [clean] if clean else []
    return [_truncate_for_summary(clean, max_chars)]


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


def _author_like_summary(
    agent_id: str,
    text: str,
    *,
    max_fragments: int = 4,
    max_chars: int = 1100,
) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean, max_count=max_fragments, max_chars=max_chars)
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
                return base + " " + _join_recap_sentences(remainder, max_chars=max_chars)
            return base

    action = _normalise_fragment(sentence)
    if agent_id == "design_refiner":
        base = f"The Refiner suggests {action}."
    else:
        base = f"The Author proposes {action}."
    if remainder:
        return base + " " + _join_recap_sentences(remainder, max_chars=max_chars)
    return base


def _challenger_summary(
    text: str,
    *,
    max_fragments: int = 4,
    max_chars: int = 1100,
) -> str:
    clean = _clean_agent_text(text)

    weakness_match = re.search(
        r"(weakness(?:es)?|concerns?|gaps?)\s*[:\-]?\s*(.*)",
        clean,
        flags=re.IGNORECASE,
    )
    if weakness_match and weakness_match.group(2).strip():
        tail = weakness_match.group(2).strip()
        parts = _substantive_sentence_list(tail, max_count=max_fragments, max_chars=max_chars)
        if parts:
            head = f"The Challenger highlights that {_normalise_fragment(parts[0])}."
            if len(parts) > 1:
                return head + " " + _join_recap_sentences(parts[1:], max_chars=max_chars)
            return head

    parts = _substantive_sentence_list(clean, max_count=max_fragments, max_chars=max_chars)
    if not parts:
        return "The Challenger highlights trade-offs worth reviewing in the full output."
    head = f"The Challenger highlights that {_normalise_fragment(parts[0])}."
    if len(parts) > 1:
        return head + " " + _join_recap_sentences(parts[1:], max_chars=max_chars)
    return head


def _judge_summary(
    text: str,
    *,
    max_fragments: int = 4,
    max_chars: int = 1100,
) -> str:
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

    parts = _substantive_sentence_list(clean, max_count=max_fragments, max_chars=max_chars)
    if parts:
        head = f"The Judge concludes that {_normalise_fragment(parts[0])}."
        if len(parts) > 1:
            return head + " " + _join_recap_sentences(parts[1:], max_chars=max_chars)
        return head
    fragment = _pick_first_substantive_sentence(clean)
    return f"The Judge concludes that {_normalise_fragment(fragment)}."


def _retrieval_planner_summary(
    text: str,
    *,
    max_fragments: int = 4,
    max_chars: int = 1100,
) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean, max_count=max_fragments, max_chars=max_chars)
    if not parts:
        return "The Retrieval planner produced no substantive handoff text; see verbose output."
    recap = _join_recap_sentences(parts, max_chars=max_chars)
    return f"The Retrieval planner: {recap}"


def _context_retrieval_summary(
    text: str,
    *,
    max_fragments: int = 4,
    max_chars: int = 1100,
) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean, max_count=max_fragments, max_chars=max_chars)
    if not parts:
        return "Context Retrieval returned little text; expand with /verbose on if needed."
    recap = _join_recap_sentences(parts, max_chars=max_chars)
    return f"Context Retrieval: {recap}"


def _context_synthesizer_summary(
    text: str,
    *,
    max_fragments: int = 4,
    max_chars: int = 1100,
) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean, max_count=max_fragments, max_chars=max_chars)
    if not parts:
        return "Context Synthesizer produced no brief; check verbose output."
    recap = _join_recap_sentences(parts, max_chars=max_chars)
    return f"Context Synthesizer: {recap}"


def _review_summary(
    text: str,
    *,
    max_fragments: int = 4,
    max_chars: int = 1100,
) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean, max_count=max_fragments, max_chars=max_chars)
    if not parts:
        return "The Review notes points worth reading in the full stage output."
    recap = _join_recap_sentences(parts, max_chars=max_chars)
    return f"The Review notes: {recap}"


def _summary_agent_summary(
    text: str,
    *,
    max_fragments: int = 4,
    max_chars: int = 1100,
) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean, max_count=max_fragments, max_chars=max_chars)
    if not parts:
        return "Summary produced no substantive text; check verbose output."
    recap = _join_recap_sentences(parts, max_chars=max_chars)
    return f"Summary: {recap}"


def _operations_summary(
    text: str,
    *,
    max_fragments: int = 4,
    max_chars: int = 1100,
) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean, max_count=max_fragments, max_chars=max_chars)
    if not parts:
        return "Operations suggests checking the full output for tool and environment detail."
    recap = _join_recap_sentences(parts, max_chars=max_chars)
    return f"Operations: {recap}"


def _orchestrator_summary(
    text: str,
    *,
    max_fragments: int = 4,
    max_chars: int = 1100,
) -> str:
    clean = _clean_agent_text(text)
    parts = _substantive_sentence_list(clean, max_count=max_fragments, max_chars=max_chars)
    if not parts:
        return "The Orchestrator recommends reading the full final answer."
    recap = _join_recap_sentences(parts, max_chars=max_chars)
    return f"The Orchestrator: {recap}"


def _role_led_summary(agent_id: str, body: str, width: int = 100, *, compact: bool = False) -> str:
    """Plain-text recap for an agent stage.

    Args:
        agent_id: Registry agent id.
        body: Raw stage output (may contain Markdown; stripped for recaps).
        width: Wrap width for terminal display.
        compact: When True, keep a single substantive fragment and a shorter char budget
            for ``/verbose off`` panels.
    """
    mf = 1 if compact else 4
    # /verbose off: one scannable recap; panel title already names the agent.
    mc = 400 if compact else 1100
    if agent_id in {"design", "design_author", "design_refiner"}:
        summary = (
            _author_like_summary(agent_id, body, max_fragments=mf, max_chars=mc)
            if agent_id != "design_refiner"
            else _author_like_summary("design_refiner", body, max_fragments=mf, max_chars=mc)
        )
    elif agent_id == "design_challenger":
        summary = _challenger_summary(body, max_fragments=mf, max_chars=mc)
    elif agent_id == "judge":
        summary = _judge_summary(body, max_fragments=mf, max_chars=mc)
    elif agent_id == "retrieval_planner":
        summary = _retrieval_planner_summary(body, max_fragments=mf, max_chars=mc)
    elif agent_id == "context_retrieval":
        summary = _context_retrieval_summary(body, max_fragments=mf, max_chars=mc)
    elif agent_id == "context_synthesizer":
        summary = _context_synthesizer_summary(body, max_fragments=mf, max_chars=mc)
    elif agent_id == "summary":
        summary = _summary_agent_summary(body, max_fragments=mf, max_chars=mc)
    elif agent_id == "review":
        summary = _review_summary(body, max_fragments=mf, max_chars=mc)
    elif agent_id == "operations":
        summary = _operations_summary(body, max_fragments=mf, max_chars=mc)
    elif agent_id == "orchestrator":
        summary = _orchestrator_summary(body, max_fragments=mf, max_chars=mc)
    else:
        clean = _clean_agent_text(body)
        parts = _substantive_sentence_list(clean, max_count=mf, max_chars=mc)
        if parts:
            recap = _join_recap_sentences(parts, max_chars=mc)
            summary = f"{_label(agent_id)}: {recap}"
        else:
            summary = f"{_label(agent_id)}: (no recap; use verbose output)"

    if compact:
        # Length is already capped via *mc* and ``_truncate_for_summary``. Do not run a
        # second ``textwrap`` slice: taking the first N wrapped lines dropped tail content
        # and left stub lines such as ``a…`` when a word wrapped across the boundary.
        return summary

    max_lines = 14
    wrapped = textwrap.wrap(summary, width=width, break_long_words=False, break_on_hyphens=False)
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
    sink = _ACTIVE_DISPLAY_SINK.get()
    if sink is not None and hasattr(sink, "status"):
        sink.status(body, title=title)
        return
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

    With ``/verbose off``, shows one concise sentence-style recap as Markdown
    (``**Summary:** …``). With ``/verbose on``, renders the full stage body as
    Markdown so structure is preserved.

    Args:
        agent_id: Registry agent identifier for icons and styling.
        body: Stage text (Markdown-friendly) from the model.
        verbose: When True, print the full ``body``; when False, print a generated summary.
    """
    rendered_text = render_stage_output_text(agent_id, body, verbose=verbose)
    sink = _ACTIVE_DISPLAY_SINK.get()
    if sink is not None and hasattr(sink, "stage_output"):
        sink.stage_output(agent_id, rendered_text, verbose=verbose)
        return
    icon = _icon(agent_id)
    label = _label(agent_id)
    style = _style(agent_id)
    title = Text(f"{icon} {label}", style=f"bold {style}")
    rendered_body = Markdown(rendered_text)
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


def render_stage_output_text(agent_id: str, body: str, *, verbose: bool) -> str:
    """Return user-facing Markdown for one stage body.

    Normal mode is intentionally concise and shared by CLI and web. Verbose mode
    may preserve more structure, but still removes machine-readable contracts.
    """
    display_body = _hide_machine_evidence_blocks(body)
    if verbose:
        return display_body.strip() or "_empty_"
    recap = _role_led_summary(agent_id, display_body, compact=True).strip()
    recap = _strip_compact_agent_prefix(agent_id, recap)
    return f"**Summary:** {recap}" if recap else "**Summary:** _(empty)_"


def render_peer_message(message: PeerMessage) -> Panel:
    speaker = message.speaker
    title = Text(f"{_icon(speaker)} {_label(speaker)}", style=f"bold {_style(speaker)}")
    subtitle = Text(_RENDER_TITLES["stage"], style=f"italic {_RENDER_STYLES['stage']}")
    if getattr(message, "step", ""):
        subtitle = Text(f"{_RENDER_TITLES['stage']} • {message.step}", style=f"italic {_style(speaker)}")

    content = _hide_machine_evidence_blocks(message.content or "").strip() or "_empty_"

    return Panel(
        Markdown(content),
        title=title,
        subtitle=subtitle,
        border_style=_style(speaker),
        padding=(0, 1),
        expand=True,
    )


def print_final_answer(body: str, *, title: str | None = None) -> None:
    sink = _ACTIVE_DISPLAY_SINK.get()
    if sink is not None and hasattr(sink, "final"):
        sink.final(body, title=title)
        return
    panel_title = Text(title or _RENDER_TITLES["final"], style=f"bold {_RENDER_STYLES['final']}")
    display_body = _hide_machine_evidence_blocks(body)
    console.print(
        Panel(
            Markdown(display_body.strip() or "_empty_"),
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
