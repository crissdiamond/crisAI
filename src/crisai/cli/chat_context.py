from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from crisai.cli.display import sanitize_user_visible_text
from crisai.cli.session_store import (
    HistoryEntry,
    SessionMemory,
    load_session_anchors,
    load_session_memory,
    save_session_anchors,
    save_session_memory,
    task_dir,
)
from crisai.cli.text_loader import render_cli_text
from crisai.config import load_settings
from crisai.orchestration.session_anchors import (
    extract_session_anchors_from_history,
    render_anchor_registry,
    render_resolved_anchor_references,
    resolve_anchor_references,
)
from crisai.workspace.spaces import load_workspace_spaces

_DEFAULT_CONFIG = {
    "strategy": "deterministic",
    "agentic_agent_id": "memory_summarizer",
    "max_recent_turns": 2,
    "max_runtime_chars": 6000,
    "max_memory_chars": 3000,
    "task_drift_nudge": True,
}
_SOURCE_PATH_RE = re.compile(r"`((?:context|knowledge|knowledge_staging|tasks|workspace)/[^`]+)`")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]{3,160})\]\(([^)]+)\)")
_NOISE_SECTION_RE = re.compile(
    r"(?ims)^(\|.*\|\n\|[-:| ]+\|\n(?:\|.*\|\n?)+|```(?:json)?\s*\{.*?schema_version.*?\}\s*```)"
)
_LEGACY_WORKSPACE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_/-])(?:workspace/)?context(?=/)")


@dataclass(frozen=True, slots=True)
class SessionMemoryConfig:
    """Runtime settings for compact session memory."""

    strategy: str = "deterministic"
    agentic_agent_id: str = "memory_summarizer"
    max_recent_turns: int = 2
    max_runtime_chars: int = 6000
    max_memory_chars: int = 3000
    task_drift_nudge: bool = True


@dataclass(frozen=True, slots=True)
class RuntimeContextPackage:
    """Prompt package built from raw history plus compact memory."""

    prompt: str
    memory: SessionMemory
    included_recent_entries: int
    truncated: bool
    drift_nudge: str = ""


def load_session_memory_config(registry_dir: Path | None = None) -> SessionMemoryConfig:
    """Load session memory config from registry/session_memory.yaml."""
    root = registry_dir or load_settings().registry_dir
    path = root / "session_memory.yaml"
    payload: dict[str, object] = {}
    if path.is_file():
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            block = raw.get("session_memory") if isinstance(raw, dict) else {}
            payload = block if isinstance(block, dict) else {}
        except (OSError, yaml.YAMLError):
            payload = {}
    env_overrides = {
        "strategy": os.getenv("CRISAI_SESSION_MEMORY_STRATEGY"),
        "agentic_agent_id": os.getenv("CRISAI_SESSION_MEMORY_AGENT_ID"),
        "max_recent_turns": os.getenv("CRISAI_SESSION_MEMORY_MAX_RECENT_TURNS"),
        "max_runtime_chars": os.getenv("CRISAI_SESSION_MEMORY_MAX_RUNTIME_CHARS"),
        "max_memory_chars": os.getenv("CRISAI_SESSION_MEMORY_MAX_MEMORY_CHARS"),
        "task_drift_nudge": os.getenv("CRISAI_SESSION_MEMORY_TASK_DRIFT_NUDGE"),
    }
    merged = {**_DEFAULT_CONFIG, **{k: v for k, v in payload.items() if v is not None}}
    merged.update({k: v for k, v in env_overrides.items() if v is not None})
    strategy = str(merged.get("strategy") or "deterministic").strip().lower()
    if strategy not in {"deterministic", "agentic"}:
        strategy = "deterministic"
    return SessionMemoryConfig(
        strategy=strategy,
        agentic_agent_id=str(merged.get("agentic_agent_id") or "memory_summarizer"),
        max_recent_turns=max(0, _int_setting(merged.get("max_recent_turns"), 2)),
        max_runtime_chars=max(1000, _int_setting(merged.get("max_runtime_chars"), 6000)),
        max_memory_chars=max(500, _int_setting(merged.get("max_memory_chars"), 3000)),
        task_drift_nudge=_bool_setting(merged.get("task_drift_nudge"), True),
    )


def render_history(history: list[HistoryEntry]) -> str:
    """Renders chat history as a transcript for prompt wrapping."""
    if not history:
        return ""

    lines: list[str] = []
    for role, content in history:
        if role == "user":
            lines.append(f"User: {content}")
        else:
            lines.append(f"Assistant: {sanitize_user_visible_text(content)}")

    return "\n\n".join(lines)


def compact_session_memory(history: list[HistoryEntry], *, max_memory_chars: int = 3000) -> SessionMemory:
    """Create deterministic compact memory from a raw session transcript."""
    if not history:
        return SessionMemory()
    user_messages = [_clean_for_memory(content) for role, content in history if role == "user" and content.strip()]
    assistant_messages = [
        _clean_for_memory(sanitize_user_visible_text(content))
        for role, content in history
        if role == "assistant" and content.strip()
    ]
    sources = _extract_sources(history)
    task_goal = _truncate(user_messages[-1] if user_messages else "", 500)
    last_outputs = [_truncate(item, 500) for item in assistant_messages[-2:]]
    current_state = _truncate(last_outputs[-1] if last_outputs else task_goal, 800)
    decisions = _extract_decisions(assistant_messages)
    open_questions = [
        _truncate(item, 240)
        for item in user_messages[-4:]
        if "?" in item or item.lower().startswith(("can ", "should ", "why ", "how "))
    ]
    do_not_repeat = [
        "Do not repeat old source tables or previous final answers unless the user explicitly asks.",
        "Prefer compact source references over copied historical prose.",
    ]
    memory = SessionMemory(
        task_goal=_truncate(task_goal, max_memory_chars // 3),
        current_state=_truncate(current_state, max_memory_chars // 3),
        important_decisions=decisions[:8],
        known_sources=sources[:12],
        open_questions=open_questions[:5],
        last_outputs=last_outputs,
        do_not_repeat=do_not_repeat,
    )
    return _limit_memory(memory, max_memory_chars)


def update_session_memory(session_name: str, history: list[HistoryEntry], config: SessionMemoryConfig | None = None) -> SessionMemory:
    """Rebuild and persist compact memory for a session."""
    cfg = config or load_session_memory_config()
    # Agentic memory is intentionally routed through the same persisted contract
    # until the dedicated memory agent is wired into runtime execution.
    memory = compact_session_memory(history, max_memory_chars=cfg.max_memory_chars)
    save_session_memory(session_name, memory)
    anchors = extract_session_anchors_from_history(history, registry_dir=load_settings().registry_dir)
    save_session_anchors(session_name, anchors)
    return memory


def build_runtime_context_package(
    user_input: str,
    history: list[HistoryEntry],
    *,
    session_name: str | None = None,
    config: SessionMemoryConfig | None = None,
) -> RuntimeContextPackage:
    """Build bounded runtime context for agent execution."""
    user_input = normalise_legacy_workspace_paths(user_input)
    if not history:
        return RuntimeContextPackage(prompt=user_input, memory=SessionMemory(), included_recent_entries=0, truncated=False)
    cfg = config or load_session_memory_config()
    memory = load_session_memory(session_name) if session_name else SessionMemory()
    anchors = load_session_anchors(session_name) if session_name else None
    resolved_anchors = resolve_anchor_references(user_input, anchors, registry_dir=load_settings().registry_dir) if anchors else ()
    if not any((memory.task_goal, memory.current_state, memory.known_sources, memory.last_outputs)):
        memory = compact_session_memory(history, max_memory_chars=cfg.max_memory_chars)
    recent = _relevant_recent_entries(user_input, history, max_entries=cfg.max_recent_turns * 2)
    memory_text = render_session_memory(memory)
    transcript = render_history(recent)
    truncated = False
    if len(transcript) + len(memory_text) > cfg.max_runtime_chars:
        budget = max(0, cfg.max_runtime_chars - len(memory_text) - 500)
        transcript = _truncate(transcript, budget)
        truncated = True
    runtime_context = "\n\n".join(
        part
        for part in [
            "Active task workspace:\n"
            + f"- Task session: {session_name}\n"
            + f"- Task root: workspace/tasks/{task_dir(session_name).name}\n"
            + f"- Artefacts: workspace/tasks/{task_dir(session_name).name}/artefacts\n"
            + f"- Inputs: workspace/tasks/{task_dir(session_name).name}/inputs"
            if session_name
            else "",
            "Compact session memory:\n" + memory_text if memory_text else "",
            "Session anchors:\n" + render_anchor_registry(anchors) if anchors and anchors.anchors else "",
            "Resolved user references:\n"
            + render_resolved_anchor_references(resolved_anchors)
            + "\n\nUse these resolved references as authoritative labels/titles. Do not renumber or reinterpret them."
            if resolved_anchors
            else "",
            "Relevant recent turns:\n" + transcript if transcript else "",
        ]
        if part.strip()
    )
    if not runtime_context.strip():
        return RuntimeContextPackage(prompt=user_input, memory=memory, included_recent_entries=0, truncated=False)
    prompt = render_cli_text(
        "chat/history_wrapper.md",
        transcript=runtime_context,
        user_input=user_input,
    )
    drift_nudge = detect_task_drift(user_input, memory) if cfg.task_drift_nudge else ""
    return RuntimeContextPackage(
        prompt=prompt,
        memory=memory,
        included_recent_entries=len(recent),
        truncated=truncated,
        drift_nudge=drift_nudge,
    )


def render_session_memory(memory: SessionMemory) -> str:
    """Render compact memory as human-readable runtime context."""
    sections = []
    if memory.task_goal:
        sections.append(f"Task goal: {memory.task_goal}")
    if memory.current_state:
        sections.append(f"Current state: {memory.current_state}")
    for label, values in (
        ("Important decisions", memory.important_decisions),
        ("Known sources", memory.known_sources),
        ("Open questions", memory.open_questions),
        ("Recent outputs", memory.last_outputs),
        ("Do not repeat", memory.do_not_repeat),
    ):
        if values:
            sections.append(label + ":\n" + "\n".join(f"- {item}" for item in values))
    return "\n\n".join(sections)


def detect_task_drift(user_input: str, memory: SessionMemory) -> str:
    """Return a non-blocking session nudge when latest input diverges from memory."""
    if not memory.task_goal:
        return ""
    current_terms = _content_terms(user_input)
    memory_terms = _content_terms(" ".join([memory.task_goal, memory.current_state, " ".join(memory.known_sources)]))
    if len(current_terms) < 4 or len(memory_terms) < 4:
        return ""
    overlap = current_terms & memory_terms
    if len(overlap) <= 1:
        return "This looks like a new task. Consider `/session new <name>` to avoid carrying old context."
    return ""


def build_chat_input(user_input: str, history: list[HistoryEntry], *, session_name: str | None = None) -> str:
    """Builds the message passed to the agent runtime.

    Raw history is compacted into task memory plus a small relevant recent tail.
    """
    return build_runtime_context_package(user_input, history, session_name=session_name).prompt


def normalise_legacy_workspace_paths(text: str) -> str:
    """Map pre-refactor workspace path wording to the configured knowledge root."""
    if not text:
        return ""
    return _LEGACY_WORKSPACE_PATH_RE.sub("workspace/knowledge", text)


def _int_setting(value: object, default: int) -> int:
    try:
        if isinstance(value, (str, bytes, bytearray, int, float)):
            return int(value)
    except (TypeError, ValueError):
        return default
    return default


def _bool_setting(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _clean_for_memory(text: str) -> str:
    clean = sanitize_user_visible_text(text or "")
    clean = _NOISE_SECTION_RE.sub("", clean)
    return re.sub(r"\n{3,}", "\n\n", clean).strip()


def _extract_sources(history: list[HistoryEntry]) -> list[str]:
    seen: set[str] = set()
    sources: list[str] = []
    for _role, content in history:
        text = sanitize_user_visible_text(content)
        for match in _SOURCE_PATH_RE.finditer(text):
            value = _canonical_source_path(match.group(1).strip())
            if value not in seen:
                seen.add(value)
                sources.append(value)
        for match in _MARKDOWN_LINK_RE.finditer(text):
            value = _canonical_source_path(_source_from_markdown_link(match.group(1), match.group(2)))
            if value and value not in seen and len(value.split()) <= 12:
                seen.add(value)
                sources.append(value)
    return sources


def _source_from_markdown_link(label: str, href: str) -> str:
    """Extract a workspace source path from a Markdown link label or href."""
    href_text = (href or "").strip()
    marker = "/workspace/"
    if marker in href_text:
        return href_text.split(marker, 1)[1]
    return (label or "").strip()


def _canonical_source_path(path: str) -> str:
    """Normalize source paths in session memory to configured workspace roots."""
    return load_workspace_spaces().canonicalize_workspace_path(path)


def _extract_decisions(messages: list[str]) -> list[str]:
    decisions: list[str] = []
    markers = ("recommend", "should", "do not", "use ", "target state", "interim")
    for message in messages[-6:]:
        for sentence in re.split(r"(?<=[.!?])\s+", message):
            stripped = sentence.strip(" -*\n")
            if 30 <= len(stripped) <= 260 and any(marker in stripped.lower() for marker in markers):
                decisions.append(stripped)
                break
    return list(dict.fromkeys(decisions))


def _relevant_recent_entries(user_input: str, history: list[HistoryEntry], *, max_entries: int) -> list[HistoryEntry]:
    if max_entries <= 0:
        return []
    query_terms = _content_terms(user_input)
    recent = history[-max_entries:]
    if not query_terms:
        return recent
    relevant = [
        (role, _truncate(_clean_for_memory(content), 1200))
        for role, content in recent
        if query_terms & _content_terms(content)
    ]
    return relevant or [(role, _truncate(_clean_for_memory(content), 1200)) for role, content in recent[-2:]]


def _content_terms(text: str) -> set[str]:
    stop = {"the", "and", "for", "with", "that", "this", "from", "into", "about", "using", "please", "would"}
    return {token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", (text or "").lower()) if token not in stop}


def _limit_memory(memory: SessionMemory, max_chars: int) -> SessionMemory:
    rendered = render_session_memory(memory)
    if len(rendered) <= max_chars:
        return memory
    return SessionMemory(
        task_goal=_truncate(memory.task_goal, 500),
        current_state=_truncate(memory.current_state, 700),
        important_decisions=memory.important_decisions[:4],
        known_sources=memory.known_sources[:8],
        open_questions=memory.open_questions[:3],
        last_outputs=[_truncate(item, 350) for item in memory.last_outputs[:1]],
        do_not_repeat=memory.do_not_repeat,
    )


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    clean = (text or "").strip()
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 1].rstrip() + "…"
