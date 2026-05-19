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


def test_parse_evidence_bundle_accepts_legacy_string_source() -> None:
    raw = """
```json
{
  "schema_version": "evidence_bundle_v1",
  "request": "Can you summarise the most recent and likely master document?",
  "items": [
    {
      "source": "UCL Integration Strategy_Full Presentation v2.pptx",
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "read_sharepoint_document_by_handle",
      "content_excerpt": "Integration Strategy v1.0, September 2021.",
      "raw_error": null
    }
  ]
}
```
"""
    bundle = parse_evidence_bundle(raw)

    assert bundle.has_content_read() is True
    assert bundle.items[0].source.title == "UCL Integration Strategy_Full Presentation v2.pptx"
    assert bundle.items[0].source.source_type == "sharepoint_document"
    assert bundle.items[0].source.metadata["normalised_from"] == "string_source"


def test_evidence_item_defaults_to_primary_role() -> None:
    bundle = EvidenceBundle.from_dict(_bundle())

    item = bundle.items[0]
    assert item.evidence_role == "primary"
    assert item.to_dict()["evidence_role"] == "primary"


def test_evidence_item_accepts_role_from_source_metadata() -> None:
    payload = _bundle()
    payload["items"][0]["source"]["metadata"] = {"evidence_role": "supplemental"}

    bundle = EvidenceBundle.from_dict(payload)

    assert bundle.items[0].evidence_role == "supplemental"
    assert bundle.to_dict()["items"][0]["evidence_role"] == "supplemental"


def test_evidence_item_rejects_invalid_role() -> None:
    payload = _bundle()
    payload["items"][0]["evidence_role"] = "candidate"

    with pytest.raises(ValueError, match="evidence_role"):
        EvidenceBundle.from_dict(payload)


def test_evidence_bundle_rejects_invalid_level() -> None:
    payload = _bundle(level="made_up")
    with pytest.raises(ValueError, match="evidence_level"):
        EvidenceBundle.from_dict(payload)


def test_evidence_level_upgrades_after_successful_read() -> None:
    payload = _bundle(level="search_hit_only")
    payload["items"][0]["read_status"] = "read"
    payload["items"][0]["read_tool"] = "read_sharepoint_document_by_handle"
    payload["items"][0]["content_excerpt"] = "Slide 1: Strategy."

    bundle = EvidenceBundle.from_dict(payload)

    assert bundle.items[0].evidence_level == "content_read"


def test_sanitized_bundle_removes_read_handles() -> None:
    payload = _bundle()
    payload["items"][0]["source"]["metadata"] = {
        "read_handle": "sharepoint_doc:nested",
        "site": "Data Team",
    }

    sanitized = EvidenceBundle.from_dict(payload).to_sanitized_dict()
    source = sanitized["items"][0]["source"]

    assert "read_handle" not in source
    assert source["metadata"] == {"site": "Data Team"}


def test_evidence_bundle_dedupes_by_source_guid() -> None:
    payload = _bundle(level="search_hit_only")
    first_url = "https://tenant.sharepoint.com/doc.aspx?sourcedoc=%7B4844F689-9858-498C-A888-95D025216DA8%7D&file=a.pptx"
    second_url = "https://tenant.sharepoint.com/doc.aspx?sourcedoc=%7B4844F689-9858-498C-A888-95D025216DA8%7D&file=b.pptx"
    payload["items"][0]["source"]["open_url"] = first_url
    duplicate = _bundle()["items"][0]
    duplicate["source"]["open_url"] = second_url
    duplicate["source"]["title"] = "Duplicate Deck.pptx"
    payload["items"].append(duplicate)

    bundle = EvidenceBundle.from_dict(payload)

    assert len(bundle.items) == 1
    assert bundle.items[0].source.title == "Duplicate Deck.pptx"
    assert bundle.items[0].evidence_level == "content_read"


def test_source_type_uses_registry_marker_for_model_variant_label() -> None:
    payload = _bundle()
    payload["items"][0]["source"]["source_type"] = "onedrive_document"
    payload["items"][0]["source"]["open_url"] = "https://tenant.sharepoint.com/sites/team/doc.pptx"

    bundle = EvidenceBundle.from_dict(payload)

    assert bundle.items[0].source.source_type == "sharepoint_document"


def test_read_failed_requires_raw_error() -> None:
    payload = _bundle(level="read_failed")
    payload["items"][0]["raw_error"] = ""
    with pytest.raises(ValueError, match="raw_error"):
        EvidenceBundle.from_dict(payload)


def test_request_requires_content_read_for_document_summary() -> None:
    assert request_requires_content_read("Can you summarise this document?") is True
    assert request_requires_content_read("Find documents about strategy") is False
