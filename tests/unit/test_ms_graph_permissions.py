from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

import crisai.ms_graph as ms_graph

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX file modes only")


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_configure_workspace_hardens_auth_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MS_TOKEN_CACHE_PATH", raising=False)
    monkeypatch.delenv("MS_TOKEN_INFO_PATH", raising=False)
    auth_dir = tmp_path / ".auth"
    auth_dir.mkdir(mode=0o755)

    ms_graph.configure_workspace(tmp_path, namespace="sharepoint")

    assert _mode(auth_dir) == 0o700


def test_write_token_info_creates_private_file_and_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token_info = tmp_path / ".tokens" / "ms_token_info.json"
    monkeypatch.setenv("MS_TOKEN_INFO_PATH", str(token_info))
    monkeypatch.setenv("MS_TOKEN_CACHE_PATH", str(tmp_path / ".tokens" / "msal_token_cache.json"))

    ms_graph.configure_workspace(tmp_path)
    ms_graph.write_token_info({"account": "user@example.com"})

    assert _mode(token_info.parent) == 0o700
    assert _mode(token_info) == 0o600


def test_save_token_cache_creates_private_file_and_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token_cache = tmp_path / ".tokens" / "msal_token_cache.json"
    monkeypatch.setenv("MS_TOKEN_CACHE_PATH", str(token_cache))
    monkeypatch.setenv("MS_TOKEN_INFO_PATH", str(tmp_path / ".tokens" / "ms_token_info.json"))

    class ChangedCache:
        has_state_changed = True

        def serialize(self) -> str:
            return '{"AccessToken": {}}'

    ms_graph.configure_workspace(tmp_path)
    ms_graph._save_token_cache(ChangedCache())  # noqa: SLF001

    assert _mode(token_cache.parent) == 0o700
    assert _mode(token_cache) == 0o600
