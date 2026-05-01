from __future__ import annotations

from crisai.runtime import (
    _mcp_client_session_timeout_seconds,
    _resolve_client_session_timeout_seconds,
)


def test_mcp_timeout_default(monkeypatch):
    monkeypatch.delenv("CRISAI_MCP_CLIENT_TIMEOUT_SECONDS", raising=False)
    assert _mcp_client_session_timeout_seconds() == 60.0


def test_mcp_timeout_from_env(monkeypatch):
    monkeypatch.setenv("CRISAI_MCP_CLIENT_TIMEOUT_SECONDS", "90")
    assert _mcp_client_session_timeout_seconds() == 90.0


def test_mcp_timeout_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("CRISAI_MCP_CLIENT_TIMEOUT_SECONDS", "bogus")
    assert _mcp_client_session_timeout_seconds() == 60.0


def test_mcp_timeout_clamps_minimum(monkeypatch):
    monkeypatch.setenv("CRISAI_MCP_CLIENT_TIMEOUT_SECONDS", "2")
    assert _mcp_client_session_timeout_seconds() == 10.0


def test_server_timeout_override(monkeypatch):
    monkeypatch.setenv("CRISAI_MCP_CLIENT_TIMEOUT_SECONDS", "60")
    assert _resolve_client_session_timeout_seconds({"client_timeout_seconds": 240}) == 240.0


def test_server_timeout_invalid_override_falls_back(monkeypatch):
    monkeypatch.setenv("CRISAI_MCP_CLIENT_TIMEOUT_SECONDS", "60")
    assert _resolve_client_session_timeout_seconds({"client_timeout_seconds": "oops"}) == 60.0
