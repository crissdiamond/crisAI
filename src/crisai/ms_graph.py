"""Delegated Microsoft Graph access shared by MCP servers (SharePoint, intranet pages).

Uses the same MSAL public-client cache and environment variables as the SharePoint
server: ``MS_TENANT_ID``, ``MS_CLIENT_ID``, optional ``MS_TOKEN_CACHE_PATH``,
``MS_TOKEN_INFO_PATH``.
"""

from __future__ import annotations

import inspect
import json
import logging
import os
import shutil
import webbrowser
from pathlib import Path
from typing import Any, Callable

import requests
from dotenv import load_dotenv
from msal import PublicClientApplication, SerializableTokenCache

load_dotenv()

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

DEFAULT_SCOPES = [
    "User.Read",
    "Sites.Read.All",
    "Files.Read.All",
]

TENANT_ID = os.getenv("MS_TENANT_ID", "")
CLIENT_ID = os.getenv("MS_CLIENT_ID", "")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}" if TENANT_ID else ""

_token_cache_path: Path | None = None
_token_info_path: Path | None = None
_telemetry: Callable[[str], None] | None = None


def configure_workspace(workspace_root: Path) -> None:
    """Set token cache paths under ``workspace_root/.auth`` (overridable via env)."""
    global _token_cache_path, _token_info_path
    cache_dir = workspace_root / ".auth"
    cache_dir.mkdir(parents=True, exist_ok=True)
    _token_cache_path = Path(os.getenv("MS_TOKEN_CACHE_PATH", cache_dir / "msal_token_cache.json"))
    _token_info_path = Path(os.getenv("MS_TOKEN_INFO_PATH", cache_dir / "msal_token_info.json"))


def set_telemetry_hook(hook: Callable[[str], None] | None) -> None:
    """Optional JSON-line or structured log hook (used by SharePoint MCP)."""
    global _telemetry
    _telemetry = hook


def _emit(event: str) -> None:
    if _telemetry:
        _telemetry(event)
    else:
        logger.debug("%s", event)


def _require_env() -> None:
    missing = []
    if not TENANT_ID:
        missing.append("MS_TENANT_ID")
    if not CLIENT_ID:
        missing.append("MS_CLIENT_ID")
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    if _token_cache_path is None:
        raise RuntimeError("ms_graph.configure_workspace() was not called")


def _load_token_cache() -> SerializableTokenCache:
    cache = SerializableTokenCache()
    assert _token_cache_path is not None
    if _token_cache_path.exists():
        cache.deserialize(_token_cache_path.read_text(encoding="utf-8"))
    return cache


def _save_token_cache(cache: SerializableTokenCache) -> None:
    assert _token_cache_path is not None
    if cache.has_state_changed:
        _token_cache_path.parent.mkdir(parents=True, exist_ok=True)
        _token_cache_path.write_text(cache.serialize(), encoding="utf-8")


def _build_app(cache: SerializableTokenCache) -> PublicClientApplication:
    return PublicClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache,
    )


def _is_wsl_environment() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        content = Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return "microsoft" in content or "wsl" in content


def _open_interactive_browser(url: str) -> bool:
    launched = False
    if _is_wsl_environment():
        for candidate in ("wslview", "explorer.exe"):
            if shutil.which(candidate):
                try:
                    os.spawnlp(os.P_NOWAIT, candidate, candidate, url)
                    launched = True
                    break
                except OSError:
                    continue
    if not launched:
        launched = bool(webbrowser.open(url, new=1))
    if not launched:
        print("Open a browser on this device to visit:")
        print(url)
        _emit("interactive_browser_manual_fallback")
    return True


def _acquire_token_interactive_compat(
    app: PublicClientApplication,
    scopes: list[str],
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "scopes": scopes,
        "prompt": "select_account",
        "domain_hint": "organizations",
    }
    try:
        parameters = inspect.signature(app.acquire_token_interactive).parameters
    except (TypeError, ValueError):
        parameters = {}
    if "open_browser" in parameters:
        kwargs["open_browser"] = _open_interactive_browser
    return app.acquire_token_interactive(**kwargs)


def _acquire_token_device_code(
    app: PublicClientApplication,
    scopes: list[str],
) -> dict[str, Any]:
    """Acquire a token via the OAuth 2.0 device code flow.

    This is the reliable alternative to ``acquire_token_interactive`` in
    environments where the localhost redirect cannot be reached from the
    browser (e.g. WSL2: the Windows browser cannot hit the WSL2 MSAL listener
    on localhost). The flow opens the browser to the device-login URL with the
    user code pre-filled so the user only needs to confirm and authenticate.
    """
    flow = app.initiate_device_flow(scopes=scopes)
    if "user_code" not in flow:
        raise RuntimeError(
            f"Failed to initiate device code flow: {flow.get('error_description') or flow}"
        )
    # ``verification_uri_complete`` pre-fills the user_code in the browser so
    # the user only has to click Continue rather than typing the code manually.
    browser_url = str(flow.get("verification_uri_complete") or flow.get("verification_uri", ""))
    if browser_url:
        _open_interactive_browser(browser_url)
    _emit(
        f"device_code_flow user_code={flow.get('user_code')!r} "
        f"verification_uri={flow.get('verification_uri')!r}"
    )
    # Block until the user completes auth in the browser or the flow expires.
    return app.acquire_token_by_device_flow(flow)


def _format_interactive_auth_failure(result: dict[str, Any] | None, scopes: list[str]) -> str:
    payload = result or {}
    error_code = str(payload.get("error") or "unknown_error")
    description = str(
        payload.get("error_description") or payload.get("error_message") or "No description returned."
    )
    suberror = payload.get("suberror")
    correlation_id = payload.get("correlation_id")
    lines = [
        "Microsoft interactive login did not return an access token.",
        f"Error code: {error_code}",
        f"Description: {description}",
        f"Requested scopes: {', '.join(scopes)}",
        "Troubleshooting:",
        "- Complete the browser flow in the same local session and wait for redirect to localhost.",
        "- If prompted multiple times, close stale auth tabs and retry once.",
        "- If this persists on clean install, run intranet_auth_status / sharepoint_auth_status and login again.",
    ]
    if suberror:
        lines.append(f"Suberror: {suberror}")
    if correlation_id:
        lines.append(f"Correlation ID: {correlation_id}")
    return "\n".join(lines)


def write_token_info(info: dict[str, Any]) -> None:
    assert _token_info_path is not None
    _token_info_path.parent.mkdir(parents=True, exist_ok=True)
    _token_info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")


def read_token_info() -> dict[str, Any]:
    assert _token_info_path is not None
    if _token_info_path.exists():
        return json.loads(_token_info_path.read_text(encoding="utf-8"))
    return {}


def delegated_auth_status() -> dict[str, Any]:
    """Return token cache and silent-acquire state for MCP auth_status tools."""
    _require_env()
    info = read_token_info()
    cache = _load_token_cache()
    app = _build_app(cache)
    accounts = app.get_accounts()
    silent_result = None
    has_valid_silent_token = False
    silent_error = None
    if accounts:
        silent_result = app.acquire_token_silent(scopes=list(DEFAULT_SCOPES), account=accounts[0])
        if silent_result and "access_token" in silent_result:
            has_valid_silent_token = True
        elif silent_result:
            silent_error = silent_result.get("error_description") or str(silent_result)
    return {
        "has_cached_token_info": bool(info),
        "account": info.get("account"),
        "scopes": info.get("scope"),
        "cached_accounts": [a.get("username") for a in accounts],
        "has_valid_silent_token": has_valid_silent_token,
        "silent_error": silent_error,
    }


def acquire_token_silent_only(scopes: list[str] | None = None) -> dict[str, Any] | None:
    """Return MSAL result dict or None if no cached account or silent refresh failed."""
    _require_env()
    scopes = scopes or list(DEFAULT_SCOPES)
    cache = _load_token_cache()
    app = _build_app(cache)
    accounts = app.get_accounts()
    if not accounts:
        return None
    result = app.acquire_token_silent(scopes=scopes, account=accounts[0])
    _save_token_cache(cache)
    return result


def acquire_token(*, scopes: list[str] | None = None, force_interactive: bool = False) -> str:
    """Acquire a delegated Graph access token, using cache or interactive login."""
    _require_env()
    scopes = scopes or list(DEFAULT_SCOPES)

    result = acquire_token_silent_only(scopes=scopes)
    if result and "access_token" in result:
        granted = result.get("scope")
        account = result.get("id_token_claims", {}).get("preferred_username")
        if account or granted:
            write_token_info(
                {
                    "account": account,
                    "scope": granted,
                    "has_access_token": True,
                }
            )
        return str(result["access_token"])

    if not force_interactive:
        force_interactive = True

    cache = _load_token_cache()
    app = _build_app(cache)

    # In WSL2 the Windows browser cannot reach the MSAL localhost redirect
    # listener inside WSL, so the browser-redirect interactive flow hangs
    # until the MCP client timeout fires.  Device code flow is used instead:
    # it opens the browser to the device-login URL (user code pre-filled) and
    # polls for completion without requiring a localhost redirect.
    if _is_wsl_environment():
        _emit(f"interactive_login_device_code scopes={scopes}")
        result = _acquire_token_device_code(app, scopes)
    else:
        _emit(f"interactive_login scopes={scopes}")
        result = _acquire_token_interactive_compat(app, scopes)

    _save_token_cache(cache)

    if not result or "access_token" not in result:
        message = _format_interactive_auth_failure(result, scopes)
        _emit(f"interactive_login_failed error={result}")
        raise RuntimeError(message)

    granted = result.get("scope")
    account = result.get("id_token_claims", {}).get("preferred_username")
    write_token_info(
        {
            "account": account,
            "scope": granted,
            "has_access_token": True,
        }
    )
    _emit(f"token_acquired scopes={granted} account={account}")
    return str(result["access_token"])


def require_silent_token(scopes: list[str] | None = None) -> str:
    """Return a valid access token using silent MSAL refresh only.

    Raises ``RuntimeError`` immediately when the cache holds no account or
    silent refresh fails. Never launches an interactive browser flow. Callers
    (e.g. MCP server tools) should catch this error and surface it to the agent
    as an instruction to call the explicit login tool (``intranet_login`` /
    ``login_sharepoint``).
    """
    _require_env()
    scopes = scopes or list(DEFAULT_SCOPES)
    result = acquire_token_silent_only(scopes=scopes)
    if result and "access_token" in result:
        return str(result["access_token"])
    error_hint = ""
    if result:
        error_hint = f": {result.get('error_description') or result.get('error') or result}"
    raise RuntimeError(
        f"No valid Microsoft Graph token available (silent refresh failed{error_hint}). "
        "Call intranet_login or login_sharepoint to re-authenticate."
    )


def graph_get(
    path: str,
    params: dict[str, Any] | None = None,
    timeout: int = 60,
    *,
    silent_only: bool = False,
) -> dict[str, Any]:
    """GET a Microsoft Graph API path.

    Args:
        path: Graph API path relative to ``/v1.0``.
        params: Optional query parameters.
        timeout: Request timeout in seconds.
        silent_only: When ``True``, use only the cached token (no interactive
            browser prompt). Raises ``RuntimeError`` immediately when auth is
            required, rather than hanging on a browser flow.
    """
    token = require_silent_token() if silent_only else acquire_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    url = f"{GRAPH_BASE}{path}"
    resp = requests.get(url, headers=headers, params=params, timeout=timeout)
    if resp.status_code >= 400:
        raise RuntimeError(f"Graph GET {path} failed: {resp.status_code} {resp.text}")
    return resp.json()


def graph_get_url(url: str, timeout: int = 60, *, silent_only: bool = False) -> dict[str, Any]:
    """GET an absolute Microsoft Graph URL (for example ``@odata.nextLink`` pagination).

    Args:
        url: Absolute Graph URL.
        timeout: Request timeout in seconds.
        silent_only: When ``True``, use only the cached token (no interactive browser prompt).
    """
    token = require_silent_token() if silent_only else acquire_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code >= 400:
        raise RuntimeError(f"Graph GET URL failed: {resp.status_code} {resp.text}")
    return resp.json()


def graph_get_bytes(url: str, timeout: int = 120, *, silent_only: bool = False) -> bytes:
    """Download raw bytes from an absolute Graph URL.

    Args:
        url: Absolute URL.
        timeout: Request timeout in seconds.
        silent_only: When ``True``, use only the cached token (no interactive browser prompt).
    """
    token = require_silent_token() if silent_only else acquire_token()
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code >= 400:
        raise RuntimeError(f"Graph content download failed: {resp.status_code} {resp.text}")
    return resp.content
