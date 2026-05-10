"""Validated evidence handoff contracts for retrieval workflows."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

ALLOWED_EVIDENCE_LEVELS = {
    "search_hit_only",
    "metadata_read",
    "content_read",
    "read_failed",
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
        return cls(
            source_type=str(data.get("source_type") or "").strip(),
            title=str(data.get("title") or "").strip(),
            open_url=str(data.get("open_url") or "").strip(),
            location=str(data.get("location") or "").strip(),
            read_handle=str(data.get("read_handle") or "").strip(),
            workspace_path=str(data.get("workspace_path") or "").strip(),
            content_id=str(data.get("content_id") or "").strip(),
            metadata=dict(metadata),
        )

    def validate(self) -> None:
        if not self.source_type:
            raise ValueError("source.source_type is required.")
        if not self.title:
            raise ValueError("source.title is required.")
        has_reference = any((self.open_url, self.read_handle, self.workspace_path, self.content_id))
        if not has_reference:
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


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One source plus its current retrieval/read status."""

    source: SourceReference
    evidence_level: str
    read_status: str
    read_tool: str = ""
    content_excerpt: str = ""
    raw_error: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceItem:
        source_raw = data.get("source") or {}
        if not isinstance(source_raw, dict):
            raise ValueError("item.source must be an object.")
        return cls(
            source=SourceReference.from_dict(source_raw),
            evidence_level=str(data.get("evidence_level") or "").strip(),
            read_status=str(data.get("read_status") or "").strip(),
            read_tool=str(data.get("read_tool") or "").strip(),
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
            "read_tool": self.read_tool,
            "content_excerpt": self.content_excerpt,
            "raw_error": self.raw_error,
        }


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
            items=[EvidenceItem.from_dict(item) for item in raw_items],
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

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def parse_evidence_bundle(text: str) -> EvidenceBundle:
    """Parse the first valid fenced JSON EvidenceBundle from text."""
    errors: list[str] = []
    for match in _JSON_FENCE_RE.finditer(text or ""):
        raw = match.group(1)
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict) and payload.get("schema_version") == "evidence_bundle_v1":
                return EvidenceBundle.from_dict(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(str(exc))
    suffix = f" Last validation error: {errors[-1]}" if errors else ""
    raise ValueError(f"No valid fenced evidence_bundle_v1 JSON block found.{suffix}")


def request_requires_content_read(message: str) -> bool:
    """Return True for requests where metadata-only evidence is insufficient."""
    text = (message or "").lower()
    summary_markers = ("summarise", "summarize", "summary", "what does", "what is in")
    source_markers = ("document", "deck", "presentation", "file", "source", "read", "open")
    if any(marker in text for marker in summary_markers) and any(marker in text for marker in source_markers):
        return True
    return "summarise the" in text or "summarize the" in text


def render_evidence_bundle_block(bundle: EvidenceBundle) -> str:
    """Render a fenced JSON block for prompts and traces."""
    return "```json\n" + bundle.to_json() + "\n```"
