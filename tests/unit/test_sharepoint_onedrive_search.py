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


def _raw_item(name: str, guid: str) -> dict:
    return {
        "id": f"item-{guid}",
        "name": name,
        "webUrl": f"https://liveuclac-my.sharepoint.com/personal/x/Doc.aspx?sourcedoc=%7B{guid}%7D",
        "parentReference": {"driveId": "DRV"},
        "file": {"mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    }


def test_search_drops_office_lock_stubs_and_keeps_real_file(monkeypatch):
    # Reproduces the Test001/test003 impersonation: the live search returns the
    # ~$ lock stub ranked above the real deck; the connector must drop the stub so
    # the genuine file surfaces (CRISAI-ADR-015 connector hygiene).
    raw = {
        "value": [
            _raw_item("~$UCL Integration Strategy_Full Presentation v2 (cd).pptx", "7D59EB57"),
            _raw_item("UCL Integration Strategy_Full Presentation v2.pptx", "DD876D07"),
            _raw_item("UCL Integration Strategy full deck v3_cd.pptx", "B6289617"),
        ]
    }
    monkeypatch.setattr(sharepoint_server, "_graph_get", lambda path, params=None, timeout=60: raw)

    hits = sharepoint_server.search_my_onedrive("UCL integration strategy")

    names = [h["name"] for h in hits]
    assert not any(n.startswith("~$") for n in names)
    assert "UCL Integration Strategy_Full Presentation v2.pptx" in names
    assert "UCL Integration Strategy full deck v3_cd.pptx" in names


def test_lock_stub_filter_runs_before_the_max_hits_cap(monkeypatch):
    # A real file ranked just below a stub must not be pushed out by the cap.
    raw = {
        "value": [
            _raw_item("~$Deck.pptx", "AAAA"),
            _raw_item("Real Deck.pptx", "BBBB"),
        ]
    }
    monkeypatch.setattr(sharepoint_server, "_graph_get", lambda path, params=None, timeout=60: raw)

    hits = sharepoint_server.search_my_onedrive("deck", max_hits=1)

    assert [h["name"] for h in hits] == ["Real Deck.pptx"]


def test_is_office_lock_stub_recognises_temp_markers():
    assert sharepoint_server._is_office_lock_stub("~$Strategy.pptx")
    assert sharepoint_server._is_office_lock_stub(".~lock.Report.docx#")
    assert not sharepoint_server._is_office_lock_stub("Strategy v2.pptx")
    assert not sharepoint_server._is_office_lock_stub("Integration-strategy.pdf")
