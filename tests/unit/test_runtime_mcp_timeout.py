from __future__ import annotations

from crisai.runtime import _mcp_client_session_timeout_seconds


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
