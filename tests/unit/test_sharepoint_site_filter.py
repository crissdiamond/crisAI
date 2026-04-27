from __future__ import annotations

from crisai.servers.sharepoint_server import _is_likely_personal_onedrive_site


def test_detects_onedrive_personal_site_url():
    assert _is_likely_personal_onedrive_site(
        {
            "webUrl": "https://ucl365-my.sharepoint.com/personal/user_ucl_ac_uk/Documents",
            "displayName": "OneDrive",
        }
    )


def test_team_site_not_flagged_as_personal_onedrive():
    assert not _is_likely_personal_onedrive_site(
        {
            "webUrl": "https://ucl365.sharepoint.com/sites/IntegrationStrategy",
            "displayName": "Integration Strategy",
        }
    )
