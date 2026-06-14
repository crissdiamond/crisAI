"""Deterministic extraction and resolution of user-visible session anchors."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from crisai.orchestration import semantic_catalog as catalog_module


@dataclass(frozen=True, slots=True)
class SessionAnchor:
    """Stable reference to a user-visible item created earlier in a task."""

    kind: str
    label: str
    title: str
    order: str = ""
    summary: str = ""
    status: str = ""
    source_path: str = ""
    source_turn: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable anchor."""
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SessionAnchor:
        """Build an anchor from persisted JSON."""
        return cls(
            kind=str(payload.get("kind") or "").strip(),
            label=str(payload.get("label") or "").strip(),
            title=str(payload.get("title") or "").strip(),
            order=str(payload.get("order") or "").strip(),
            summary=str(payload.get("summary") or "").strip(),
            status=str(payload.get("status") or "").strip(),
            source_path=str(payload.get("source_path") or "").strip(),
            source_turn=_optional_int(payload.get("source_turn")),
        )


@dataclass(frozen=True, slots=True)
class AnchorReference:
    """Resolved reference from the latest user request to a stored anchor."""

    matched_text: str
    anchor: SessionAnchor

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable resolved reference."""
        return {
            "matched_text": self.matched_text,
            "anchor": self.anchor.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AnchorReference:
        """Build a resolved reference from persisted/request-contract JSON."""
        anchor_payload = payload.get("anchor")
        anchor = SessionAnchor.from_dict(anchor_payload if isinstance(anchor_payload, dict) else {})
        return cls(matched_text=str(payload.get("matched_text") or "").strip(), anchor=anchor)


@dataclass(frozen=True, slots=True)
class AnchorRegistry:
    """Collection of anchors known for a task session."""

    schema_version: str = "session_anchors_v1"
    anchors: tuple[SessionAnchor, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable registry."""
        return {
            "schema_version": self.schema_version,
            "anchors": [anchor.to_dict() for anchor in self.anchors],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AnchorRegistry:
        """Build a registry from persisted JSON."""
        raw = payload.get("anchors")
        anchors = tuple(
            SessionAnchor.from_dict(item)
            for item in raw
            if isinstance(item, dict)
        ) if isinstance(raw, list) else ()
        return cls(
            schema_version=str(payload.get("schema_version") or "session_anchors_v1"),
            anchors=anchors,
        )


@dataclass(frozen=True, slots=True)
class SessionSourceCandidate:
    """Safe source identity surfaced in an earlier turn."""

    title: str
    source_family: str = ""
    source_type: str = ""
    source_scope: str = ""
    open_url: str = ""
    content_id: str = ""
    workspace_path: str = ""
    location: str = ""
    evidence_level: str = ""
    read_status: str = ""
    rank: int | None = None
    source_turn: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SessionSourceCandidate:
        """Build a candidate from persisted JSON."""
        return cls(
            title=str(payload.get("title") or "").strip(),
            source_family=str(payload.get("source_family") or "").strip(),
            source_type=str(payload.get("source_type") or "").strip(),
            source_scope=str(payload.get("source_scope") or "").strip(),
            open_url=str(payload.get("open_url") or "").strip(),
            content_id=str(payload.get("content_id") or "").strip(),
            workspace_path=str(payload.get("workspace_path") or "").strip(),
            location=str(payload.get("location") or "").strip(),
            evidence_level=str(payload.get("evidence_level") or "").strip(),
            read_status=str(payload.get("read_status") or "").strip(),
            rank=_optional_int(payload.get("rank")),
            source_turn=_optional_int(payload.get("source_turn")),
            metadata={
                str(key): str(value)
                for key, value in (payload.get("metadata") or {}).items()
                if str(key).strip() and str(value).strip()
            }
            if isinstance(payload.get("metadata"), dict)
            else {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return asdict(self)

    @property
    def identity(self) -> str:
        """Return the strongest stable non-secret source identity available."""
        for value in (
            self.content_id,
            _sourcedoc_identity(self.open_url),
            self.open_url,
            self.workspace_path,
            self.title,
        ):
            cleaned = (value or "").strip().lower()
            if cleaned:
                return cleaned
        return ""

    @property
    def logical_key(self) -> str:
        """Return the identity of the underlying document for de-duplication.

        The same document re-discovered in a later turn can carry a different
        provider GUID (a different URL form or list context), so ``identity``
        alone does not collapse re-discovered copies. The logical key groups by
        normalised title plus source family and scope so one document maps to one
        anchor (CRISAI-ADR-015), preventing duplicate copies of one file from
        crowding out other distinct sources during resolution.
        """
        title = _normalise_match_text(self.title)
        if not title:
            return self.identity
        return "|".join((title, self.source_family.lower().strip(), self.source_scope.lower().strip()))

    @property
    def strong_identity(self) -> str:
        """Return the stable provider id (content_id or sourcedoc GUID) only.

        Unlike ``identity``, this does not fall back to the open URL, workspace
        path, or title — it is empty when no provider id is known. Two candidates
        with the same strong identity are the same physical document even if their
        display titles differ (CRISAI-ADR-015).
        """
        for value in (self.content_id, _sourcedoc_identity(self.open_url)):
            cleaned = (value or "").strip().lower()
            if cleaned:
                return cleaned
        return ""


@dataclass(frozen=True, slots=True)
class ResolvedSourceReference:
    """A persisted source candidate matched to the latest user request."""

    matched_text: str
    score: float
    source: SessionSourceCandidate

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ResolvedSourceReference:
        """Build a resolved source reference from request-contract JSON."""
        source_payload = payload.get("source")
        return cls(
            matched_text=str(payload.get("matched_text") or "").strip(),
            score=float(payload.get("score") or 0.0),
            source=SessionSourceCandidate.from_dict(source_payload if isinstance(source_payload, dict) else {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "matched_text": self.matched_text,
            "score": self.score,
            "source": self.source.to_dict(),
        }


def extract_session_anchors_from_history(
    history: list[tuple[str, str]],
    *,
    registry_dir: Path | None = None,
) -> AnchorRegistry:
    """Extract stable anchors from assistant outputs in a session transcript."""
    catalog = _load_catalog(registry_dir)
    anchors: list[SessionAnchor] = []
    for turn_index, (role, content) in enumerate(history):
        if role != "assistant" or not content.strip():
            continue
        anchors.extend(_extract_table_anchors(content, catalog=catalog, source_turn=turn_index))
        anchors.extend(_extract_heading_anchors(content, catalog=catalog, source_turn=turn_index))
    return AnchorRegistry(anchors=tuple(_dedupe_anchors(anchors)))


def resolve_anchor_references(
    message: str,
    registry: AnchorRegistry,
    *,
    registry_dir: Path | None = None,
) -> tuple[AnchorReference, ...]:
    """Resolve references in ``message`` against stored session anchors."""
    if not message.strip() or not registry.anchors:
        return ()
    catalog = _load_catalog(registry_dir)
    text = _clean_text(message).lower()
    resolved: list[AnchorReference] = []
    resolved_keys: set[tuple[str, str, str]] = set()

    for kind, terms in catalog.session_anchors.kinds.items():
        kind_terms = sorted((term for term in terms if term), key=len, reverse=True)
        if not kind_terms:
            continue
        term_pattern = "|".join(re.escape(term) for term in kind_terms)
        for match in re.finditer(rf"\b(?P<kind>{term_pattern})s?\s+(?P<refs>[0-9][0-9,\sand]*)", text):
            refs = re.findall(r"\d+", match.group("refs"))
            for ref in refs:
                anchor = _find_anchor_by_kind_and_order(registry.anchors, kind, ref)
                if anchor is None:
                    continue
                _append_reference(resolved, resolved_keys, match.group(0).strip(), anchor)

        if any(term in text for term in kind_terms) and _contains_preferred_marker(text, catalog):
            candidates = []
            for anchor in registry.anchors:
                if anchor.kind != kind:
                    continue
                status_text = f"{anchor.status} {anchor.summary} {anchor.title}".lower()
                if _contains_preferred_marker(status_text, catalog):
                    candidates.append(anchor)
            if len(candidates) == 1:
                _append_reference(resolved, resolved_keys, f"preferred {kind}", candidates[0])

    for anchor in registry.anchors:
        title = _clean_text(anchor.title).lower()
        if len(title) >= 6 and title in text:
            _append_reference(resolved, resolved_keys, anchor.title, anchor)

    return tuple(resolved)


def resolve_session_sources(
    message: str,
    candidates: tuple[SessionSourceCandidate, ...],
    *,
    registry_dir: Path | None = None,
    limit: int = 3,
) -> tuple[ResolvedSourceReference, ...]:
    """Resolve latest-turn source references against persisted source candidates."""
    if not (message or "").strip() or not candidates:
        return ()
    query_terms = _content_terms(message, registry_dir=registry_dir)
    if not query_terms:
        return ()
    scored: list[ResolvedSourceReference] = []
    normalized_message = _normalise_match_text(message)
    for candidate in candidates:
        title_terms = _content_terms(candidate.title, registry_dir=registry_dir)
        if not title_terms:
            continue
        overlap = query_terms & title_terms
        if not overlap:
            continue
        score = float(len(overlap) * 2)
        normalized_title = _normalise_match_text(candidate.title)
        if normalized_title and normalized_title in normalized_message:
            score += 8.0
        if len(overlap) >= 2:
            score += 2.0
        if candidate.open_url or candidate.workspace_path or candidate.content_id:
            score += 0.25
        if score < 4.0:
            continue
        scored.append(
            ResolvedSourceReference(
                matched_text=", ".join(sorted(overlap)),
                score=round(score, 3),
                source=candidate,
            )
        )
    scored.sort(key=lambda item: (-item.score, item.source.rank or 10_000, item.source.title.lower()))
    return tuple(_dedupe_resolved_sources(scored)[: max(1, limit)])


def render_resolved_sources(references: tuple[ResolvedSourceReference, ...], *, max_items: int = 5) -> str:
    """Render resolved sources for runtime prompt handoff."""
    if not references:
        return "None."
    lines: list[str] = []
    for reference in references[:max_items]:
        source = reference.source
        bits = [
            f"title: {source.title}",
            f"matched: {reference.matched_text}",
            f"source_family: {source.source_family}",
            f"source_type: {source.source_type}",
        ]
        if source.source_scope:
            bits.append(f"source_scope: {source.source_scope}")
        if source.location:
            bits.append(f"location: {source.location}")
        if source.open_url:
            bits.append(f"open_url: {source.open_url}")
        if source.workspace_path:
            bits.append(f"workspace_path: {source.workspace_path}")
        lines.append("- " + " | ".join(bit for bit in bits if bit and not bit.endswith(": ")))
    return "\n".join(lines)


def render_anchor_registry(registry: AnchorRegistry, *, max_items: int = 20) -> str:
    """Render anchors as compact runtime context."""
    if not registry.anchors:
        return ""
    lines = []
    for anchor in registry.anchors[:max_items]:
        bits = [anchor.label or anchor.kind, anchor.title]
        if anchor.status:
            bits.append(f"status: {anchor.status}")
        if anchor.source_path:
            bits.append(f"source: {anchor.source_path}")
        lines.append("- " + " | ".join(bit for bit in bits if bit))
    return "\n".join(lines)


def render_resolved_anchor_references(references: tuple[AnchorReference, ...]) -> str:
    """Render resolved references for agent runtime prompts."""
    if not references:
        return ""
    lines = []
    for ref in references:
        anchor = ref.anchor
        bits = [
            f"matched: {ref.matched_text}",
            f"label: {anchor.label}",
            f"title: {anchor.title}",
            f"kind: {anchor.kind}",
        ]
        if anchor.summary:
            bits.append(f"summary: {anchor.summary}")
        if anchor.status:
            bits.append(f"status: {anchor.status}")
        if anchor.source_path:
            bits.append(f"source: {anchor.source_path}")
        lines.append("- " + " | ".join(bit for bit in bits if bit))
    return "\n".join(lines)


def _extract_table_anchors(
    markdown: str,
    *,
    catalog: catalog_module.SemanticCatalog,
    source_turn: int,
) -> list[SessionAnchor]:
    anchors: list[SessionAnchor] = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines) - 1:
        if not (_looks_like_table_row(lines[i]) and _looks_like_separator(lines[i + 1])):
            i += 1
            continue
        headers = [_normalise_cell(cell) for cell in _split_table_row(lines[i])]
        rows: list[list[str]] = []
        i += 2
        while i < len(lines) and _looks_like_table_row(lines[i]):
            rows.append([_normalise_cell(cell) for cell in _split_table_row(lines[i])])
            i += 1
        anchors.extend(_anchors_from_table(headers, rows, catalog=catalog, source_turn=source_turn))
    return anchors


def _anchors_from_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    catalog: catalog_module.SemanticCatalog,
    source_turn: int,
) -> list[SessionAnchor]:
    anchors: list[SessionAnchor] = []
    header_map = {header.lower(): idx for idx, header in enumerate(headers)}
    kind, title_idx = _table_kind_and_title_index(headers, catalog)
    if not kind or title_idx is None:
        return []
    order_idx = _first_matching_header(header_map, catalog.session_anchors.order_columns)
    summary_idx = _first_matching_header(header_map, catalog.session_anchors.summary_columns)
    status_idx = _first_matching_header(header_map, catalog.session_anchors.status_columns)
    for row_position, row in enumerate(rows, start=1):
        title = _cell_at(row, title_idx)
        if not title:
            continue
        order = _cell_at(row, order_idx) if order_idx is not None else ""
        if not order:
            order = _leading_number(title) or str(row_position)
        label = f"{kind.title()} {order}" if order else kind.title()
        anchors.append(
            SessionAnchor(
                kind=kind,
                label=label,
                title=_strip_leading_number(title),
                order=order,
                summary=_cell_at(row, summary_idx) if summary_idx is not None else "",
                status=_cell_at(row, status_idx) if status_idx is not None else "",
                source_turn=source_turn,
            )
        )
    return anchors


def _extract_heading_anchors(
    markdown: str,
    *,
    catalog: catalog_module.SemanticCatalog,
    source_turn: int,
) -> list[SessionAnchor]:
    anchors: list[SessionAnchor] = []
    kind_terms = {
        term: kind
        for kind, terms in catalog.session_anchors.kinds.items()
        for term in terms
    }
    if not kind_terms:
        return anchors
    pattern = "|".join(re.escape(term) for term in sorted(kind_terms, key=len, reverse=True))
    heading_re = re.compile(
        rf"^#+\s+(?:(?P<kind>{pattern})\s*)?(?P<num>\d+)?[.) :-]*(?P<title>.+)$",
        re.IGNORECASE,
    )
    for line in markdown.splitlines():
        match = heading_re.match(line.strip())
        if not match:
            continue
        raw_kind = (match.group("kind") or "").lower()
        kind = kind_terms.get(raw_kind)
        title = _normalise_cell(match.group("title") or "")
        number = (match.group("num") or _leading_number(title) or "").strip()
        if not kind or not number or not title:
            continue
        anchors.append(
            SessionAnchor(
                kind=kind,
                label=f"{kind.title()} {number}",
                title=_strip_leading_number(title),
                order=number,
                source_turn=source_turn,
            )
        )
    return anchors


def _table_kind_and_title_index(headers: list[str], catalog: catalog_module.SemanticCatalog) -> tuple[str, int | None]:
    lowered = [header.lower() for header in headers]
    for kind, terms in catalog.session_anchors.kinds.items():
        for idx, header in enumerate(lowered):
            if header in terms:
                return kind, idx
    title_idx = _first_matching_header({h: i for i, h in enumerate(lowered)}, catalog.session_anchors.title_columns)
    return ("", title_idx)


def _first_matching_header(header_map: dict[str, int], candidates: frozenset[str]) -> int | None:
    for candidate in candidates:
        if candidate in header_map:
            return header_map[candidate]
    return None


def _find_anchor_by_kind_and_order(anchors: tuple[SessionAnchor, ...], kind: str, order: str) -> SessionAnchor | None:
    for anchor in anchors:
        if anchor.kind == kind and anchor.order == order:
            return anchor
    return None


def _contains_preferred_marker(text: str, catalog: catalog_module.SemanticCatalog) -> bool:
    return any(marker in text for marker in catalog.session_anchors.preferred_markers)


def _append_reference(
    resolved: list[AnchorReference],
    keys: set[tuple[str, str, str]],
    matched_text: str,
    anchor: SessionAnchor,
) -> None:
    key = (anchor.kind, anchor.order, anchor.title.lower())
    if key in keys:
        return
    keys.add(key)
    resolved.append(AnchorReference(matched_text=matched_text, anchor=anchor))


def _dedupe_resolved_sources(references: list[ResolvedSourceReference]) -> list[ResolvedSourceReference]:
    seen: set[str] = set()
    deduped: list[ResolvedSourceReference] = []
    for reference in references:
        key = reference.source.logical_key or reference.source.identity
        if key in seen:
            continue
        seen.add(key)
        deduped.append(reference)
    return deduped


# Evidence strength ordering for choosing which re-discovered copy of a document
# to keep when merging duplicates (CRISAI-ADR-003 levels; read_failed is weakest).
_EVIDENCE_STRENGTH = {
    "content_read": 3,
    "metadata_read": 2,
    "search_hit_only": 1,
    "read_failed": 0,
    "": 0,
}


def _candidate_strength(candidate: SessionSourceCandidate) -> tuple[int, int, int]:
    """Rank a candidate so the strongest copy of a document wins a merge."""
    return (
        _EVIDENCE_STRENGTH.get(candidate.evidence_level, 0),
        candidate.source_turn if candidate.source_turn is not None else -1,
        1 if (candidate.content_id or candidate.open_url or candidate.workspace_path) else 0,
    )


def dedupe_source_candidates_by_logical_document(
    candidates: list[SessionSourceCandidate],
) -> list[SessionSourceCandidate]:
    """Collapse re-discovered copies of one document into a single anchor.

    Two candidates are the same document when they share a stable provider id
    (``strong_identity`` — same physical file, possibly different display titles)
    OR a ``logical_key`` (same title/family/scope, re-discovered with a different
    GUID across turns). Each group keeps the strongest copy (highest evidence
    level, then most recent turn, then one carrying a durable handle), preserving
    first-seen order for stable rendering. One document maps to one anchor so
    duplicate copies cannot crowd out other distinct sources under the resolution
    limit (CRISAI-ADR-015).
    """
    groups: list[dict[str, Any]] = []

    def _find_group(candidate: SessionSourceCandidate) -> dict[str, Any] | None:
        sid = candidate.strong_identity
        lk = candidate.logical_key
        for group in groups:
            if sid and sid in group["identities"]:
                return group
            if lk and lk in group["logical_keys"]:
                return group
        return None

    for candidate in candidates:
        if not (candidate.strong_identity or candidate.logical_key):
            continue
        group = _find_group(candidate)
        if group is None:
            group = {"identities": set(), "logical_keys": set(), "best": candidate}
            groups.append(group)
        elif _candidate_strength(candidate) > _candidate_strength(group["best"]):
            group["best"] = candidate
        if candidate.strong_identity:
            group["identities"].add(candidate.strong_identity)
        if candidate.logical_key:
            group["logical_keys"].add(candidate.logical_key)
    return [group["best"] for group in groups]


def _sourcedoc_identity(open_url: str) -> str:
    """Return a provider item id from URL query parameters when present."""
    if not open_url:
        return ""
    try:
        query = parse_qs(urlparse(open_url).query)
    except ValueError:
        return ""
    for values in query.values():
        for value in values:
            cleaned = value.strip().strip("{}")
            if re.fullmatch(
                r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                cleaned,
            ):
                return cleaned
    return ""


def _dedupe_anchors(anchors: list[SessionAnchor]) -> list[SessionAnchor]:
    by_key: dict[tuple[str, str, str], SessionAnchor] = {}
    for anchor in anchors:
        key = (anchor.kind, anchor.order, anchor.title.lower())
        by_key[key] = anchor
    return list(by_key.values())


def _split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _looks_like_table_row(line: str) -> bool:
    return line.strip().startswith("|") and line.strip().endswith("|")


def _looks_like_separator(line: str) -> bool:
    stripped = line.strip().strip("|").strip()
    return bool(stripped) and all(ch in "-:| " for ch in stripped)


def _normalise_cell(value: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", value or "")
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_]+", "", text)
    return " ".join(text.split()).strip()


def _clean_text(value: str) -> str:
    return " ".join((value or "").split()).strip()


def _content_terms(text: str, *, registry_dir: Path | None = None) -> set[str]:
    try:
        catalog = _load_catalog(registry_dir)
        lexicon = catalog.lexicon
        stop = lexicon.all_function_words | lexicon.prompt_noise_terms | lexicon.title_relation_terms
    except Exception:  # noqa: BLE001 - source resolution must fail soft.
        stop = frozenset()
    terms = {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{1,}", (text or "").lower())
        if token not in stop
    }
    return {
        token
        for token in terms
        if len(token) >= 3 or re.fullmatch(r"v[0-9]+", token)
    }


def _normalise_match_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _cell_at(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return _normalise_cell(row[idx])


def _leading_number(value: str) -> str:
    match = re.match(r"\s*(\d+)\b", value or "")
    return match.group(1) if match else ""


def _strip_leading_number(value: str) -> str:
    return re.sub(r"^\s*\d+[.) :-]*", "", value or "").strip()


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_catalog(registry_dir: Path | None) -> catalog_module.SemanticCatalog:
    return catalog_module.load_semantic_catalog(str(registry_dir) if registry_dir is not None else None)
