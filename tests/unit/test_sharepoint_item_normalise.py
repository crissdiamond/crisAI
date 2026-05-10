from __future__ import annotations

import importlib
import sys

import pytest


def _load_sharepoint_server(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["sharepoint_server.py", str(tmp_path)])
    import crisai.servers.sharepoint_server as sharepoint_server

    return importlib.reload(sharepoint_server)


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
