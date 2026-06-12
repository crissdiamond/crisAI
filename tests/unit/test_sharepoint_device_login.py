"""Non-blocking SharePoint device-code login (web "Connect SharePoint" flow)."""

import asyncio

import pytest

from crisai import ms_graph


class _FakeApp:
    """Minimal MSAL PublicClientApplication stand-in for the device flow."""

    def __init__(self, flow=None, token=None):
        self._flow = flow or {
            "user_code": "ABC-123",
            "verification_uri": "https://microsoft.com/devicelogin",
            "verification_uri_complete": "https://microsoft.com/devicelogin?otc=ABC-123",
            "expires_in": 900,
            "message": "Go and enter the code.",
        }
        self._token = token

    def initiate_device_flow(self, scopes=None):
        return self._flow

    def acquire_token_by_device_flow(self, flow):
        return self._token


@pytest.fixture(autouse=True)
def _reset_device_login_state():
    ms_graph._device_login_state.update({"status": "idle", "account": None, "error": None})
    yield
    ms_graph._device_login_state.update({"status": "idle", "account": None, "error": None})


def test_start_device_login_returns_code_without_blocking(monkeypatch):
    monkeypatch.setattr(ms_graph, "_require_env", lambda: None)
    monkeypatch.setattr(ms_graph, "_load_token_cache", lambda: object())
    monkeypatch.setattr(ms_graph, "_build_app", lambda cache: _FakeApp())
    # The completion runs on a daemon thread; stub it so the test is deterministic.
    monkeypatch.setattr(ms_graph, "_complete_device_login", lambda *a, **k: None)
    monkeypatch.setattr(ms_graph, "delegated_auth_status", lambda: {"has_valid_silent_token": False})

    result = ms_graph.start_device_login()

    assert result["user_code"] == "ABC-123"
    assert result["verification_uri"] == "https://microsoft.com/devicelogin"
    assert ms_graph.device_login_status()["status"] == "pending"


def test_complete_device_login_records_connected(monkeypatch):
    monkeypatch.setattr(ms_graph, "_save_token_cache", lambda cache: None)
    recorded: dict[str, object] = {}
    monkeypatch.setattr(ms_graph, "write_token_info", lambda info: recorded.update(info))
    monkeypatch.setattr(ms_graph, "delegated_auth_status", lambda: {"has_valid_silent_token": False})
    app = _FakeApp(
        token={
            "access_token": "tok",
            "scope": "Files.Read.All",
            "id_token_claims": {"preferred_username": "me@example.com"},
        }
    )

    ms_graph._complete_device_login(app, object(), {"user_code": "X"})
    status = ms_graph.device_login_status()

    assert status["status"] == "connected"
    assert status["account"] == "me@example.com"
    assert recorded.get("has_access_token") is True


def test_complete_device_login_records_failure(monkeypatch):
    monkeypatch.setattr(ms_graph, "delegated_auth_status", lambda: {"has_valid_silent_token": False})
    app = _FakeApp(token={"error": "expired_token", "error_description": "Code expired."})

    ms_graph._complete_device_login(app, object(), {"user_code": "X"})
    status = ms_graph.device_login_status()

    assert status["status"] == "failed"
    assert "expired" in (status["error"] or "").lower()


def test_device_login_status_reports_connected_when_token_cached(monkeypatch):
    monkeypatch.setattr(
        ms_graph,
        "delegated_auth_status",
        lambda: {"has_valid_silent_token": True, "account": "cached@example.com"},
    )

    status = ms_graph.device_login_status()

    assert status["status"] == "connected"
    assert status["account"] == "cached@example.com"


def test_web_endpoints_surface_start_and_status(monkeypatch):
    from crisai.apps import web as web_mod

    monkeypatch.setattr(web_mod.ms_graph, "configure_workspace", lambda *a, **k: None)
    monkeypatch.setattr(
        web_mod.ms_graph,
        "start_device_login",
        lambda: {"user_code": "ZZZ-999", "verification_uri": "https://microsoft.com/devicelogin"},
    )
    monkeypatch.setattr(
        web_mod.ms_graph,
        "device_login_status",
        lambda: {"status": "pending", "account": None, "error": None},
    )
    monkeypatch.setattr(
        web_mod, "load_settings", lambda: type("S", (), {"workspace_dir": web_mod.Path("/tmp")})()
    )

    start = asyncio.run(web_mod.api_v1_sharepoint_login_start())
    status = asyncio.run(web_mod.api_v1_sharepoint_login_status())

    assert start["user_code"] == "ZZZ-999"
    assert status["status"] == "pending"
