"""MCP server for scoped intranet content (SharePoint pages today; pluggable providers)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from crisai.config import load_settings
from crisai import ms_graph
from crisai.intranet.config import IntranetSettings, load_intranet_settings
from crisai.intranet.providers.sharepoint_pages import (
    SharePointPagesProvider,
    effective_allow_hosts,
    resolve_site_entries,
)
from crisai.intranet.providers.wiki import WikiProvider
from crisai.logging_utils import append_json_log_line, configure_mcp_framework_logging

load_dotenv()

mcp = FastMCP("crisai-intranet")

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
ROOT.mkdir(parents=True, exist_ok=True)

LOG_FILE = load_settings().log_dir / "intranet_mcp.log"
SETTINGS = load_settings()
ms_graph.configure_workspace(ROOT)


def log_event(message: str) -> None:
    append_json_log_line(
        LOG_FILE,
        message,
        logger_name="crisai.mcp.intranet",
        service_component="intranet_mcp",
    )


def _configure_mcp_logging() -> None:
    configure_mcp_framework_logging(LOG_FILE, service_component="intranet_mcp")


def _build_provider(cfg: IntranetSettings) -> Any:
    if cfg.provider == "wiki":
        return WikiProvider()
    if cfg.provider == "sharepoint_pages":
        resolved = resolve_site_entries(cfg) if cfg.raw_sharepoint_sites else []
        hosts = effective_allow_hosts(cfg, resolved)
        return SharePointPagesProvider(settings=cfg, sites=resolved, allowed_hosts=hosts)
    raise RuntimeError(
        f"Unknown intranet.provider {cfg.provider!r} in registry/intranet.yaml "
        "(expected sharepoint_pages or wiki)."
    )


INTRANET_CFG = load_intranet_settings(SETTINGS.registry_dir)
PROVIDER = _build_provider(INTRANET_CFG)

_configure_mcp_logging()


@mcp.tool()
def intranet_login() -> str:
    """Force interactive Microsoft login (delegated Graph; same cache as SharePoint tools)."""
    log_event("intranet_login")
    ms_graph.acquire_token(force_interactive=True)
    info = ms_graph.read_token_info()
    return f"Intranet login successful. Account={info.get('account')} Scopes={info.get('scope')}"


@mcp.tool()
def intranet_auth_status() -> dict[str, Any]:
    """Return Microsoft Graph delegated auth status without prompting."""
    log_event("intranet_auth_status")
    return ms_graph.delegated_auth_status()


@mcp.tool()
def intranet_search(query: str, max_hits: int = 20) -> list[dict[str, Any]]:
    """Search configured intranet sites (SharePoint site pages). Not a general web search.

    Returns graph_site_id and graph_page_id for use with intranet_fetch.
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
    """Fetch normalized text for a SharePoint site page from intranet_search results."""
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
    """List same-host Site Pages URLs linked from a page (use after intranet_fetch on hub/catalog pages)."""
    log_event(f"intranet_list_page_links site={graph_site_id!r} page={graph_page_id!r}")
    try:
        links = PROVIDER.list_page_links(graph_site_id, graph_page_id)
    except Exception as exc:
        log_event(f"intranet_list_page_links error={exc!r}")
        raise
    log_event(f"intranet_list_page_links done count={len(links)}")
    return links


if __name__ == "__main__":
    mcp.run()
