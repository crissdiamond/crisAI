"""Manual Microsoft Graph auth smoke test.

This module is intentionally skipped by pytest and can be run directly:
`python tests/orchestration/test_graph_login.py`.
"""

from __future__ import annotations

import os
import shutil
import webbrowser
from pathlib import Path

import requests
from dotenv import load_dotenv
from msal import PublicClientApplication

load_dotenv()


def _is_wsl_environment() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        content = Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return "microsoft" in content or "wsl" in content


def _open_interactive_browser(url: str) -> None:
    if _is_wsl_environment():
        for candidate in ("wslview", "explorer.exe"):
            if shutil.which(candidate):
                os.spawnlp(os.P_NOWAIT, candidate, candidate, url)
                return
    webbrowser.open(url, new=1)


def run_manual_graph_login_smoke() -> None:
    tenant_id = os.environ["MS_TENANT_ID"]
    client_id = os.environ["MS_CLIENT_ID"]
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scopes = ["User.Read", "Sites.Read.All", "Files.Read.All"]

    app = PublicClientApplication(client_id=client_id, authority=authority)
    result = app.acquire_token_interactive(
        scopes=scopes,
        domain_hint="organizations",
        open_browser=_open_interactive_browser,
    )

    print("\nGranted scopes:")
    print(result.get("scope"))

    if "access_token" not in result:
        print("Login failed")
        print(result)
        raise SystemExit(1)

    print("Login succeeded")
    print("Account:", result.get("id_token_claims", {}).get("preferred_username"))

    headers = {
        "Authorization": f"Bearer {result['access_token']}",
        "Accept": "application/json",
    }

    for endpoint in (
        "https://graph.microsoft.com/v1.0/me",
        "https://graph.microsoft.com/v1.0/sites/root",
        "https://graph.microsoft.com/v1.0/sites?search=*",
        "https://graph.microsoft.com/v1.0/me/drives",
    ):
        response = requests.get(endpoint, headers=headers, timeout=30)
        print(f"\n{endpoint} status:", response.status_code)
        print(response.text[:2000])


def test_graph_login_manual_only():
    import pytest

    pytest.skip("Manual smoke test only. Run file directly when needed.")


if __name__ == "__main__":
    run_manual_graph_login_smoke()
