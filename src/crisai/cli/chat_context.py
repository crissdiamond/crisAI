from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from crisai.cli import display as display_module
from crisai.cli import session_store as session_store_module
from crisai.cli import text_loader as text_loader_module
from crisai import config as config_module
from crisai.orchestration import retrieval_association_graph as graph_module
from crisai.orchestration import semantic_catalog as catalog_module
from crisai.orchestration import session_anchors as anchors_module
from crisai.workspace import spaces as spaces_module

sanitize_user_visible_text = display_module.sanitize_user_visible_text

HistoryEntry = session_store_module.HistoryEntry
SessionMemory = session_store_module.SessionMemory
load_session_anchors = session_store_module.load_session_anchors
load_session_memory = session_store_module.load_session_memory
sanitize_session_name = session_store_module.sanitize_session_name
save_session_anchors = session_store_module.save_session_anchors
save_session_memory = session_store_module.save_session_memory

render_cli_text = text_loader_module.render_cli_text
load_settings = config_module.load_settings

collect_graph_emits = graph_module.collect_graph_emits
deterministic_context_from_registry = graph_module.deterministic_context_from_registry
expand_retrieval_hints = graph_module.expand_retrieval_hints
load_retrieval_association_graph = graph_module.load_retrieval_association_graph

LexiconTerms = catalog_module.LexiconTerms
SessionMemoryTerms = catalog_module.SessionMemoryTerms
load_semantic_catalog = catalog_module.load_semantic_catalog

SessionSourceCandidate = anchors_module.SessionSourceCandidate
extract_session_anchors_from_history = anchors_module.extract_session_anchors_from_history
render_anchor_registry = anchors_module.render_anchor_registry
render_resolved_anchor_references = anchors_module.render_resolved_anchor_references
resolve_anchor_references = anchors_module.resolve_anchor_references

load_workspace_spaces = spaces_module.load_workspace_spaces

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
_MACHINE_SCHEMA_BLOCK_RE = re.compile(
    r"(?ims)^```(?:json)?\s*\{.*?schema_version.*?\}\s*```"
)
_FENCED_JSON_BLOCK_RE = re.compile(r"(?is)```(?:json)?\s*(.*?)\s*```")
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
    source_candidates = _extract_source_candidates(history)
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
        source_candidates=source_candidates[:20],
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
    existing = load_session_memory(session_name)
    memory = compact_session_memory(history, max_memory_chars=cfg.max_memory_chars)
    if existing.source_candidates:
        memory = _memory_with_source_candidates(
            memory,
            _dedupe_source_candidates([*memory.source_candidates, *existing.source_candidates]),
        )
    save_session_memory(session_name, memory)
    anchors = extract_session_anchors_from_history(history, registry_dir=load_settings().registry_dir)
    save_session_anchors(session_name, anchors)
    return memory


def persist_session_source_candidates_from_output(session_name: str, output: str) -> list[SessionSourceCandidate]:
    """Persist source candidates discovered in a single-turn source output."""
    if not session_name or not (output or "").strip():
        return []
    discovered = _extract_source_candidates([("assistant", output)])
    if not discovered:
        return []
    existing = load_session_memory(session_name)
    merged = _dedupe_source_candidates([*discovered, *existing.source_candidates])
    save_session_memory(session_name, _memory_with_source_candidates(existing, merged))
    return merged


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
    settings = load_settings()
    registry_dir = Path(settings.registry_dir)
    preserve_recent_tables = is_continuation_request(user_input, registry_dir=registry_dir)
    resolved_anchors = resolve_anchor_references(user_input, anchors, registry_dir=registry_dir) if anchors else ()
    if history and not any((memory.task_goal, memory.current_state, memory.known_sources, memory.last_outputs)):
        memory = compact_session_memory(history, max_memory_chars=cfg.max_memory_chars)
    recent = _relevant_recent_entries(
        user_input,
        history,
        max_entries=cfg.max_recent_turns * 2,
        preserve_tables=preserve_recent_tables,
    )
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
        ("Source candidates", _render_source_candidates(memory.source_candidates)),
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
    return session_store_module.load_history(session_name)


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


def is_continuation_request(user_input: str, *, registry_dir: Path | None = None) -> bool:
    """Return whether the user input is a configured bare continuation command."""
    text = normalise_legacy_workspace_paths(user_input or "").strip()
    if not text:
        return False
    catalog = _semantic_catalog(registry_dir)
    interaction = getattr(catalog, "interaction", None) if catalog is not None else None
    patterns = getattr(interaction, "continuation_patterns", ()) if interaction is not None else ()
    return any(pattern.search(text) for pattern in patterns)


def continuation_intent_message(
    user_input: str,
    history: list[HistoryEntry],
    *,
    registry_dir: Path | None = None,
) -> str:
    """Return an intent message that carries the immediately preceding exchange."""
    normalized = normalise_legacy_workspace_paths(user_input or "")
    if not history or not is_continuation_request(normalized, registry_dir=registry_dir):
        return normalized
    previous_user = _last_history_content(history, "user")
    previous_assistant = _last_history_content(history, "assistant")
    if not previous_user and not previous_assistant:
        return normalized
    template = _continuation_intent_template(registry_dir)
    if not template:
        return normalized
    parts = [template["preamble"]]
    if previous_user:
        parts.extend(["", template["previous_user_label"], previous_user])
    if previous_assistant:
        parts.extend(["", template["previous_assistant_label"], _clean_recent_turn(previous_assistant, preserve_tables=True)])
    parts.extend(["", template["current_user_label"], normalized])
    return "\n".join(part for part in parts if part is not None).strip()


def _continuation_intent_template(registry_dir: Path | None = None) -> dict[str, str]:
    required = ("preamble", "previous_user_label", "previous_assistant_label", "current_user_label")
    catalog = _semantic_catalog(registry_dir)
    lexicon = getattr(catalog, "lexicon", None) if catalog is not None else None
    template = getattr(lexicon, "continuation_intent_template", {}) if lexicon is not None else {}
    if not isinstance(template, dict):
        return {}
    clean = {key: str(template.get(key) or "").strip() for key in required}
    return clean if all(clean.values()) else {}


def _last_history_content(history: list[HistoryEntry], role: str) -> str:
    for entry_role, content in reversed(history):
        if entry_role == role and str(content).strip():
            return normalise_legacy_workspace_paths(str(content))
    return ""


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
    return _clean_recent_turn(text, preserve_tables=False)


def _memory_with_source_candidates(
    memory: SessionMemory,
    source_candidates: list[SessionSourceCandidate],
) -> SessionMemory:
    return SessionMemory(
        schema_version=memory.schema_version,
        task_goal=memory.task_goal,
        current_state=memory.current_state,
        scope=list(memory.scope),
        assumptions=list(memory.assumptions),
        constraints=list(memory.constraints),
        important_decisions=list(memory.important_decisions),
        rejected_options=list(memory.rejected_options),
        source_findings=list(memory.source_findings),
        known_sources=list(memory.known_sources),
        source_candidates=source_candidates,
        active_artefacts=list(memory.active_artefacts),
        open_questions=list(memory.open_questions),
        next_actions=list(memory.next_actions),
        last_outputs=list(memory.last_outputs),
        do_not_repeat=list(memory.do_not_repeat),
        updated_at=memory.updated_at,
    )


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


def _semantic_catalog(registry_dir: Path | None = None):
    try:
        if registry_dir is not None:
            return load_semantic_catalog(str(registry_dir))
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


def _extract_source_candidates(history: list[HistoryEntry]) -> list[SessionSourceCandidate]:
    candidates: list[SessionSourceCandidate] = []
    for turn_index, (role, content) in enumerate(history):
        if role != "assistant" or not content.strip():
            continue
        candidates.extend(_source_candidates_from_evidence_bundles(content, source_turn=turn_index))
        candidates.extend(_source_candidates_from_markdown_links(content, source_turn=turn_index))
    return _dedupe_source_candidates(candidates)


def _source_candidates_from_evidence_bundles(content: str, *, source_turn: int) -> list[SessionSourceCandidate]:
    candidates: list[SessionSourceCandidate] = []
    for match in _FENCED_JSON_BLOCK_RE.finditer(content or ""):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or payload.get("schema_version") != "evidence_bundle_v1":
            continue
        items = payload.get("items")
        if not isinstance(items, list):
            continue
        for rank, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            source = item.get("source")
            if not isinstance(source, dict):
                continue
            candidate = _candidate_from_source_payload(
                source,
                rank=rank,
                source_turn=source_turn,
                evidence_level=str(item.get("evidence_level") or ""),
                read_status=str(item.get("read_status") or ""),
            )
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def _candidate_from_source_payload(
    source: dict[str, Any],
    *,
    rank: int,
    source_turn: int,
    evidence_level: str = "",
    read_status: str = "",
) -> SessionSourceCandidate | None:
    title = str(source.get("title") or source.get("name") or "").strip()
    open_url = str(source.get("open_url") or source.get("webUrl") or "").strip()
    content_id = str(source.get("content_id") or "").strip()
    workspace_path = str(source.get("workspace_path") or "").strip()
    if not title and workspace_path:
        title = Path(workspace_path).name
    if not title:
        return None
    source_type = str(source.get("source_type") or "").strip()
    family = _source_family_from_reference(
        title=title,
        source_type=source_type,
        open_url=open_url,
        workspace_path=workspace_path,
        content_id=content_id,
    )
    scope = _source_scope(
        source_type=source_type,
        open_url=open_url,
        workspace_path=workspace_path,
        content_id=content_id,
    )
    metadata_payload = source.get("metadata")
    metadata = (
        {str(key): value for key, value in metadata_payload.items()}
        if isinstance(metadata_payload, dict)
        else {}
    )
    metadata = _safe_source_candidate_metadata(metadata)
    return SessionSourceCandidate(
        title=title,
        source_family=str(source.get("source_family") or "").strip() or family,
        source_type=source_type or _source_type_from_reference(open_url=open_url, workspace_path=workspace_path),
        source_scope=scope,
        open_url=open_url,
        content_id=content_id,
        workspace_path=workspace_path,
        location=str(source.get("location") or "").strip(),
        evidence_level=evidence_level,
        read_status=read_status,
        rank=rank,
        source_turn=source_turn,
        metadata=metadata,
    )


def _source_candidates_from_markdown_links(content: str, *, source_turn: int) -> list[SessionSourceCandidate]:
    candidates: list[SessionSourceCandidate] = []
    for rank, match in enumerate(_MARKDOWN_LINK_RE.finditer(content or ""), start=1):
        label = (match.group(1) or "").strip()
        href = (match.group(2) or "").strip()
        if not label or not href:
            continue
        workspace_path = _workspace_path_from_href(href)
        open_url = "" if workspace_path else href
        family = _source_family_from_reference(title=label, open_url=open_url, workspace_path=workspace_path)
        scope = _source_scope(open_url=open_url, workspace_path=workspace_path)
        source_type = _source_type_from_reference(open_url=open_url, workspace_path=workspace_path)
        if not scope and not workspace_path:
            continue
        location = _markdown_table_location(content, match.start())
        candidates.append(
            SessionSourceCandidate(
                title=label,
                source_family=family,
                source_type=source_type,
                source_scope=scope,
                open_url=open_url,
                workspace_path=workspace_path,
                location=location,
                evidence_level="metadata_read",
                read_status="metadata_read",
                rank=rank,
                source_turn=source_turn,
            )
        )
    return candidates


def _workspace_path_from_href(href: str) -> str:
    href_text = (href or "").strip()
    marker = "/workspace/"
    if marker in href_text:
        return _canonical_source_path(href_text.split(marker, 1)[1])
    if href_text.startswith("workspace/"):
        return _canonical_source_path(href_text)
    return ""


def _markdown_table_location(content: str, match_start: int) -> str:
    line_start = content.rfind("\n", 0, match_start) + 1
    line_end = content.find("\n", match_start)
    line = content[line_start:] if line_end == -1 else content[line_start:line_end]
    if "|" not in line:
        return ""
    raw_cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    clean_cells = [re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cell).strip() for cell in raw_cells]
    for index, cell in enumerate(raw_cells):
        if _MARKDOWN_LINK_RE.search(cell):
            return clean_cells[index + 1] if index + 1 < len(clean_cells) else ""
    return ""


def _source_scope(
    *,
    source_type: str = "",
    open_url: str = "",
    workspace_path: str = "",
    content_id: str = "",
) -> str:
    lowered_ref = f"{source_type} {open_url} {workspace_path} {content_id}".lower()
    catalog = _semantic_catalog()
    constraints = getattr(catalog, "retrieval_constraints", None) if catalog is not None else None
    markers_by_scope = getattr(constraints, "source_scope_markers", {}) if constraints is not None else {}
    for scope, markers in markers_by_scope.items():
        if any(marker and marker in lowered_ref for marker in markers):
            return str(scope)
    return ""


def _source_family_from_reference(
    *,
    title: str = "",
    source_type: str = "",
    open_url: str = "",
    workspace_path: str = "",
    content_id: str = "",
) -> str:
    registry_dir = getattr(load_settings(), "registry_dir", None)
    if registry_dir is None:
        return ""
    del title
    reference_text = " ".join(part for part in (source_type, open_url, workspace_path, content_id) if part)
    if not reference_text.strip():
        return ""
    try:
        root = Path(registry_dir)
        graph = load_retrieval_association_graph(root)
        seeds, _terms = expand_retrieval_hints(reference_text, graph)
        emits = collect_graph_emits(graph, seeds)
        sources = emits.get("suggested_sources")
        if isinstance(sources, list):
            direct_families = [str(source) for source in sources if str(source).strip()]
            if direct_families:
                return sorted(direct_families)[0]
        context, loaded = deterministic_context_from_registry(reference_text, root)
    except Exception:  # noqa: BLE001 - source continuity must fail soft.
        return ""
    if not loaded:
        return ""
    families = [source for source in sorted(context.suggested_sources) if source != "generic_retrieval"]
    return families[0] if families else ""


def _source_type_from_reference(*, open_url: str = "", workspace_path: str = "") -> str:
    reference_text = " ".join(part for part in (open_url, workspace_path) if part).lower()
    catalog = _semantic_catalog()
    constraints = getattr(catalog, "retrieval_constraints", None) if catalog is not None else None
    markers_by_type = getattr(constraints, "source_type_markers", {}) if constraints is not None else {}
    for source_type, markers in markers_by_type.items():
        if any(marker and marker in reference_text for marker in markers):
            return str(source_type)
    return ""


def _safe_source_candidate_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    catalog = _semantic_catalog()
    constraints = getattr(catalog, "retrieval_constraints", None) if catalog is not None else None
    denied = (
        cast(frozenset[str], getattr(constraints, "source_candidate_metadata_deny_keys", frozenset()))
        if constraints is not None
        else frozenset()
    )
    return {
        str(key): str(value)
        for key, value in metadata.items()
        if str(key).strip() and str(value).strip() and str(key).strip().lower() not in denied
    }


def _dedupe_source_candidates(candidates: list[SessionSourceCandidate]) -> list[SessionSourceCandidate]:
    by_identity: dict[str, SessionSourceCandidate] = {}
    for candidate in candidates:
        identity = candidate.identity.strip().lower()
        if identity not in by_identity:
            by_identity[identity] = candidate
    return list(by_identity.values())


def _render_source_candidates(candidates: list[SessionSourceCandidate]) -> list[str]:
    rendered: list[str] = []
    for candidate in candidates[:12]:
        parts = [candidate.title]
        if candidate.source_family:
            parts.append(candidate.source_family)
        if candidate.source_scope:
            parts.append(candidate.source_scope)
        if candidate.location:
            parts.append(candidate.location)
        rendered.append(" | ".join(parts))
    return rendered


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


def _relevant_recent_entries(
    user_input: str,
    history: list[HistoryEntry],
    *,
    max_entries: int,
    preserve_tables: bool = False,
) -> list[HistoryEntry]:
    if max_entries <= 0:
        return []
    query_terms = _content_terms(user_input)
    recent = history[-max_entries:]
    max_chars = 2000 if preserve_tables else 1200
    if not query_terms:
        return [(role, _truncate(_clean_recent_turn(content, preserve_tables=preserve_tables), max_chars)) for role, content in recent]
    relevant = [
        (role, _truncate(clean, max_chars))
        for role, content in recent
        if (clean := _clean_recent_turn(content, preserve_tables=preserve_tables))
        if query_terms & _content_terms(content)
    ]
    fallback = [
        (role, _truncate(clean, max_chars))
        for role, content in recent[-2:]
        if (clean := _clean_recent_turn(content, preserve_tables=preserve_tables))
    ]
    return relevant or fallback


def _clean_recent_turn(text: str, *, preserve_tables: bool) -> str:
    clean = sanitize_user_visible_text(text or "")
    if _is_runtime_failure_note(clean):
        return ""
    clean = _MACHINE_SCHEMA_BLOCK_RE.sub("", clean) if preserve_tables else _NOISE_SECTION_RE.sub("", clean)
    return re.sub(r"\n{3,}", "\n\n", clean).strip()


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
        source_candidates=memory.source_candidates[:12],
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
