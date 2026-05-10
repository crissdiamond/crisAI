from __future__ import annotations

import pytest

from crisai.orchestration.evidence_contract import (
    EvidenceBundle,
    parse_evidence_bundle,
    request_requires_content_read,
)


def _bundle(level: str = "content_read") -> dict:
    return {
        "schema_version": "evidence_bundle_v1",
        "request": "Summarise the deck",
        "items": [
            {
                "source": {
                    "source_type": "sharepoint_document",
                    "title": "Deck.pptx",
                    "open_url": "https://example.com/deck.pptx",
                    "read_handle": "sharepoint_doc:abc",
                    "metadata": {},
                },
                "evidence_level": level,
                "read_status": "read_success" if level == "content_read" else "not_read",
                "read_tool": "read_sharepoint_document_by_handle" if level == "content_read" else "",
                "content_excerpt": "Slide 1\nStrategy" if level == "content_read" else "",
                "raw_error": "Graph 400" if level == "read_failed" else "",
            }
        ],
        "gaps": [],
    }


def test_parse_evidence_bundle_from_fenced_json() -> None:
    raw = """
```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Summarise the deck",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "Deck.pptx",
        "open_url": "https://example.com/deck.pptx",
        "read_handle": "sharepoint_doc:abc",
        "metadata": {}
      },
      "evidence_level": "content_read",
      "read_status": "read_success",
      "read_tool": "read_sharepoint_document_by_handle",
      "content_excerpt": "Slide 1",
      "raw_error": ""
    }
  ],
  "gaps": []
}
```
"""
    bundle = parse_evidence_bundle(raw)
    assert bundle.has_content_read() is True
    assert bundle.items[0].source.title == "Deck.pptx"


def test_evidence_bundle_rejects_invalid_level() -> None:
    payload = _bundle(level="made_up")
    with pytest.raises(ValueError, match="evidence_level"):
        EvidenceBundle.from_dict(payload)


def test_read_failed_requires_raw_error() -> None:
    payload = _bundle(level="read_failed")
    payload["items"][0]["raw_error"] = ""
    with pytest.raises(ValueError, match="raw_error"):
        EvidenceBundle.from_dict(payload)


def test_request_requires_content_read_for_document_summary() -> None:
    assert request_requires_content_read("Can you summarise this document?") is True
    assert request_requires_content_read("Find documents about strategy") is False
