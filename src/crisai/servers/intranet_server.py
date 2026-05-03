"""MCP server for scoped intranet content (SharePoint pages today; pluggable providers)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from crisai.config import load_settings
from crisai.intranet.config import IntranetSettings, load_intranet_settings
from crisai.intranet.providers.sharepoint_pages import SharePointPagesProvider
from crisai.intranet.providers.wiki import WikiProvider
from crisai.logging_utils import append_json_log_line, configure_mcp_framework_logging

load_dotenv()

mcp = FastMCP("crisai-intranet")

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
ROOT.mkdir(parents=True, exist_ok=True)

LOG_FILE = load_settings().log_dir / "intranet_mcp.log"
SETTINGS = load_settings()


def log_event(message: str) -> None:
    append_json_log_line(
        LOG_FILE,
        message,
        logger_name="crisai.mcp.intranet",
        service_component="intranet_mcp",
    )


def _configure_mcp_logging() -> None:
    configure_mcp_framework_logging(LOG_FILE, service_component="intranet_mcp")


def _build_provider(cfg: IntranetSettings, workspace_root: Path) -> Any:
    """Instantiate the provider for the configured intranet backend.

    The provider is responsible for configuring its own token cache so that
    each backend (SharePoint pages, wiki, …) manages credentials independently
    of other MCP servers sharing the same workspace.
    """
    if cfg.provider == "wiki":
        return WikiProvider()
    if cfg.provider == "sharepoint_pages":
        return SharePointPagesProvider(settings=cfg, workspace_root=workspace_root)
    raise RuntimeError(
        f"Unknown intranet.provider {cfg.provider!r} in registry/intranet.yaml "
        "(expected sharepoint_pages or wiki)."
    )


INTRANET_CFG = load_intranet_settings(SETTINGS.registry_dir)
PROVIDER = _build_provider(INTRANET_CFG, ROOT)

_configure_mcp_logging()


@mcp.tool()
def intranet_login() -> str:
    """Force interactive login for the intranet provider.

    The authentication mechanism depends on the configured provider
    (device code flow in WSL2, browser redirect otherwise for SharePoint).
    Token cache is isolated from other MCP servers.
    """
    log_event("intranet_login")
    return PROVIDER.login()


@mcp.tool()
def intranet_auth_status() -> dict[str, Any]:
    """Return intranet provider authentication status without prompting."""
    log_event("intranet_auth_status")
    return PROVIDER.auth_status()


@mcp.tool()
def intranet_search(query: str, max_hits: int = 40) -> list[dict[str, Any]]:
    """Search configured intranet sites (SharePoint site pages). Not a general web search.

    Returns graph_site_id and graph_page_id for use with intranet_fetch.
    If the token has expired and cannot be silently refreshed, an interactive
    re-authentication flow is triggered automatically (device code in WSL2,
    browser redirect otherwise).
    """
    cap = max(1, min(max_hits, 50))
    log_event(f"intranet_search query={query!r} max_hits={cap}")
    try:
        hits = PROVIDER.search(query, max_hits=cap)
    except Exception as exc:
        log_event(f"intranet_search error={exc!r}")
        raise
    titles = [str(h.get("title") or "")[:80] for h in hits[:5]]
    log_event(f"intranet_search done hits={len(hits)} sample_titles={titles!r}")
    return hits


@mcp.tool()
def intranet_fetch(graph_site_id: str, graph_page_id: str) -> str:
    """Fetch normalized text for a SharePoint site page from intranet_search results.

    If the token has expired and cannot be silently refreshed, an interactive
    re-authentication flow is triggered automatically.
    """
    log_event(f"intranet_fetch site={graph_site_id!r} page={graph_page_id!r}")
    max_chars = max(4_000, INTRANET_CFG.max_fetch_chars)
    try:
        text = PROVIDER.fetch(graph_site_id, graph_page_id, max_chars=max_chars)
    except Exception as exc:
        log_event(f"intranet_fetch error={exc!r}")
        raise
    log_event(f"intranet_fetch done chars={len(text)} max_chars={max_chars}")
    return text


@mcp.tool()
def intranet_list_page_links(graph_site_id: str, graph_page_id: str) -> list[dict[str, Any]]:
    """List same-host Site Pages URLs linked from a page (use after intranet_fetch on hub/catalog pages).

    Each result always contains web_url and open_url.  When the page catalogue
    cache is warm, results are also enriched with title, graph_site_id,
    graph_page_id, and site_label — so you can call intranet_fetch directly on
    each entry without a separate search step to resolve the IDs.

    If the token has expired and cannot be silently refreshed, an interactive
    re-authentication flow is triggered automatically.
    """
    log_event(f"intranet_list_page_links site={graph_site_id!r} page={graph_page_id!r}")
    try:
        links = PROVIDER.list_page_links(graph_site_id, graph_page_id)
    except Exception as exc:
        log_event(f"intranet_list_page_links error={exc!r}")
        raise
    log_event(f"intranet_list_page_links done count={len(links)}")
    return links


@mcp.tool()
def intranet_list_all_pages() -> list[dict[str, Any]]:
    """Return the complete page catalogue for all configured intranet sites.

    Use this tool for comprehensive, deterministic discovery — it returns every
    available page regardless of keyword matching, so pages that intranet_search
    might miss (e.g. hub pages reachable only via navigation) are always included.

    Results are served from an on-disk cache (workspace/.cache/intranet_pages_cache.json)
    valid for INTRANET_PAGE_CACHE_TTL_HOURS (default 4 h, set in .env or registry/intranet.yaml).
    A cache miss triggers a full paginated Graph scan across all configured sites.

    Each entry contains: title, web_url, graph_site_id, graph_page_id, site_label.
    Use graph_site_id + graph_page_id with intranet_fetch to retrieve page content.
    """
    log_event("intranet_list_all_pages")
    try:
        pages = PROVIDER.list_all_pages()
    except Exception as exc:
        log_event(f"intranet_list_all_pages error={exc!r}")
        raise
    log_event(f"intranet_list_all_pages done count={len(pages)}")
    return pages


if __name__ == "__main__":
    mcp.run()
