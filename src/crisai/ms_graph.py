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
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any, Callable, Union

import requests
from dotenv import load_dotenv
from msal import ConfidentialClientApplication, PublicClientApplication, SerializableTokenCache

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
CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET", "")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}" if TENANT_ID else ""

# Type alias covering both MSAL application classes used here.
_MsalApp = Union[PublicClientApplication, ConfidentialClientApplication]

_token_cache_path: Path | None = None
_token_info_path: Path | None = None
_telemetry: Callable[[str], None] | None = None


def configure_workspace(workspace_root: Path, namespace: str = "default") -> None:
    """Set token cache paths under ``workspace_root/.auth`` (overridable via env).

    Args:
        workspace_root: Root of the local workspace; the ``.auth`` subdirectory
            is created automatically.
        namespace: Logical service identifier used to derive independent cache
            file names so that different MCP servers (e.g. ``sharepoint`` and
            ``intranet``) do not share credentials.  The special value
            ``"default"`` preserves the original file names
            (``msal_token_cache.json`` / ``msal_token_info.json``) for
            backward compatibility.  Any other value produces
            ``{namespace}_token_cache.json`` / ``{namespace}_token_info.json``.
            Environment variables ``MS_TOKEN_CACHE_PATH`` and
            ``MS_TOKEN_INFO_PATH`` override the derived paths when set.
    """
    global _token_cache_path, _token_info_path
    cache_dir = workspace_root / ".auth"
    cache_dir.mkdir(parents=True, exist_ok=True)
    if namespace == "default":
        default_cache = cache_dir / "msal_token_cache.json"
        default_info = cache_dir / "msal_token_info.json"
    else:
        default_cache = cache_dir / f"{namespace}_token_cache.json"
        default_info = cache_dir / f"{namespace}_token_info.json"
    _token_cache_path = Path(os.getenv("MS_TOKEN_CACHE_PATH", str(default_cache)))
    _token_info_path = Path(os.getenv("MS_TOKEN_INFO_PATH", str(default_info)))


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


def _build_public_app(cache: SerializableTokenCache) -> PublicClientApplication:
    """Return a ``PublicClientApplication`` backed by *cache*.

    Always public, regardless of ``MS_CLIENT_SECRET``, because only the public
    client supports ``initiate_device_flow`` / ``acquire_token_interactive``.
    Used exclusively for the interactive flow phase.
    """
    return PublicClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache,
    )


def _build_app(cache: SerializableTokenCache) -> _MsalApp:
    """Return the MSAL application used for silent token operations.

    When ``MS_CLIENT_SECRET`` is set the Azure AD app is a confidential client:
    ``ConfidentialClientApplication`` includes the secret in token-endpoint
    requests so silent refresh satisfies ``AADSTS7000218``.  Falls back to
    ``PublicClientApplication`` when no secret is configured (Azure app must
    then have "Allow public client flows" enabled).
    """
    if CLIENT_SECRET:
        return ConfidentialClientApplication(
            client_id=CLIENT_ID,
            client_credential=CLIENT_SECRET,
            authority=AUTHORITY,
            token_cache=cache,
        )
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
    app: _MsalApp,
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


def _show_device_code_instruction(flow: dict[str, Any]) -> None:
    """Print the MSAL/raw device-code instruction to stderr and open the browser."""
    user_code = str(flow.get("user_code", ""))
    verification_uri = str(flow.get("verification_uri", ""))
    instruction = (
        str(flow.get("message", ""))
        or f"Go to {verification_uri} and enter the code: {user_code}"
    )
    # Stderr is visible in the user's terminal; stdout is the MCP wire protocol.
    print(f"\n[crisAI auth] {instruction}\n", file=sys.stderr, flush=True)
    browser_url = str(flow.get("verification_uri_complete") or verification_uri)
    if browser_url:
        _open_interactive_browser(browser_url)
    _emit(f"device_code_flow user_code={user_code!r} verification_uri={verification_uri!r}")


def _acquire_token_device_code(
    app: PublicClientApplication,
    scopes: list[str],
) -> dict[str, Any]:
    """Acquire a token via the OAuth 2.0 device code flow (public client path).

    Used when ``MS_CLIENT_SECRET`` is not set.  Opens the browser to the
    Microsoft device-login URL and polls for completion.  Requires the Azure AD
    app to have "Allow public client flows" enabled.
    """
    flow = app.initiate_device_flow(scopes=scopes)
    if "user_code" not in flow:
        raise RuntimeError(
            f"Failed to initiate device code flow: {flow.get('error_description') or flow}"
        )
    _show_device_code_instruction(flow)
    return app.acquire_token_by_device_flow(flow)


def _acquire_token_device_code_confidential(scopes: list[str]) -> dict[str, Any]:
    """Device code flow for confidential client apps (``MS_CLIENT_SECRET`` present).

    ``ConfidentialClientApplication`` does not expose ``initiate_device_flow``.
    Per RFC 8628 §3.1, confidential clients MUST include their credentials in
    the device authorization request (not only in the token exchange), so both
    steps are done via raw ``requests`` with ``client_secret`` included.

    After a successful exchange the ``refresh_token`` is stored in
    ``_token_info_path`` so that subsequent silent refreshes can use
    ``ConfidentialClientApplication.acquire_token_by_refresh_token``.
    """
    # Step 1 – initiate with client_secret (required by RFC 8628 §3.1 for
    # confidential clients; public-client MSAL flows omit it, causing
    # AADSTS7000218 on the subsequent token exchange).
    dc_resp = requests.post(
        f"{AUTHORITY}/oauth2/v2.0/devicecode",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": " ".join(scopes),
        },
        timeout=30,
    )
    flow: dict[str, Any] = dc_resp.json()
    if "user_code" not in flow:
        raise RuntimeError(
            f"Failed to initiate device code flow: {flow.get('error_description') or flow}"
        )
    _show_device_code_instruction(flow)

    # Step 2 – poll the token endpoint with client_secret included.
    token_endpoint = f"{AUTHORITY}/oauth2/v2.0/token"
    device_code = str(flow.get("device_code", ""))
    interval = max(int(flow.get("interval", 5)), 5)
    expires_in = int(flow.get("expires_in", 900))
    deadline = time.monotonic() + expires_in

    while time.monotonic() < deadline:
        time.sleep(interval)
        resp = requests.post(
            token_endpoint,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "device_code": device_code,
            },
            timeout=30,
        )
        result: dict[str, Any] = resp.json()

        if "access_token" in result:
            # Persist the refresh_token so _acquire_silent_confidential can
            # use it on the next run to bootstrap the MSAL CCA cache.
            info = read_token_info()
            info["refresh_token"] = result.get("refresh_token", "")
            write_token_info(info)
            return result

        error = str(result.get("error", ""))
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        raise RuntimeError(
            f"Device code flow failed: {result.get('error_description', result)}"
        )

    raise RuntimeError("Device code flow timed out – user did not complete authentication.")


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
    has_valid_silent_token = False
    silent_error = None

    if CLIENT_SECRET:
        # Confidential client: try _acquire_silent_confidential which checks
        # both the MSAL CCA cache and the stored refresh_token.
        result = _acquire_silent_confidential(list(DEFAULT_SCOPES))
        has_valid_silent_token = bool(result and "access_token" in result)
        if result and "access_token" not in result:
            silent_error = result.get("error_description") or str(result)
        has_refresh_token = bool(info.get("refresh_token"))
        return {
            "has_cached_token_info": bool(info),
            "account": info.get("account"),
            "scopes": info.get("scope"),
            "has_refresh_token": has_refresh_token,
            "has_valid_silent_token": has_valid_silent_token,
            "silent_error": silent_error,
        }

    cache = _load_token_cache()
    app = _build_public_app(cache)
    accounts = app.get_accounts()
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


def _acquire_silent_confidential(scopes: list[str]) -> dict[str, Any] | None:
    """Silent token acquisition for confidential client apps.

    Tries the MSAL cache first.  When the cache has no account (e.g. after a
    fresh device-code exchange that bypassed MSAL), falls back to the
    ``refresh_token`` stored in ``_token_info_path`` and calls
    ``ConfidentialClientApplication.acquire_token_by_refresh_token`` – which
    includes ``client_secret``, satisfies AADSTS7000218, and also populates
    the MSAL cache so future calls hit the faster silent path.
    """
    cache = _load_token_cache()
    cca = ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=AUTHORITY,
        token_cache=cache,
    )
    accounts = cca.get_accounts()
    if accounts:
        result = cca.acquire_token_silent(scopes=scopes, account=accounts[0])
        _save_token_cache(cache)
        if result and "access_token" in result:
            return result

    # Cache miss – try the persisted refresh_token from the manual device-code flow.
    info = read_token_info()
    refresh_token = info.get("refresh_token", "")
    if not refresh_token:
        return None
    result = cca.acquire_token_by_refresh_token(refresh_token, scopes=scopes)
    _save_token_cache(cache)
    if result and "access_token" in result:
        # Update stored refresh_token (rotated by server).
        info["refresh_token"] = result.get("refresh_token", refresh_token)
        write_token_info(info)
        return result
    return None


def acquire_token_silent_only(scopes: list[str] | None = None) -> dict[str, Any] | None:
    """Return MSAL result dict or None if no cached account or silent refresh failed."""
    _require_env()
    scopes = scopes or list(DEFAULT_SCOPES)
    if CLIENT_SECRET:
        return _acquire_silent_confidential(scopes)
    cache = _load_token_cache()
    app = _build_public_app(cache)
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
            info = read_token_info()
            info.update({"account": account, "scope": granted, "has_access_token": True})
            if result.get("refresh_token"):
                info["refresh_token"] = result["refresh_token"]
            write_token_info(info)
        return str(result["access_token"])

    if not force_interactive:
        force_interactive = True

    # Confidential client path: device code flow with client_secret in the
    # token exchange.  MSAL's ConfidentialClientApplication does not expose
    # initiate_device_flow, so we handle the exchange ourselves via requests.
    if CLIENT_SECRET:
        _emit(f"interactive_login_device_code_confidential scopes={scopes}")
        result = _acquire_token_device_code_confidential(scopes)
    elif _is_wsl_environment():
        # Public client in WSL2: device code flow avoids the broken localhost
        # redirect (Windows browser cannot reach the WSL2 MSAL listener).
        cache = _load_token_cache()
        app = _build_public_app(cache)
        _emit(f"interactive_login_device_code scopes={scopes}")
        result = _acquire_token_device_code(app, scopes)
        _save_token_cache(cache)
    else:
        cache = _load_token_cache()
        app = _build_public_app(cache)
        _emit(f"interactive_login scopes={scopes}")
        result = _acquire_token_interactive_compat(app, scopes)
        _save_token_cache(cache)

    if not result or "access_token" not in result:
        message = _format_interactive_auth_failure(result, scopes)
        _emit(f"interactive_login_failed error={result}")
        raise RuntimeError(message)

    granted = result.get("scope")
    account = result.get("id_token_claims", {}).get("preferred_username")
    # Merge so that fields written by _acquire_token_device_code_confidential
    # (e.g. refresh_token) are preserved rather than overwritten.
    info = read_token_info()
    info.update({"account": account, "scope": granted, "has_access_token": True})
    if result.get("refresh_token"):
        info["refresh_token"] = result["refresh_token"]
    write_token_info(info)
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
