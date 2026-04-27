from __future__ import annotations

from crisai.servers.sharepoint_server import _normalise_item


def test_normalise_item_duplicates_web_url_as_open_url():
    row = _normalise_item(
        {
            "id": "item-1",
            "name": "Plan.pdf",
            "webUrl": "https://contoso.sharepoint.com/sites/a/Shared%20Documents/Plan.pdf",
            "parentReference": {},
            "file": {"mimeType": "application/pdf"},
        }
    )
    assert row["webUrl"] == "https://contoso.sharepoint.com/sites/a/Shared%20Documents/Plan.pdf"
    assert row["open_url"] == row["webUrl"]
