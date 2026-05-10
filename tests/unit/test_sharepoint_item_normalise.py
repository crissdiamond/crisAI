from __future__ import annotations

import importlib
import io
import sys

import pytest
from pptx import Presentation


def _load_sharepoint_server(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["sharepoint_server.py", str(tmp_path)])
    import crisai.servers.sharepoint_server as sharepoint_server

    return importlib.reload(sharepoint_server)


def _sample_pptx_bytes() -> bytes:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Integration Strategy"
    textbox = slide.shapes.add_textbox(914400, 1371600, 4572000, 914400)
    textbox.text_frame.text = "Target architecture and roadmap"
    output = io.BytesIO()
    prs.save(output)
    return output.getvalue()


def test_normalise_item_duplicates_web_url_as_open_url(monkeypatch: pytest.MonkeyPatch, tmp_path):
    sharepoint_server = _load_sharepoint_server(monkeypatch, tmp_path)
    row = sharepoint_server._normalise_item(
        {
            "id": "item-1",
            "name": "Plan.pdf",
            "webUrl": "https://contoso.sharepoint.com/sites/a/Shared%20Documents/Plan.pdf",
            "parentReference": {"driveId": "drive-1"},
            "file": {"mimeType": "application/pdf"},
        }
    )
    assert row["webUrl"] == "https://contoso.sharepoint.com/sites/a/Shared%20Documents/Plan.pdf"
    assert row["open_url"] == row["webUrl"]
    assert row["read_handle"].startswith("sharepoint_doc:")
    assert sharepoint_server._decode_read_handle(row["read_handle"]) == ("drive-1", "item-1")


def test_decode_read_handle_rejects_malformed_handle(monkeypatch: pytest.MonkeyPatch, tmp_path):
    sharepoint_server = _load_sharepoint_server(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="read_handle"):
        sharepoint_server._decode_read_handle("not-a-handle")


def test_read_sharepoint_document_by_handle_delegates_to_raw_reader(monkeypatch: pytest.MonkeyPatch, tmp_path):
    sharepoint_server = _load_sharepoint_server(monkeypatch, tmp_path)
    handle = sharepoint_server._encode_read_handle("drive-1", "item-1")
    calls: list[tuple[str, str]] = []

    def fake_read_sharepoint_document(drive_id: str, item_id: str) -> str:
        calls.append((drive_id, item_id))
        return "deck text"

    monkeypatch.setattr(sharepoint_server, "read_sharepoint_document", fake_read_sharepoint_document)

    assert sharepoint_server.read_sharepoint_document_by_handle(handle) == "deck text"
    assert calls == [("drive-1", "item-1")]


def test_inspect_sharepoint_powerpoint_by_handle_returns_slide_extraction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    sharepoint_server = _load_sharepoint_server(monkeypatch, tmp_path)
    handle = sharepoint_server._encode_read_handle("drive-1", "item-1")

    monkeypatch.setattr(
        sharepoint_server,
        "_graph_get",
        lambda path: {
            "id": "item-1",
            "name": "Deck.pptx",
            "webUrl": "https://example.com/Deck.pptx",
            "parentReference": {"driveId": "drive-1"},
            "file": {"mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation"},
        },
    )
    monkeypatch.setattr(sharepoint_server, "_graph_get_bytes", lambda url: _sample_pptx_bytes())

    result = sharepoint_server.inspect_sharepoint_powerpoint_by_handle(handle)

    assert result["status"] == "partial_text"
    assert result["slide_count"] == 1
    assert result["source"]["read_handle"] == handle
    assert result["slides"][0]["title"] == "Integration Strategy"
    assert "Target architecture and roadmap" in result["slides"][0]["text"]
