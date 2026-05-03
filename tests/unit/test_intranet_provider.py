from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest
import yaml

from crisai.intranet.config import IntranetSettings, SharePointSiteEntry, load_intranet_settings
import crisai.intranet.providers.sharepoint_pages as sharepoint_pages
from crisai.intranet.providers.sharepoint_pages import (
    SharePointPagesProvider,
    effective_allow_hosts,
    _sitepage_urls_in_object,
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


def test_sitepage_urls_in_object_finds_embedded_sharepoint_urls() -> None:
    payload = {
        "links": [
            {"url": "https://contoso.sharepoint.com/sites/hr/SitePages/integration-patterns.aspx"},
        ],
        "note": "see https://contoso.sharepoint.com/sites/hr/SitePages/detail.aspx too",
    }
    urls = _sitepage_urls_in_object(payload)
    assert "https://contoso.sharepoint.com/sites/hr/SitePages/integration-patterns.aspx" in urls
    assert "https://contoso.sharepoint.com/sites/hr/SitePages/detail.aspx" in urls


def test_wiki_provider_raises() -> None:
    wiki = WikiProvider()
    with pytest.raises(RuntimeError, match="not implemented"):
        wiki.search("q", 5)
    with pytest.raises(RuntimeError, match="list_page_links"):
        wiki.list_page_links("s", "p")
    with pytest.raises(RuntimeError, match="list_all_pages"):
        wiki.list_all_pages()


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


def test_load_intranet_settings_page_cache_ttl_from_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure no env override so the YAML value is used.
    monkeypatch.delenv("INTRANET_PAGE_CACHE_TTL_HOURS", raising=False)
    reg = tmp_path / "registry"
    reg.mkdir()
    (reg / "intranet.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "intranet": {
                    "provider": "sharepoint_pages",
                    "allow_hosts": [],
                    "limits": {"max_fetch_chars": 5000, "graph_timeout_seconds": 30, "page_cache_ttl_hours": 8},
                    "sharepoint_pages": {"sites": []},
                },
            }
        ),
        encoding="utf-8",
    )
    cfg = load_intranet_settings(reg)
    assert cfg.page_cache_ttl_hours == 8


def test_load_intranet_settings_page_cache_ttl_env_overrides_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reg = tmp_path / "registry"
    reg.mkdir()
    (reg / "intranet.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "intranet": {
                    "provider": "sharepoint_pages",
                    "allow_hosts": [],
                    "limits": {"page_cache_ttl_hours": 8},
                    "sharepoint_pages": {"sites": []},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("INTRANET_PAGE_CACHE_TTL_HOURS", "2")
    cfg = load_intranet_settings(reg)
    assert cfg.page_cache_ttl_hours == 2


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


# ---------------------------------------------------------------------------
# list_all_pages: cache management
# ---------------------------------------------------------------------------

def _make_settings(ttl_hours: int = 4) -> IntranetSettings:
    return IntranetSettings(
        provider="sharepoint_pages",
        allow_hosts=["contoso.sharepoint.com"],
        max_fetch_chars=5000,
        graph_timeout_seconds=60,
        raw_sharepoint_sites=[],
        page_cache_ttl_hours=ttl_hours,
    )


def _make_sites() -> list[SharePointSiteEntry]:
    return [
        SharePointSiteEntry(
            label="hr",
            graph_site_id="site-a",
            web_url="https://contoso.sharepoint.com/sites/hr",
        )
    ]


def test_list_all_pages_fetches_from_graph_and_caches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    graph_calls: list[str] = []

    def fake_graph_get(path: str, params: dict | None = None, timeout: int = 60) -> dict:
        graph_calls.append(path)
        return {
            "value": [
                {"id": "p1", "title": "Page A", "webUrl": "https://contoso.sharepoint.com/sites/hr/SitePages/a.aspx"},
                {"id": "p2", "title": "Page B", "webUrl": "https://contoso.sharepoint.com/sites/hr/SitePages/b.aspx"},
            ]
        }

    monkeypatch.setattr(sharepoint_pages.ms_graph, "graph_get", fake_graph_get)
    monkeypatch.setattr(sharepoint_pages.ms_graph, "graph_get_url", lambda *a, **kw: {"value": []})

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    prov = SharePointPagesProvider(settings=_make_settings(), sites=_make_sites(), workspace_root=workspace)

    pages = prov.list_all_pages()

    assert len(pages) == 2
    assert pages[0]["title"] == "Page A"
    assert pages[0]["graph_site_id"] == "site-a"
    assert pages[1]["graph_page_id"] == "p2"
    assert len(graph_calls) >= 1

    # Cache file should now exist.
    cache_file = workspace / ".cache" / "intranet_pages_cache.json"
    assert cache_file.exists()
    cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert cached_data["ttl_hours"] == 4
    assert len(cached_data["pages"]) == 2


def test_list_all_pages_returns_cached_result_without_graph_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    graph_calls: list[str] = []

    def fake_graph_get(path: str, params: dict | None = None, timeout: int = 60) -> dict:
        graph_calls.append(path)
        return {"value": []}

    monkeypatch.setattr(sharepoint_pages.ms_graph, "graph_get", fake_graph_get)

    workspace = tmp_path / "workspace"
    cache_dir = workspace / ".cache"
    cache_dir.mkdir(parents=True)
    cached_pages = [{"title": "Cached Page", "web_url": "u", "graph_site_id": "s", "graph_page_id": "p", "site_label": "hr"}]
    cache_data = {
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ttl_hours": 4,
        "pages": cached_pages,
    }
    (cache_dir / "intranet_pages_cache.json").write_text(json.dumps(cache_data), encoding="utf-8")

    prov = SharePointPagesProvider(settings=_make_settings(), sites=_make_sites(), workspace_root=workspace)
    pages = prov.list_all_pages()

    assert pages == cached_pages
    assert graph_calls == [], "Graph should not be called when cache is fresh"


def test_list_all_pages_ignores_expired_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_graph_get(path: str, params: dict | None = None, timeout: int = 60) -> dict:
        return {
            "value": [{"id": "fresh", "title": "Fresh Page", "webUrl": "https://contoso.sharepoint.com/sites/hr/SitePages/fresh.aspx"}]
        }

    monkeypatch.setattr(sharepoint_pages.ms_graph, "graph_get", fake_graph_get)
    monkeypatch.setattr(sharepoint_pages.ms_graph, "graph_get_url", lambda *a, **kw: {"value": []})

    workspace = tmp_path / "workspace"
    cache_dir = workspace / ".cache"
    cache_dir.mkdir(parents=True)
    # Write a cache entry that is 5 hours old (TTL is 4 h).
    stale_ts = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).isoformat()
    stale_data = {
        "fetched_at": stale_ts,
        "ttl_hours": 4,
        "pages": [{"title": "Stale Page", "web_url": "u", "graph_site_id": "s", "graph_page_id": "p", "site_label": "hr"}],
    }
    (cache_dir / "intranet_pages_cache.json").write_text(json.dumps(stale_data), encoding="utf-8")

    prov = SharePointPagesProvider(settings=_make_settings(ttl_hours=4), sites=_make_sites(), workspace_root=workspace)
    pages = prov.list_all_pages()

    assert any(p["title"] == "Fresh Page" for p in pages), "Expired cache should be ignored"


def test_list_all_pages_no_workspace_root_skips_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without workspace_root the provider fetches from Graph and skips caching."""

    def fake_graph_get(path: str, params: dict | None = None, timeout: int = 60) -> dict:
        return {"value": [{"id": "x", "title": "NoCache", "webUrl": "https://contoso.sharepoint.com/sites/hr/SitePages/x.aspx"}]}

    monkeypatch.setattr(sharepoint_pages.ms_graph, "graph_get", fake_graph_get)
    monkeypatch.setattr(sharepoint_pages.ms_graph, "graph_get_url", lambda *a, **kw: {"value": []})

    prov = SharePointPagesProvider(settings=_make_settings(), sites=_make_sites(), workspace_root=None)
    pages = prov.list_all_pages()

    assert any(p["title"] == "NoCache" for p in pages)
