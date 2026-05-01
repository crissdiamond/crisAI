from __future__ import annotations

import importlib
import sys

# sharepoint_server resolves ROOT from sys.argv[1] when present.
# Force a stable argv shape for unit tests importing this module directly.
sys.argv = [sys.argv[0]]

sharepoint_server = importlib.import_module("crisai.servers.sharepoint_server")


def test_open_interactive_browser_returns_webbrowser_result(monkeypatch):
    monkeypatch.setattr(sharepoint_server, "_is_wsl_environment", lambda: False)
    monkeypatch.setattr(sharepoint_server.webbrowser, "open", lambda _url, new=1: True)

    assert sharepoint_server._open_interactive_browser("https://example.com") is True


def test_open_interactive_browser_returns_true_when_wsl_launcher_available(monkeypatch):
    monkeypatch.setattr(sharepoint_server, "_is_wsl_environment", lambda: True)
    monkeypatch.setattr(sharepoint_server.shutil, "which", lambda candidate: "/usr/bin/wslview" if candidate == "wslview" else None)
    monkeypatch.setattr(sharepoint_server.os, "spawnlp", lambda *args: 12345)

    assert sharepoint_server._open_interactive_browser("https://example.com") is True


def test_open_interactive_browser_falls_back_when_wsl_launcher_fails(monkeypatch):
    monkeypatch.setattr(sharepoint_server, "_is_wsl_environment", lambda: True)
    monkeypatch.setattr(sharepoint_server.shutil, "which", lambda candidate: "/usr/bin/wslview" if candidate == "wslview" else None)

    def _raise_os_error(*_args):
        raise OSError("boom")

    monkeypatch.setattr(sharepoint_server.os, "spawnlp", _raise_os_error)
    monkeypatch.setattr(sharepoint_server.webbrowser, "open", lambda _url, new=1: False)

    assert sharepoint_server._open_interactive_browser("https://example.com") is True


def test_format_interactive_auth_failure_contains_core_fields():
    message = sharepoint_server._format_interactive_auth_failure(
        {
            "error": "invalid_grant",
            "error_description": "Authorization code was invalid or expired.",
            "correlation_id": "abc-123",
            "suberror": "bad_token",
        },
        ["User.Read", "Sites.Read.All"],
    )

    assert "Error code: invalid_grant" in message
    assert "Description: Authorization code was invalid or expired." in message
    assert "Requested scopes: User.Read, Sites.Read.All" in message
    assert "Correlation ID: abc-123" in message
    assert "Suberror: bad_token" in message


def test_format_interactive_auth_failure_handles_missing_payload():
    message = sharepoint_server._format_interactive_auth_failure(None, ["User.Read"])

    assert "Error code: unknown_error" in message
    assert "Requested scopes: User.Read" in message
