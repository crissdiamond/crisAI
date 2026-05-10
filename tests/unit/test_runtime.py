from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from crisai.registry import ServerSpec
from crisai.runtime import RuntimeManager, _resolve_headers


def _make_spec(transport: str, **extra) -> ServerSpec:
    raw: dict = {"transport": transport, "tools": {"allow": ["tool_a"]}, **extra}
    return ServerSpec(
        id="test_server",
        name="Test Server",
        enabled=True,
        transport=transport,
        tags=[],
        raw=raw,
    )


class TestResolveHeaders:
    def test_empty_when_no_config(self):
        assert _resolve_headers({}) == {}

    def test_literal_headers_returned(self):
        raw = {"headers": {"X-Custom": "value", "Accept": "application/json"}}
        result = _resolve_headers(raw)
        assert result["X-Custom"] == "value"
        assert result["Accept"] == "application/json"

    def test_api_key_env_injects_bearer(self, monkeypatch):
        monkeypatch.setenv("MY_API_KEY", "secret123")
        result = _resolve_headers({"api_key_env": "MY_API_KEY"})
        assert result["Authorization"] == "Bearer secret123"

    def test_api_key_env_skipped_when_unset(self, monkeypatch):
        monkeypatch.delenv("MISSING_KEY", raising=False)
        result = _resolve_headers({"api_key_env": "MISSING_KEY"})
        assert "Authorization" not in result

    def test_literal_headers_win_over_api_key(self, monkeypatch):
        monkeypatch.setenv("MY_API_KEY", "auto-token")
        raw = {
            "api_key_env": "MY_API_KEY",
            "headers": {"Authorization": "Token override"},
        }
        result = _resolve_headers(raw)
        assert result["Authorization"] == "Token override"


class TestRuntimeManagerBuildServer:
    def test_stdio_builds_mcp_server_stdio(self, monkeypatch, tmp_path):
        captured = {}

        def fake_stdio(name, params, client_session_timeout_seconds, tool_filter):
            captured.update({"name": name, "params": params})
            return MagicMock()

        monkeypatch.setattr("crisai.runtime.MCPServerStdio", fake_stdio)
        spec = _make_spec("stdio", command="python", args=["server.py"])
        RuntimeManager(tmp_path).build_server(spec)
        assert captured["params"]["command"] == "python"
        assert captured["params"]["cwd"] == str(tmp_path)

    def test_sse_passes_url_and_headers(self, monkeypatch, tmp_path):
        captured = {}

        def fake_sse(name, params, client_session_timeout_seconds, tool_filter):
            captured.update({"name": name, "params": params})
            return MagicMock()

        monkeypatch.setattr("crisai.runtime.MCPServerSse", fake_sse)
        spec = _make_spec(
            "sse",
            url="https://mcp.example.com/sse",
            headers={"X-Tenant": "acme"},
        )
        RuntimeManager(tmp_path).build_server(spec)
        assert captured["params"]["url"] == "https://mcp.example.com/sse"
        assert captured["params"]["headers"]["X-Tenant"] == "acme"

    def test_sse_injects_api_key_from_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MY_SSE_KEY", "tok-abc")
        captured = {}

        def fake_sse(name, params, client_session_timeout_seconds, tool_filter):
            captured["params"] = params
            return MagicMock()

        monkeypatch.setattr("crisai.runtime.MCPServerSse", fake_sse)
        spec = _make_spec("sse", url="https://mcp.example.com/sse", api_key_env="MY_SSE_KEY")
        RuntimeManager(tmp_path).build_server(spec)
        assert captured["params"]["headers"]["Authorization"] == "Bearer tok-abc"

    def test_streamable_http_passes_url(self, monkeypatch, tmp_path):
        captured = {}

        def fake_http(name, params, client_session_timeout_seconds, tool_filter):
            captured["params"] = params
            return MagicMock()

        monkeypatch.setattr("crisai.runtime.MCPServerStreamableHttp", fake_http)
        spec = _make_spec("streamable-http", url="https://mcp.example.com/mcp")
        RuntimeManager(tmp_path).build_server(spec)
        assert captured["params"]["url"] == "https://mcp.example.com/mcp"

    def test_unknown_transport_raises_not_implemented(self, tmp_path):
        spec = _make_spec("websocket")
        with pytest.raises(NotImplementedError, match="websocket"):
            RuntimeManager(tmp_path).build_server(spec)
