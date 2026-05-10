from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

from crisai.intranet.config import IntranetSettings


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
