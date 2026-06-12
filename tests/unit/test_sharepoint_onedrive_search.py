"""OneDrive search resilience: placeholder drive ids resolve to the user's drive.

Agents frequently call search_drive_documents with placeholder ids
(`__placeholder__`, `root`, `me`, …) instead of threading a real id from
list_my_drives. These resolve to the primary OneDrive instead of failing, and a
dedicated search_my_onedrive tool removes the need for a drive id entirely.
"""

import pytest

from crisai.servers import sharepoint_server


@pytest.mark.parametrize("alias", ["", "root", "me", "onedrive", "__placeholder__", "__invalid__", "ONEDRIVE"])
def test_resolve_drive_id_maps_placeholder_to_primary(monkeypatch, alias):
    monkeypatch.setattr(sharepoint_server, "_my_drive_id", lambda: "REAL-DRIVE")
    assert sharepoint_server._resolve_drive_id(alias) == "REAL-DRIVE"


def test_resolve_drive_id_keeps_real_id(monkeypatch):
    monkeypatch.setattr(sharepoint_server, "_my_drive_id", lambda: "SHOULD-NOT-BE-CALLED")
    assert sharepoint_server._resolve_drive_id("b!Tg1M-real-id") == "b!Tg1M-real-id"


def test_search_my_onedrive_targets_me_drive(monkeypatch):
    captured: dict[str, str] = {}

    def fake_get(path, params=None, timeout=60):
        captured["path"] = path
        return {"value": []}

    monkeypatch.setattr(sharepoint_server, "_graph_get", fake_get)

    sharepoint_server.search_my_onedrive("UCL integration strategy")

    assert "/me/drive/root/search" in captured["path"]


def test_search_drive_documents_resolves_placeholder(monkeypatch):
    captured: dict[str, str] = {}

    def fake_get(path, params=None, timeout=60):
        captured["path"] = path
        return {"value": []}

    monkeypatch.setattr(sharepoint_server, "_my_drive_id", lambda: "REAL-DRIVE")
    monkeypatch.setattr(sharepoint_server, "_graph_get", fake_get)

    sharepoint_server.search_drive_documents("__placeholder__", "UCL integration strategy")

    assert "/drives/REAL-DRIVE/root/search" in captured["path"]
