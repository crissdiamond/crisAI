"""SharePoint read tools must use silent-only Graph auth.

Regression guard for the `list_my_drives` hang: read tools went through the
interactive `acquire_token()` path, so an unauthenticated call started a
device-code login that blocked until the 240s MCP client timeout crashed the
run. Read wrappers now pass `silent_only=True` so a missing token fails fast.
"""

from crisai.servers import sharepoint_server


def test_graph_get_uses_silent_only_auth(monkeypatch):
    captured: dict[str, object] = {}

    def fake_graph_get(path, params=None, timeout=60, *, silent_only=False):
        captured["silent_only"] = silent_only
        return {"value": []}

    monkeypatch.setattr(sharepoint_server.ms_graph, "graph_get", fake_graph_get)

    sharepoint_server._graph_get("/me/drives")

    assert captured["silent_only"] is True


def test_graph_get_bytes_uses_silent_only_auth(monkeypatch):
    captured: dict[str, object] = {}

    def fake_graph_get_bytes(url, timeout=120, *, silent_only=False):
        captured["silent_only"] = silent_only
        return b"data"

    monkeypatch.setattr(sharepoint_server.ms_graph, "graph_get_bytes", fake_graph_get_bytes)

    sharepoint_server._graph_get_bytes("https://graph.microsoft.com/v1.0/example")

    assert captured["silent_only"] is True
