"""Validated evidence handoff contracts for retrieval workflows."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

from .semantic_catalog import load_semantic_catalog
from .task_contract import infer_task_contract

ALLOWED_EVIDENCE_LEVELS = {
    "search_hit_only",
    "metadata_read",
    "content_read",
    "read_failed",
}
ALLOWED_EVIDENCE_ROLES = {
    "primary",
    "supplemental",
}
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Source identity passed between agents."""

    source_type: str
    title: str
    open_url: str = ""
    location: str = ""
    read_handle: str = ""
    workspace_path: str = ""
    content_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceReference:
        metadata = data.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError("source.metadata must be an object when provided.")
        open_url = str(data.get("open_url") or "").strip()
        workspace_path = str(data.get("workspace_path") or "").strip()
        return cls(
            source_type=_registry_source_type(
                str(data.get("source_type") or "").strip(),
                open_url=open_url,
                workspace_path=workspace_path,
            ),
            title=str(data.get("title") or "").strip(),
            open_url=open_url,
            location=str(data.get("location") or "").strip(),
            read_handle=str(data.get("read_handle") or "").strip(),
            workspace_path=workspace_path,
            content_id=str(data.get("content_id") or "").strip(),
            metadata=dict(metadata),
        )

    @classmethod
    def from_legacy_title(cls, title: str, *, read_tool: str = "") -> SourceReference:
        """Build a source reference from the pre-schema string source format."""
        return cls(
            source_type=_infer_source_type(read_tool),
            title=title.strip(),
            metadata={"normalised_from": "string_source"},
        )

    def validate(self) -> None:
        if not self.source_type:
            raise ValueError("source.source_type is required.")
        if not self.title:
            raise ValueError("source.title is required.")
        has_reference = any((self.open_url, self.read_handle, self.workspace_path, self.content_id))
        is_legacy_string_source = self.metadata.get("normalised_from") == "string_source"
        if not has_reference and not is_legacy_string_source:
            raise ValueError(
                "source must include at least one of open_url, read_handle, workspace_path, or content_id."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "title": self.title,
            "open_url": self.open_url,
            "location": self.location,
            "read_handle": self.read_handle,
            "workspace_path": self.workspace_path,
            "content_id": self.content_id,
            "metadata": dict(self.metadata),
        }

    def to_sanitized_dict(self) -> dict[str, Any]:
        """Return source identity safe for durable logs and UI snapshots."""
        payload = self.to_dict()
        payload.pop("read_handle", None)
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            payload["metadata"] = _without_sensitive_keys(metadata)
        return payload

    @property
    def stable_identity(self) -> str:
        """Return the strongest comparable non-secret identity for dedupe."""
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


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One source plus its current retrieval/read status."""

    source: SourceReference
    evidence_level: str
    read_status: str
    evidence_role: str = "primary"
    read_tool: str = ""
    content_excerpt: str = ""
    raw_error: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceItem:
        source_raw = data.get("source") or {}
        read_tool = str(data.get("read_tool") or "").strip()
        if isinstance(source_raw, str):
            source = SourceReference.from_legacy_title(source_raw, read_tool=read_tool)
        elif isinstance(source_raw, dict):
            source = SourceReference.from_dict(source_raw)
        else:
            raise ValueError("item.source must be an object.")
        evidence_level = _upgraded_evidence_level(
            str(data.get("evidence_level") or "").strip(),
            read_status=str(data.get("read_status") or "").strip(),
            read_tool=read_tool,
            content_excerpt=str(data.get("content_excerpt") or ""),
        )
        return cls(
            source=source,
            evidence_level=evidence_level,
            read_status=str(data.get("read_status") or "").strip(),
            evidence_role=_evidence_role(data, source),
            read_tool=read_tool,
            content_excerpt=str(data.get("content_excerpt") or ""),
            raw_error=str(data.get("raw_error") or ""),
        )

    def validate(self) -> None:
        self.source.validate()
        if self.evidence_level not in ALLOWED_EVIDENCE_LEVELS:
            allowed = ", ".join(sorted(ALLOWED_EVIDENCE_LEVELS))
            raise ValueError(f"item.evidence_level must be one of: {allowed}.")
        if not self.read_status:
            raise ValueError("item.read_status is required.")
        if self.evidence_role not in ALLOWED_EVIDENCE_ROLES:
            allowed = ", ".join(sorted(ALLOWED_EVIDENCE_ROLES))
            raise ValueError(f"item.evidence_role must be one of: {allowed}.")
        if self.evidence_level == "content_read":
            if not self.read_tool:
                raise ValueError("content_read items must include read_tool.")
            if not self.content_excerpt.strip():
                raise ValueError("content_read items must include content_excerpt.")
        if self.evidence_level == "read_failed" and not self.raw_error.strip():
            raise ValueError("read_failed items must include raw_error.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "evidence_level": self.evidence_level,
            "read_status": self.read_status,
            "evidence_role": self.evidence_role,
            "read_tool": self.read_tool,
            "content_excerpt": self.content_excerpt,
            "raw_error": self.raw_error,
        }

    def to_sanitized_dict(self) -> dict[str, Any]:
        """Return evidence item safe for durable logs and UI snapshots."""
        payload = self.to_dict()
        payload["source"] = self.source.to_sanitized_dict()
        return payload


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Canonical retrieval handoff from retrieval agents to downstream stages."""

    schema_version: str
    request: str
    items: list[EvidenceItem]
    gaps: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceBundle:
        raw_items = data.get("items") or []
        if not isinstance(raw_items, list):
            raise ValueError("items must be a list.")
        raw_gaps = data.get("gaps") or []
        if not isinstance(raw_gaps, list):
            raise ValueError("gaps must be a list.")
        bundle = cls(
            schema_version=str(data.get("schema_version") or "").strip(),
            request=str(data.get("request") or "").strip(),
            items=_dedupe_items([EvidenceItem.from_dict(item) for item in raw_items]),
            gaps=[str(gap) for gap in raw_gaps],
        )
        bundle.validate()
        return bundle

    def validate(self) -> None:
        if self.schema_version != "evidence_bundle_v1":
            raise ValueError("schema_version must be 'evidence_bundle_v1'.")
        if not self.request:
            raise ValueError("request is required.")
        for item in self.items:
            item.validate()

    def has_content_read(self) -> bool:
        return any(item.evidence_level == "content_read" for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request": self.request,
            "items": [item.to_dict() for item in self.items],
            "gaps": list(self.gaps),
        }

    def to_sanitized_dict(self) -> dict[str, Any]:
        """Return evidence bundle without transient read handles."""
        return {
            "schema_version": self.schema_version,
            "request": self.request,
            "items": [item.to_sanitized_dict() for item in self.items],
            "gaps": list(self.gaps),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def parse_evidence_bundle(text: str) -> EvidenceBundle:
    """Parse the first valid EvidenceBundle from fenced or bare JSON text."""
    errors: list[str] = []
    for match in _JSON_FENCE_RE.finditer(text or ""):
        raw = match.group(1)
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict) and payload.get("schema_version") == "evidence_bundle_v1":
                return EvidenceBundle.from_dict(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(str(exc))
    for raw in _iter_bare_json_objects_with_schema(text or "", "evidence_bundle_v1"):
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict) and payload.get("schema_version") == "evidence_bundle_v1":
                return EvidenceBundle.from_dict(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(str(exc))
    suffix = f" Last validation error: {errors[-1]}" if errors else ""
    raise ValueError(f"No valid evidence_bundle_v1 JSON block found.{suffix}")


def _iter_bare_json_objects_with_schema(text: str, schema_version: str) -> list[str]:
    """Return balanced JSON object strings containing ``schema_version``.

    Some models omit a closing Markdown fence even when the JSON itself is
    balanced. Parsing balanced objects keeps the evidence gate strict on schema
    while avoiding false failures caused by Markdown formatting drift.
    """
    marker_re = re.compile(
        rf'"schema_version"\s*:\s*"{re.escape(schema_version)}"',
        re.IGNORECASE,
    )
    objects: list[str] = []
    cursor = 0
    while True:
        marker = marker_re.search(text, cursor)
        if marker is None:
            break
        start = text.rfind("{", cursor, marker.start())
        if start == -1:
            cursor = marker.end()
            continue
        end = _find_json_object_end(text, start)
        if end is None:
            cursor = marker.end()
            continue
        objects.append(text[start:end])
        cursor = end
    return objects


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


def _infer_source_type(read_tool: str) -> str:
    tool = (read_tool or "").lower()
    if "sharepoint" in tool:
        return "sharepoint_document"
    if "workspace" in tool:
        return "workspace_document"
    if "intranet" in tool:
        return "intranet_page"
    return "legacy_text"


def _evidence_role(data: dict[str, Any], source: SourceReference) -> str:
    role = str(data.get("evidence_role") or source.metadata.get("evidence_role") or "primary")
    return role.strip().lower() or "primary"


def request_requires_content_read(message: str) -> bool:
    """Return True for requests where metadata-only evidence is insufficient."""
    contract = infer_task_contract(message)
    return contract.required_evidence_level == "content_read"


def render_evidence_bundle_block(bundle: EvidenceBundle) -> str:
    """Render a fenced JSON block for prompts and traces."""
    return "```json\n" + bundle.to_json() + "\n```"


def _upgraded_evidence_level(
    evidence_level: str,
    *,
    read_status: str,
    read_tool: str,
    content_excerpt: str,
) -> str:
    """Promote stale search-hit labels after a successful read."""
    if evidence_level != "search_hit_only":
        return evidence_level
    status = (read_status or "").strip().lower()
    if not status.startswith("read"):
        return evidence_level
    if (content_excerpt or "").strip() and (read_tool or "").strip():
        return "content_read"
    return "metadata_read"


def _dedupe_items(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Deduplicate evidence items by stable non-secret source identity."""
    by_identity: dict[str, EvidenceItem] = {}
    anonymous: list[EvidenceItem] = []
    for item in items:
        identity = item.source.stable_identity
        if not identity:
            anonymous.append(item)
            continue
        existing = by_identity.get(identity)
        if existing is None or _evidence_rank(item) > _evidence_rank(existing):
            by_identity[identity] = item
    return [*by_identity.values(), *anonymous]


def _evidence_rank(item: EvidenceItem) -> int:
    levels = {
        "read_failed": 0,
        "search_hit_only": 1,
        "metadata_read": 2,
        "content_read": 3,
    }
    return levels.get(item.evidence_level, 0)


def _sourcedoc_identity(open_url: str) -> str:
    """Return a provider item id from URL query parameters when present."""
    if not open_url:
        return ""
    try:
        parsed = urlparse(open_url)
        query = parse_qs(parsed.query)
    except ValueError:
        return ""
    for values in query.values():
        for value in values:
            cleaned = value.strip().strip("{}")
            if _looks_like_guid(cleaned):
                return cleaned
    return ""


def _looks_like_guid(value: str) -> bool:
    return bool(
        re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            value,
        )
    )


def _without_sensitive_keys(value: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): item
        for key, item in value.items()
        if str(key).strip().lower() != "read_handle"
    }


def _registry_source_type(source_type: str, *, open_url: str, workspace_path: str) -> str:
    """Prefer registry source type markers over model-invented labels."""
    reference_text = " ".join(part for part in (open_url, workspace_path) if part).lower()
    if not reference_text:
        return source_type
    try:
        constraints = load_semantic_catalog().retrieval_constraints
    except Exception:  # noqa: BLE001 - evidence parsing must still validate.
        return source_type
    markers_by_type = getattr(constraints, "source_type_markers", {})
    known_types = set(markers_by_type)
    if source_type in known_types:
        return source_type
    for candidate_type, markers in markers_by_type.items():
        if any(marker and marker in reference_text for marker in markers):
            return str(candidate_type)
    return source_type
