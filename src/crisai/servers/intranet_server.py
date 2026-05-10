"""MCP server for scoped intranet content (SharePoint pages today; pluggable providers)."""

from __future__ import annotations

import importlib
import inspect
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
    if cfg.provider == "custom":
        return _build_custom_provider(cfg, workspace_root)
    if cfg.provider == "sharepoint_pages":
        return SharePointPagesProvider(settings=cfg, workspace_root=workspace_root)
    raise RuntimeError(
        f"Unknown intranet.provider {cfg.provider!r} in registry/intranet.yaml "
        "(expected sharepoint_pages, wiki, or custom)."
    )


def _build_custom_provider(cfg: IntranetSettings, workspace_root: Path) -> Any:
    """Load a user-supplied intranet provider class from ``module:Class``."""
    if not cfg.custom_class_path:
        raise RuntimeError("intranet.provider is 'custom' but intranet.custom.class_path is empty.")
    if ":" not in cfg.custom_class_path:
        raise RuntimeError("intranet.custom.class_path must use 'module:ClassName' format.")
    module_name, class_name = cfg.custom_class_path.split(":", 1)
    provider_cls = getattr(importlib.import_module(module_name), class_name)
    signature = inspect.signature(provider_cls)
    accepts_kwargs = any(
        param.kind is inspect.Parameter.VAR_KEYWORD
        for param in signature.parameters.values()
    )
    kwargs: dict[str, Any] = {}
    if accepts_kwargs or "settings" in signature.parameters:
        kwargs["settings"] = cfg.custom_settings
    if accepts_kwargs or "workspace_root" in signature.parameters:
        kwargs["workspace_root"] = workspace_root
    if kwargs:
        return provider_cls(**kwargs)
    return provider_cls()


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
    """Legacy alias for intranet_search_pages.

    SharePoint results still include graph_site_id and graph_page_id for
    compatibility. New callers should use content_id with intranet_fetch_page.
    """
    return intranet_search_pages(query=query, max_hits=max_hits)


@mcp.tool()
def intranet_search_pages(query: str, max_hits: int = 40) -> list[dict[str, Any]]:
    """Search configured intranet pages. Not a general web search.

    Returns provider-neutral content_id values for use with intranet_fetch_page.
    Provider-specific metadata may be included for diagnostics or legacy
    compatibility, but agents should treat content_id as opaque.
    """
    cap = max(1, min(max_hits, 50))
    log_event(f"intranet_search_pages query={query!r} max_hits={cap}")
    try:
        hits = PROVIDER.search(query, max_hits=cap)
    except Exception as exc:
        log_event(f"intranet_search_pages error={exc!r}")
        raise
    titles = [str(h.get("title") or "")[:80] for h in hits[:5]]
    log_event(f"intranet_search_pages done hits={len(hits)} sample_titles={titles!r}")
    return hits


@mcp.tool()
def intranet_fetch(graph_site_id: str, graph_page_id: str) -> str:
    """Legacy SharePoint fetch by Graph ids.

    New callers should use intranet_fetch_page(content_id). This tool is only
    available for the sharepoint_pages provider.
    """
    log_event(f"intranet_fetch site={graph_site_id!r} page={graph_page_id!r}")
    max_chars = max(4_000, INTRANET_CFG.max_fetch_chars)
    try:
        if INTRANET_CFG.provider != "sharepoint_pages" or not hasattr(PROVIDER, "fetch_graph_page"):
            raise RuntimeError(
                "Legacy graph id tools require intranet.provider: sharepoint_pages. "
                "Use intranet_fetch_page(content_id) for provider-neutral intranet content."
            )
        text = PROVIDER.fetch_graph_page(graph_site_id, graph_page_id, max_chars=max_chars)
    except Exception as exc:
        log_event(f"intranet_fetch error={exc!r}")
        raise
    log_event(f"intranet_fetch done chars={len(text)} max_chars={max_chars}")
    return text


@mcp.tool()
def intranet_fetch_page(content_id: str) -> str:
    """Fetch normalized text for a provider-neutral intranet page content_id."""
    log_event(f"intranet_fetch_page content_id={content_id!r}")
    max_chars = max(4_000, INTRANET_CFG.max_fetch_chars)
    try:
        text = PROVIDER.fetch(content_id, max_chars=max_chars)
    except Exception as exc:
        log_event(f"intranet_fetch_page error={exc!r}")
        raise
    log_event(f"intranet_fetch_page done chars={len(text)} max_chars={max_chars}")
    return text


@mcp.tool()
def intranet_list_page_links(graph_site_id: str, graph_page_id: str) -> list[dict[str, Any]]:
    """Legacy SharePoint page-link listing by Graph ids.

    New callers should use intranet_list_page_links_by_id(content_id). This
    tool is only available for the sharepoint_pages provider.
    """
    log_event(f"intranet_list_page_links site={graph_site_id!r} page={graph_page_id!r}")
    try:
        if INTRANET_CFG.provider != "sharepoint_pages" or not hasattr(PROVIDER, "list_page_links"):
            raise RuntimeError(
                "Legacy graph id tools require intranet.provider: sharepoint_pages. "
                "Use intranet_list_page_links_by_id(content_id) for provider-neutral intranet content."
            )
        links = PROVIDER.list_page_links(graph_site_id, graph_page_id)
    except Exception as exc:
        log_event(f"intranet_list_page_links error={exc!r}")
        raise
    log_event(f"intranet_list_page_links done count={len(links)}")
    return links


@mcp.tool()
def intranet_list_page_links_by_id(content_id: str) -> list[dict[str, Any]]:
    """List intranet page links discovered from a page identified by content_id."""
    log_event(f"intranet_list_page_links_by_id content_id={content_id!r}")
    try:
        links = PROVIDER.list_links(content_id)
    except Exception as exc:
        log_event(f"intranet_list_page_links_by_id error={exc!r}")
        raise
    log_event(f"intranet_list_page_links_by_id done count={len(links)}")
    return links


@mcp.tool()
def intranet_list_all_pages(query: str = "") -> list[dict[str, Any]]:
    """Legacy alias for intranet_list_pages."""
    return intranet_list_pages(query=query)


@mcp.tool()
def intranet_list_pages(query: str = "") -> list[dict[str, Any]]:
    """Return the page catalogue for all configured intranet sources, optionally filtered.

    Use this for comprehensive enumeration requests where search result caps
    are not appropriate. Results contain provider-neutral content_id values for
    intranet_fetch_page.
    """
    log_event(f"intranet_list_pages query={query!r}")
    try:
        pages = PROVIDER.list_all(query=query)
    except Exception as exc:
        log_event(f"intranet_list_pages error={exc!r}")
        raise
    log_event(f"intranet_list_pages done count={len(pages)}")
    return pages


if __name__ == "__main__":
    mcp.run()
