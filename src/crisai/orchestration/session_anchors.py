"""Deterministic extraction and resolution of user-visible session anchors."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .semantic_catalog import SemanticCatalog, load_semantic_catalog


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
    catalog: SemanticCatalog,
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
    catalog: SemanticCatalog,
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
    catalog: SemanticCatalog,
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


def _table_kind_and_title_index(headers: list[str], catalog: SemanticCatalog) -> tuple[str, int | None]:
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


def _contains_preferred_marker(text: str, catalog: SemanticCatalog) -> bool:
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


def _load_catalog(registry_dir: Path | None) -> SemanticCatalog:
    return load_semantic_catalog(str(registry_dir) if registry_dir is not None else None)
