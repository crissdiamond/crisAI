from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from crisai.intranet.config import IntranetSettings, SharePointSiteEntry, load_intranet_settings
import crisai.intranet.providers.sharepoint_pages as sharepoint_pages
from crisai.intranet.providers.sharepoint_pages import (
    SharePointPagesProvider,
    effective_allow_hosts,
    _strip_html,
)
from crisai.intranet.providers.wiki import WikiProvider


def test_load_intranet_settings_missing_file(tmp_path: Path) -> None:
    reg = tmp_path / "registry"
    reg.mkdir()
    cfg = load_intranet_settings(reg)
    assert cfg.provider == "sharepoint_pages"
    assert cfg.raw_sharepoint_sites == []


def test_load_intranet_settings_round_trip(tmp_path: Path) -> None:
    reg = tmp_path / "registry"
    reg.mkdir()
    (reg / "intranet.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "intranet": {
                    "provider": "sharepoint_pages",
                    "allow_hosts": ["Contoso.Sharepoint.COM"],
                    "limits": {"max_fetch_chars": 5000, "graph_timeout_seconds": 45},
                    "sharepoint_pages": {
                        "sites": [{"label": "a", "graph_site_id": "x,y,z"}],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    cfg = load_intranet_settings(reg)
    assert cfg.provider == "sharepoint_pages"
    assert cfg.allow_hosts == ["contoso.sharepoint.com"]
    assert cfg.max_fetch_chars == 5000
    assert cfg.graph_timeout_seconds == 45
    assert len(cfg.raw_sharepoint_sites) == 1


def test_effective_allow_hosts_explicit() -> None:
    settings = IntranetSettings(
        provider="sharepoint_pages",
        allow_hosts=["hr.contoso.com"],
        max_fetch_chars=1000,
        graph_timeout_seconds=60,
        raw_sharepoint_sites=[],
    )
    sites = [
        SharePointSiteEntry(
            label="s",
            graph_site_id="id",
            web_url="https://other.com/sites/x",
        )
    ]
    assert effective_allow_hosts(settings, sites) == {"hr.contoso.com"}


def test_effective_allow_hosts_derived_from_sites() -> None:
    settings = IntranetSettings(
        provider="sharepoint_pages",
        allow_hosts=[],
        max_fetch_chars=1000,
        graph_timeout_seconds=60,
        raw_sharepoint_sites=[],
    )
    sites = [
        SharePointSiteEntry(
            label="s",
            graph_site_id="id",
            web_url="https://tenant.sharepoint.com/sites/hr",
        )
    ]
    assert effective_allow_hosts(settings, sites) == {"tenant.sharepoint.com"}


def test_strip_html_removes_tags() -> None:
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_wiki_provider_raises() -> None:
    wiki = WikiProvider()
    with pytest.raises(RuntimeError, match="not implemented"):
        wiki.search("q", 5)
    with pytest.raises(RuntimeError, match="list_page_links"):
        wiki.list_page_links("s", "p")


def test_list_page_links_filters_same_host_sitepages(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = {
        "horizontalSections": [
            {
                "columns": [
                    {
                        "webparts": [
                            {
                                "innerHtml": (
                                    '<a href="integration-patterns.aspx">Patterns</a> '
                                    '<a href="https://evil.example/page">bad</a> '
                                    '<a href="/sites/it-architecture/SitePages/integration.aspx">i</a>'
                                )
                            }
                        ]
                    }
                ]
            }
        ]
    }

    def fake_get(path: str, params: dict | None = None, timeout: int = 60) -> dict:
        assert "$expand" in (params or {})
        return {
            "webUrl": "https://contoso.sharepoint.com/sites/it-architecture/SitePages/Hub.aspx",
            "canvasLayout": canvas,
        }

    monkeypatch.setattr(sharepoint_pages.ms_graph, "graph_get", fake_get)
    settings = IntranetSettings(
        provider="sharepoint_pages",
        allow_hosts=["contoso.sharepoint.com"],
        max_fetch_chars=5000,
        graph_timeout_seconds=60,
        raw_sharepoint_sites=[],
    )
    sites = [
        SharePointSiteEntry(
            label="ea",
            graph_site_id="site-a",
            web_url="https://contoso.sharepoint.com/sites/it-architecture",
        )
    ]
    prov = SharePointPagesProvider(
        settings=settings,
        sites=sites,
        allowed_hosts={"contoso.sharepoint.com"},
    )
    links = prov.list_page_links("site-a", "page-1")
    urls = {x["web_url"] for x in links}
    assert "https://contoso.sharepoint.com/sites/it-architecture/SitePages/integration-patterns.aspx" in urls
    assert "https://contoso.sharepoint.com/sites/it-architecture/SitePages/integration.aspx" in urls
    assert not any("evil.example" in u for u in urls)


def test_sharepoint_search_token_fallback_when_odata_title_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """OData exact title substring can be empty; provider should list pages and match tokens."""

    def fake_graph_get(path: str, params: dict | None = None, timeout: int = 60) -> dict:
        p = params or {}
        if "$filter" in p:
            return {"value": []}
        return {
            "value": [
                {
                    "id": "p1",
                    "title": "Integration overview",
                    "name": "Integration-overview.aspx",
                    "webUrl": "https://contoso.sharepoint.com/sites/hr/SitePages/a.aspx",
                    "description": "Design patterns for services",
                },
                {
                    "id": "p2",
                    "title": "Holiday notice",
                    "name": "Holiday.aspx",
                    "webUrl": "https://contoso.sharepoint.com/sites/hr/SitePages/b.aspx",
                    "description": "",
                },
            ]
        }

    monkeypatch.setattr(sharepoint_pages.ms_graph, "graph_get", fake_graph_get)
    settings = IntranetSettings(
        provider="sharepoint_pages",
        allow_hosts=["contoso.sharepoint.com"],
        max_fetch_chars=5000,
        graph_timeout_seconds=60,
        raw_sharepoint_sites=[],
    )
    sites = [
        SharePointSiteEntry(
            label="hr",
            graph_site_id="site-a",
            web_url="https://contoso.sharepoint.com/sites/hr",
        )
    ]
    prov = SharePointPagesProvider(
        settings=settings,
        sites=sites,
        allowed_hosts={"contoso.sharepoint.com"},
    )
    hits = prov.search("integration pattern", max_hits=10)
    assert len(hits) == 1
    assert hits[0]["graph_page_id"] == "p1"
    assert "Integration" in hits[0]["title"]


def test_sharepoint_fetch_rejects_unknown_site() -> None:
    settings = IntranetSettings(
        provider="sharepoint_pages",
        allow_hosts=["contoso.sharepoint.com"],
        max_fetch_chars=5000,
        graph_timeout_seconds=60,
        raw_sharepoint_sites=[],
    )
    sites = [
        SharePointSiteEntry(
            label="ok",
            graph_site_id="site-a",
            web_url="https://contoso.sharepoint.com/sites/hr",
        )
    ]
    prov = SharePointPagesProvider(
        settings=settings,
        sites=sites,
        allowed_hosts={"contoso.sharepoint.com"},
    )
    with pytest.raises(RuntimeError, match="not one of the configured"):
        prov.fetch("other-site", "page-1", max_chars=1000)
