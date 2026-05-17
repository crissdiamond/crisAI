from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from crisai.cli.display import sanitize_user_visible_text
from crisai.cli.session_store import (
    HistoryEntry,
    SessionMemory,
    load_session_anchors,
    load_session_memory,
    sanitize_session_name,
    save_session_anchors,
    save_session_memory,
)
from crisai.cli.text_loader import render_cli_text
from crisai.config import load_settings
from crisai.orchestration.retrieval_association_graph import (
    deterministic_context_from_registry,
)
from crisai.orchestration.semantic_catalog import (
    LexiconTerms,
    SessionMemoryTerms,
    load_semantic_catalog,
)
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
SESSION_CONTEXT_SCHEMA_VERSION = "ui_session_context_v1"
DEFAULT_RECALL_LIMIT = 5
MAX_RECALL_LIMIT = 20
BASELINE_BRIEF_MAX_CHARS = 4000
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


@dataclass(frozen=True, slots=True)
class SessionRecallResult:
    """One deterministic session-memory recall hit."""

    field: str
    content: str
    score: float
    provenance: str
    matched_terms: list[str]


@dataclass(frozen=True, slots=True)
class SessionContextPackage:
    """API/MCP package for baseline session context and optional recall."""

    schema_version: str
    session: str
    baseline_brief: str
    memory: SessionMemory
    budget: dict[str, int | bool]
    recall_query: str
    recall_results: list[SessionRecallResult]


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
        clean
        for role, content in history
        if role == "assistant" and content.strip()
        if (clean := _clean_for_memory(sanitize_user_visible_text(content)))
    ]
    sources = _extract_sources(history)
    artefacts = [source for source in sources if "/artefacts/" in source or source.startswith("tasks/")]
    task_goal = _truncate(_durable_task_goal(user_messages), 500)
    last_outputs = [_truncate(item, 500) for item in assistant_messages[-2:]]
    current_state = _truncate(last_outputs[-1] if last_outputs else task_goal, 800)
    memory_terms = _session_memory_terms()
    decisions = _extract_decisions(assistant_messages, memory_terms)
    rejected_options = _extract_marked_items(assistant_messages, memory_terms.rejected_option_markers)
    assumptions = _extract_marked_items([*user_messages, *assistant_messages], memory_terms.assumption_markers)
    constraints = _extract_marked_items([*user_messages, *assistant_messages], memory_terms.constraint_markers)
    source_findings = _extract_marked_items(assistant_messages, memory_terms.source_finding_markers)
    next_actions = _extract_marked_items(assistant_messages[-3:], memory_terms.next_action_markers)
    open_questions = _extract_open_questions(user_messages, memory_terms)
    do_not_repeat = [
        "Do not repeat old source tables or previous final answers unless the user explicitly asks.",
        "Prefer compact source references over copied historical prose.",
    ]
    memory = SessionMemory(
        task_goal=_truncate(task_goal, max_memory_chars // 3),
        current_state=_truncate(current_state, max_memory_chars // 3),
        scope=_extract_scope(user_messages),
        assumptions=assumptions[:5],
        constraints=constraints[:6],
        important_decisions=decisions[:8],
        rejected_options=rejected_options[:5],
        source_findings=source_findings[:8],
        known_sources=sources[:12],
        active_artefacts=artefacts[:8],
        open_questions=open_questions[:5],
        next_actions=next_actions[:5],
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
    cfg = config or load_session_memory_config()
    memory = load_session_memory(session_name) if session_name else SessionMemory()
    anchors = load_session_anchors(session_name) if session_name else None
    resolved_anchors = resolve_anchor_references(user_input, anchors, registry_dir=load_settings().registry_dir) if anchors else ()
    if history and not any((memory.task_goal, memory.current_state, memory.known_sources, memory.last_outputs)):
        memory = compact_session_memory(history, max_memory_chars=cfg.max_memory_chars)
    recent = _relevant_recent_entries(user_input, history, max_entries=cfg.max_recent_turns * 2)
    baseline_brief = build_session_baseline_brief(session_name, memory) if session_name else render_session_memory(memory)
    transcript = render_history(recent)
    truncated = False
    if len(transcript) + len(baseline_brief) > cfg.max_runtime_chars:
        budget = max(0, cfg.max_runtime_chars - len(baseline_brief) - 500)
        transcript = _truncate(transcript, budget)
        truncated = True
    runtime_context = "\n\n".join(
        part
        for part in [
            baseline_brief,
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
        ("Scope", memory.scope),
        ("Assumptions", memory.assumptions),
        ("Constraints", memory.constraints),
        ("Important decisions", memory.important_decisions),
        ("Rejected options", memory.rejected_options),
        ("Source findings", memory.source_findings),
        ("Known sources", memory.known_sources),
        ("Active artefacts", memory.active_artefacts),
        ("Open questions", memory.open_questions),
        ("Next actions", memory.next_actions),
        ("Recent outputs", memory.last_outputs),
        ("Do not repeat", memory.do_not_repeat),
    ):
        if values:
            sections.append(label + ":\n" + "\n".join(f"- {item}" for item in values))
    return "\n\n".join(sections)


def build_session_baseline_brief(session_name: str, memory: SessionMemory | None = None) -> str:
    """Return the deterministic baseline task brief injected for a session."""
    safe_session = session_name or "default"
    memory = memory or load_session_memory(safe_session)
    task_root = sanitize_session_name(safe_session)
    parts = [
        "Active task context:",
        f"- Session: {safe_session}",
        f"- Task root: workspace/tasks/{task_root}",
        f"- Inputs: workspace/tasks/{task_root}/inputs",
        f"- Artefacts: workspace/tasks/{task_root}/artefacts",
    ]
    rendered = render_session_memory(memory)
    if rendered:
        parts.extend(["", "Structured session memory:", rendered])
    return _truncate("\n".join(parts), BASELINE_BRIEF_MAX_CHARS)


def recall_session_memory(
    session_name: str,
    query: str,
    *,
    limit: int = DEFAULT_RECALL_LIMIT,
    memory: SessionMemory | None = None,
    history: list[HistoryEntry] | None = None,
    registry_dir: Path | None = None,
) -> list[SessionRecallResult]:
    """Return deterministic relevant recall hits for one active session."""
    query = normalise_legacy_workspace_paths(query or "")
    if not query.strip():
        return []
    memory = memory or load_session_memory(session_name)
    history = history if history is not None else load_history_for_recall(session_name)
    max_items = max(1, min(int(limit), MAX_RECALL_LIMIT))
    query_terms = _expanded_content_terms(query, registry_dir=registry_dir)
    if not query_terms:
        return []
    candidates = _memory_recall_candidates(memory)
    candidates.extend(_recent_recall_candidates(history))
    results: list[SessionRecallResult] = []
    for field, content, provenance in candidates:
        content_terms = _content_terms(content)
        matched = sorted(query_terms & content_terms)
        if not matched:
            continue
        score = round((len(matched) * 2.0) + min(len(content_terms), 40) / 40.0, 3)
        results.append(
            SessionRecallResult(
                field=field,
                content=content,
                score=score,
                provenance=provenance,
                matched_terms=matched[:12],
            )
        )
    results.sort(key=lambda item: (-item.score, item.field, item.content))
    return results[:max_items]


def load_history_for_recall(session_name: str) -> list[HistoryEntry]:
    """Load history lazily to keep recall test seams simple."""
    from crisai.cli.session_store import load_history

    return load_history(session_name)


def build_session_context_package(
    session_name: str,
    *,
    query: str = "",
    limit: int = DEFAULT_RECALL_LIMIT,
    registry_dir: Path | None = None,
) -> SessionContextPackage:
    """Build the API/MCP session context package for a session."""
    memory = load_session_memory(session_name)
    baseline = build_session_baseline_brief(session_name, memory)
    recalls = recall_session_memory(
        session_name,
        query,
        limit=limit,
        memory=memory,
        registry_dir=registry_dir,
    )
    return SessionContextPackage(
        schema_version=SESSION_CONTEXT_SCHEMA_VERSION,
        session=session_name,
        baseline_brief=baseline,
        memory=memory,
        budget={
            "baseline_chars": len(baseline),
            "baseline_char_limit": BASELINE_BRIEF_MAX_CHARS,
            "recall_limit": max(1, min(int(limit), MAX_RECALL_LIMIT)),
            "recall_count": len(recalls),
            "truncated": len(baseline) >= BASELINE_BRIEF_MAX_CHARS,
        },
        recall_query=query or "",
        recall_results=recalls,
    )


def serialize_session_context(package: SessionContextPackage) -> dict[str, Any]:
    """Return a JSON-serializable session context payload."""
    return {
        "schema_version": package.schema_version,
        "session": package.session,
        "baseline_brief": package.baseline_brief,
        "memory": asdict(package.memory),
        "budget": package.budget,
        "recall_query": package.recall_query,
        "recall_results": [asdict(result) for result in package.recall_results],
    }


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
    if _is_runtime_failure_note(clean):
        return ""
    clean = _NOISE_SECTION_RE.sub("", clean)
    return re.sub(r"\n{3,}", "\n\n", clean).strip()


def _is_runtime_failure_note(text: str) -> bool:
    """Return whether text is an infrastructure failure note, not task content."""
    lower = (text or "").strip().lower()
    return lower.startswith("request failed:") and any(
        marker in lower
        for marker in (
            "runtimeerror:",
            "workflowvalidationerror:",
            "filenotfounderror:",
            "valueerror:",
        )
    )


def _semantic_catalog():
    try:
        return load_semantic_catalog()
    except Exception:  # noqa: BLE001 - session memory must degrade safely.
        return None


def _session_memory_terms() -> SessionMemoryTerms:
    catalog = _semantic_catalog()
    return catalog.session_memory if catalog is not None else SessionMemoryTerms()


def _lexicon_terms() -> LexiconTerms:
    catalog = _semantic_catalog()
    return catalog.lexicon if catalog is not None else LexiconTerms(function_words={}, prompt_noise_terms=frozenset(), title_relation_terms=frozenset())


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


def _extract_decisions(messages: list[str], terms: SessionMemoryTerms) -> list[str]:
    decisions: list[str] = []
    for message in messages[-6:]:
        for sentence in re.split(r"(?<=[.!?])\s+", message):
            stripped = sentence.strip(" -*\n")
            if 30 <= len(stripped) <= 260 and _contains_marker(stripped, terms.decision_markers):
                decisions.append(stripped)
                break
    return list(dict.fromkeys(decisions))


def _extract_marked_items(messages: list[str], markers: frozenset[str]) -> list[str]:
    items: list[str] = []
    for message in messages[-8:]:
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", message):
            stripped = sentence.strip(" -*\n")
            if 10 <= len(stripped) <= 260 and _contains_marker(stripped, markers):
                items.append(_truncate(stripped, 260))
                break
    return list(dict.fromkeys(items))


def _contains_marker(text: str, markers: frozenset[str]) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def _starts_with_marker(text: str, markers: frozenset[str]) -> bool:
    lowered = text.lower().lstrip()
    return any(lowered.startswith(f"{marker} ") for marker in markers)


def _extract_open_questions(user_messages: list[str], terms: SessionMemoryTerms) -> list[str]:
    questions: list[str] = []
    for message in user_messages[-4:]:
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", message):
            stripped = sentence.strip(" -*\n")
            if stripped and ("?" in stripped or _starts_with_marker(stripped, terms.open_question_starters)):
                questions.append(_truncate(stripped, 240))
    return list(dict.fromkeys(questions))


def _extract_scope(user_messages: list[str]) -> list[str]:
    if not user_messages:
        return []
    latest = user_messages[-1]
    scope_items = []
    for sentence in re.split(r"(?<=[.!?])\s+", latest):
        stripped = sentence.strip(" -*\n")
        if 15 <= len(stripped) <= 220:
            scope_items.append(_truncate(stripped, 220))
    return scope_items[:3]


def _durable_task_goal(user_messages: list[str]) -> str:
    """Return the earliest substantial user goal, preserving it across follow-ups."""
    for message in user_messages:
        if len(_content_terms(message)) >= 4:
            return message
    return user_messages[0] if user_messages else ""


def _memory_recall_candidates(memory: SessionMemory) -> list[tuple[str, str, str]]:
    candidates: list[tuple[str, str, str]] = []
    for field, value in asdict(memory).items():
        if field in {"schema_version", "updated_at"}:
            continue
        if isinstance(value, str) and value.strip():
            candidates.append((field, value.strip(), f"memory.{field}"))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                text = str(item).strip()
                if text:
                    candidates.append((field, text, f"memory.{field}[{index}]"))
    return candidates


def _recent_recall_candidates(history: list[HistoryEntry]) -> list[tuple[str, str, str]]:
    candidates: list[tuple[str, str, str]] = []
    for index, (role, content) in enumerate(history[-12:]):
        clean = _truncate(_clean_for_memory(content), 500)
        if clean:
            candidates.append((f"recent_{role}", clean, f"history[-12+{index}].{role}"))
    return candidates


def _expanded_content_terms(text: str, *, registry_dir: Path | None = None) -> set[str]:
    terms = set(_content_terms(text))
    if registry_dir is None:
        return terms
    try:
        context, _loaded = deterministic_context_from_registry(text, registry_dir)
    except Exception:  # noqa: BLE001 - recall must stay deterministic and fail-soft.
        return terms
    terms.update(term for term in context.suggested_terms if term and len(term) >= 4)
    return terms


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
        if _clean_for_memory(content) and query_terms & _content_terms(content)
    ]
    fallback = [
        (role, _truncate(clean, 1200))
        for role, content in recent[-2:]
        if (clean := _clean_for_memory(content))
    ]
    return relevant or fallback


def _content_terms(text: str) -> set[str]:
    lexicon = _lexicon_terms()
    stop = lexicon.all_function_words | lexicon.prompt_noise_terms
    return {token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", (text or "").lower()) if token not in stop}


def _limit_memory(memory: SessionMemory, max_chars: int) -> SessionMemory:
    rendered = render_session_memory(memory)
    if len(rendered) <= max_chars:
        return memory
    return SessionMemory(
        task_goal=_truncate(memory.task_goal, 500),
        current_state=_truncate(memory.current_state, 700),
        scope=memory.scope[:3],
        assumptions=memory.assumptions[:3],
        constraints=memory.constraints[:4],
        important_decisions=memory.important_decisions[:4],
        rejected_options=memory.rejected_options[:3],
        source_findings=memory.source_findings[:4],
        known_sources=memory.known_sources[:8],
        active_artefacts=memory.active_artefacts[:4],
        open_questions=memory.open_questions[:3],
        next_actions=memory.next_actions[:3],
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
