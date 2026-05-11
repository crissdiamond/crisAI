from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

from crisai.intranet.config import IntranetSettings
from crisai.intranet.providers.sharepoint_pages import SharePointPagesProvider
from crisai.intranet.providers.wiki import WikiProvider


def _load_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(sys, "argv", ["intranet_server.py", str(tmp_path)])
    import crisai.servers.intranet_server as intranet_server

    return importlib.reload(intranet_server)


def test_build_custom_provider_from_class_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    intranet_server = _load_server(monkeypatch, tmp_path)
    module = types.ModuleType("tests_dummy_intranet_provider")

    class DummyProvider:
        def __init__(self, settings: dict[str, str], workspace_root: Path) -> None:
            self.settings = settings
            self.workspace_root = workspace_root

    module.DummyProvider = DummyProvider
    sys.modules[module.__name__] = module
    cfg = IntranetSettings(
        provider="custom",
        allow_hosts=[],
        max_fetch_chars=1000,
        graph_timeout_seconds=30,
        custom_class_path="tests_dummy_intranet_provider:DummyProvider",
        custom_settings={"base_url": "https://wiki.example.com"},
    )

    provider = intranet_server._build_provider(cfg, tmp_path)

    assert isinstance(provider, DummyProvider)
    assert provider.settings == {"base_url": "https://wiki.example.com"}
    assert provider.workspace_root == tmp_path


def test_build_custom_provider_supports_no_arg_constructor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    intranet_server = _load_server(monkeypatch, tmp_path)
    module = types.ModuleType("tests_dummy_no_arg_intranet_provider")

    class DummyProvider:
        pass

    module.DummyProvider = DummyProvider
    sys.modules[module.__name__] = module
    cfg = IntranetSettings(
        provider="custom",
        allow_hosts=[],
        max_fetch_chars=1000,
        graph_timeout_seconds=30,
        custom_class_path="tests_dummy_no_arg_intranet_provider:DummyProvider",
    )

    assert isinstance(intranet_server._build_provider(cfg, tmp_path), DummyProvider)


def test_build_custom_provider_validates_class_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    intranet_server = _load_server(monkeypatch, tmp_path)
    cfg = IntranetSettings(
        provider="custom",
        allow_hosts=[],
        max_fetch_chars=1000,
        graph_timeout_seconds=30,
    )

    with pytest.raises(RuntimeError, match="class_path is empty"):
        intranet_server._build_provider(cfg, tmp_path)

    cfg.custom_class_path = "missing_separator"
    with pytest.raises(RuntimeError, match="module:ClassName"):
        intranet_server._build_provider(cfg, tmp_path)


def test_build_provider_supports_wiki_sharepoint_and_rejects_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    intranet_server = _load_server(monkeypatch, tmp_path)

    wiki_cfg = IntranetSettings(
        provider="wiki",
        allow_hosts=[],
        max_fetch_chars=1000,
        graph_timeout_seconds=30,
    )
    assert isinstance(intranet_server._build_provider(wiki_cfg, tmp_path), WikiProvider)

    sharepoint_cfg = IntranetSettings(
        provider="sharepoint_pages",
        allow_hosts=[],
        max_fetch_chars=1000,
        graph_timeout_seconds=30,
        raw_sharepoint_sites=[],
    )
    provider = intranet_server._build_provider(sharepoint_cfg, tmp_path)
    assert isinstance(provider, SharePointPagesProvider)

    unknown_cfg = IntranetSettings(
        provider="unknown",
        allow_hosts=[],
        max_fetch_chars=1000,
        graph_timeout_seconds=30,
    )
    with pytest.raises(RuntimeError, match="Unknown intranet.provider"):
        intranet_server._build_provider(unknown_cfg, tmp_path)


def test_provider_neutral_tools_delegate_and_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    intranet_server = _load_server(monkeypatch, tmp_path)
    events: list[str] = []

    class Provider:
        def __init__(self) -> None:
            self.search_calls: list[tuple[str, int]] = []
            self.fetch_calls: list[tuple[str, int]] = []
            self.link_calls: list[str] = []
            self.list_calls: list[str] = []

        def login(self) -> str:
            return "logged-in"

        def auth_status(self) -> dict[str, bool]:
            return {"authenticated": True}

        def search(self, query: str, max_hits: int) -> list[dict[str, str]]:
            self.search_calls.append((query, max_hits))
            return [{"title": "Architecture home", "content_id": "page-1"}]

        def fetch(self, content_id: str, max_chars: int) -> str:
            self.fetch_calls.append((content_id, max_chars))
            return "page text"

        def list_links(self, content_id: str) -> list[dict[str, str]]:
            self.link_calls.append(content_id)
            return [{"title": "Child", "content_id": "page-2"}]

        def list_all(self, query: str = "") -> list[dict[str, str]]:
            self.list_calls.append(query)
            return [{"title": "Catalogue", "content_id": "page-3"}]

    provider = Provider()
    monkeypatch.setattr(intranet_server, "PROVIDER", provider)
    monkeypatch.setattr(intranet_server.INTRANET_CFG, "max_fetch_chars", 2500)
    monkeypatch.setattr(intranet_server, "log_event", events.append)

    assert intranet_server.intranet_login() == "logged-in"
    assert intranet_server.intranet_auth_status() == {"authenticated": True}
    assert intranet_server.intranet_search("architecture", max_hits=100) == [
        {"title": "Architecture home", "content_id": "page-1"}
    ]
    assert intranet_server.intranet_search_pages("architecture", max_hits=0) == [
        {"title": "Architecture home", "content_id": "page-1"}
    ]
    assert intranet_server.intranet_fetch_page("page-1") == "page text"
    assert intranet_server.intranet_list_page_links_by_id("page-1") == [{"title": "Child", "content_id": "page-2"}]
    assert intranet_server.intranet_list_all_pages(query="arch") == [{"title": "Catalogue", "content_id": "page-3"}]

    assert provider.search_calls == [("architecture", 50), ("architecture", 1)]
    assert provider.fetch_calls == [("page-1", 4000)]
    assert provider.link_calls == ["page-1"]
    assert provider.list_calls == ["arch"]
    assert any("intranet_search_pages done hits=1" in event for event in events)


def test_sharepoint_legacy_tools_delegate_when_provider_supports_graph_ids(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    intranet_server = _load_server(monkeypatch, tmp_path)

    class SharePointProvider:
        def fetch_graph_page(self, graph_site_id: str, graph_page_id: str, max_chars: int) -> str:
            return f"{graph_site_id}:{graph_page_id}:{max_chars}"

        def list_page_links(self, graph_site_id: str, graph_page_id: str) -> list[dict[str, str]]:
            return [{"site": graph_site_id, "page": graph_page_id}]

    monkeypatch.setattr(intranet_server.INTRANET_CFG, "provider", "sharepoint_pages")
    monkeypatch.setattr(intranet_server.INTRANET_CFG, "max_fetch_chars", 8000)
    monkeypatch.setattr(intranet_server, "PROVIDER", SharePointProvider())

    assert intranet_server.intranet_fetch("site-1", "page-1") == "site-1:page-1:8000"
    assert intranet_server.intranet_list_page_links("site-1", "page-1") == [{"site": "site-1", "page": "page-1"}]


def test_legacy_fetch_fails_for_non_sharepoint_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    intranet_server = _load_server(monkeypatch, tmp_path)

    class NeutralProvider:
        def fetch(self, content_id: str, max_chars: int) -> str:
            return "ok"

    monkeypatch.setattr(intranet_server.INTRANET_CFG, "provider", "custom")
    monkeypatch.setattr(intranet_server, "PROVIDER", NeutralProvider())

    try:
        intranet_server.intranet_fetch("site", "page")
    except RuntimeError as exc:
        assert "Use intranet_fetch_page(content_id)" in str(exc)
    else:
        raise AssertionError("legacy intranet_fetch should fail outside sharepoint_pages")


def test_legacy_link_listing_fails_for_non_sharepoint_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    intranet_server = _load_server(monkeypatch, tmp_path)

    class NeutralProvider:
        def list_links(self, content_id: str) -> list[dict[str, str]]:
            return []

    monkeypatch.setattr(intranet_server.INTRANET_CFG, "provider", "custom")
    monkeypatch.setattr(intranet_server, "PROVIDER", NeutralProvider())

    with pytest.raises(RuntimeError, match="Use intranet_list_page_links_by_id"):
        intranet_server.intranet_list_page_links("site", "page")


def test_provider_errors_are_logged_and_reraised(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    intranet_server = _load_server(monkeypatch, tmp_path)
    events: list[str] = []

    class FailingProvider:
        def search(self, query: str, max_hits: int) -> list[dict[str, str]]:
            raise ValueError("search failed")

        def fetch(self, content_id: str, max_chars: int) -> str:
            raise ValueError("fetch failed")

        def list_links(self, content_id: str) -> list[dict[str, str]]:
            raise ValueError("links failed")

        def list_all(self, query: str = "") -> list[dict[str, str]]:
            raise ValueError("list failed")

    monkeypatch.setattr(intranet_server, "PROVIDER", FailingProvider())
    monkeypatch.setattr(intranet_server, "log_event", events.append)

    with pytest.raises(ValueError, match="search failed"):
        intranet_server.intranet_search_pages("q")
    with pytest.raises(ValueError, match="fetch failed"):
        intranet_server.intranet_fetch_page("page")
    with pytest.raises(ValueError, match="links failed"):
        intranet_server.intranet_list_page_links_by_id("page")
    with pytest.raises(ValueError, match="list failed"):
        intranet_server.intranet_list_pages()

    assert any("intranet_search_pages error=" in event for event in events)
    assert any("intranet_fetch_page error=" in event for event in events)
    assert any("intranet_list_page_links_by_id error=" in event for event in events)
    assert any("intranet_list_pages error=" in event for event in events)
