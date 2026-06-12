"""Short reference tokens for SharePoint document reads.

A Graph drive id is ~66 chars of opaque base64 the model corrupts when copying
it across the search->read handover (the recurring "404 on a malformed drive
id" failure). Search results now carry a short ref the server resolves, and the
raw drive-id read tools are retired so the model can't pass long ids at all.
"""

import base64
import json

import pytest

from crisai.servers import sharepoint_server


def test_read_handle_is_short_and_resolves():
    ref = sharepoint_server._encode_read_handle("b!" + "Z" * 60, "item-XYZ")
    assert ref.startswith("spdoc-")
    assert len(ref) <= 16
    assert sharepoint_server._decode_read_handle(ref) == ("b!" + "Z" * 60, "item-XYZ")


def test_mint_ref_is_stable_for_same_item():
    first = sharepoint_server._mint_ref("d1", "i1")
    second = sharepoint_server._mint_ref("d1", "i1")
    assert first == second


def test_decode_unknown_ref_raises_clear_error():
    with pytest.raises(ValueError, match="Re-run the search"):
        sharepoint_server._decode_read_handle("spdoc-deadbeef")


def test_decode_legacy_base64_handle_still_works():
    payload = base64.urlsafe_b64encode(
        json.dumps({"drive_id": "d9", "item_id": "i9"}).encode("utf-8")
    ).decode("ascii").rstrip("=")
    legacy = f"sharepoint_doc:{payload}"
    assert sharepoint_server._decode_read_handle(legacy) == ("d9", "i9")


def test_normalise_item_emits_short_ref_that_resolves():
    drive_id = "b!" + "A" * 60
    item = {"id": "itemA", "name": "deck.pptx", "parentReference": {"driveId": drive_id}}

    out = sharepoint_server._normalise_item(item)

    assert out["read_handle"].startswith("spdoc-")
    assert len(out["read_handle"]) <= 16
    assert sharepoint_server._decode_read_handle(out["read_handle"]) == (drive_id, "itemA")


def test_resolve_drive_id_resolves_arbitrary_double_underscore_placeholder(monkeypatch):
    monkeypatch.setattr(sharepoint_server, "_my_drive_id", lambda: "REAL-DRIVE")
    assert sharepoint_server._resolve_drive_id("__TODO__") == "REAL-DRIVE"
    assert sharepoint_server._resolve_drive_id("__anything_here__") == "REAL-DRIVE"
