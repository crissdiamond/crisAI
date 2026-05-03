"""SharePoint modern site pages via Microsoft Graph (delegated)."""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from crisai import ms_graph
from crisai.intranet.config import IntranetSettings, SharePointSiteEntry

# Site page list pagination (Graph returns @odata.nextLink; deep pages are often past the first batch).
_PAGE_LIST_BATCH = 100
_MAX_SITE_PAGES_TO_SCAN = 500


def _hrefs_from_html_fragment(html: str) -> list[str]:
    out: list[str] = []
    out += re.findall(r'href\s*=\s*"([^"]+)"', html, flags=re.IGNORECASE)
    out += re.findall(r"href\s*=\s*'([^']+)'", html, flags=re.IGNORECASE)
    return [h.strip() for h in out if h.strip()]


# Absolute SharePoint Site Pages URLs embedded in web part JSON (Quick Links, embeds, etc.).
_SP_SITEPAGE_URL_RE = re.compile(
    r"https://[a-z0-9.-]+\.sharepoint\.com(?:/[^?\s\"'<>]*)?/SitePages/[^?\s\"'<>]+\.aspx",
    re.IGNORECASE,
)


def _sitepage_urls_in_object(obj: Any, *, max_urls: int = 120, max_nodes: int = 500) -> list[str]:
    """Walk web part structures and collect Site Pages URLs from any string field."""
    found: list[str] = []
    seen_urls: set[str] = set()
    nodes = [0]

    def walk(o: Any) -> None:
        if len(found) >= max_urls or nodes[0] >= max_nodes:
            return
        nodes[0] += 1
        if isinstance(o, str):
            for m in _SP_SITEPAGE_URL_RE.finditer(o):
                u = m.group(0).rstrip(").,;]")
                if u not in seen_urls:
                    seen_urls.add(u)
                    found.append(u)
                    if len(found) >= max_urls:
                        return
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return found


def _strip_html(html: str) -> str:
    """Remove tags and collapse whitespace for model consumption."""
    text = re.sub(r"(?s)<script[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"(?s)<style[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _canvas_to_text(canvas: dict[str, Any] | None) -> str:
    if not canvas:
        return ""
    parts: list[str] = []
    for section in canvas.get("horizontalSections") or []:
        for col in section.get("columns") or []:
            for wp in col.get("webparts") or []:
                inner = wp.get("innerHtml")
                if isinstance(inner, str) and inner.strip():
                    parts.append(_strip_html(inner))
                inner_text = wp.get("innerText")
                if isinstance(inner_text, str) and inner_text.strip():
                    parts.append(inner_text.strip())
    return "\n\n".join(parts)


def _page_text_from_graph(page: dict[str, Any]) -> str:
    chunks: list[str] = []
    title = page.get("title")
    if title:
        chunks.append(str(title))
    desc = page.get("description")
    if desc:
        chunks.append(_strip_html(str(desc)))
    canvas = page.get("canvasLayout")
    if isinstance(canvas, dict):
        body = _canvas_to_text(canvas)
        if body:
            chunks.append(body)
    return "\n\n".join(chunks).strip()


def _host_of(url: str) -> str | None:
    try:
        return (urlparse(url).hostname or "").lower() or None
    except ValueError:
        return None


def _collect_hrefs_from_canvas(canvas: dict[str, Any] | None) -> list[str]:
    """Extract link targets from canvas: ``href`` attributes plus embedded Site Pages URLs in web part data."""
    if not canvas:
        return []
    hrefs: list[str] = []
    for section in canvas.get("horizontalSections") or []:
        for col in section.get("columns") or []:
            for wp in col.get("webparts") or []:
                if not isinstance(wp, dict):
                    continue
                inner = wp.get("innerHtml")
                if isinstance(inner, str):
                    hrefs.extend(_hrefs_from_html_fragment(inner))
                    hrefs.extend(_sitepage_urls_in_object(inner, max_urls=30))
                hrefs.extend(_sitepage_urls_in_object(wp, max_urls=40))
    return hrefs


def _fetch_site_pages_paginated(site_id: str, timeout: int) -> list[dict[str, Any]]:
    """Collect up to ``_MAX_SITE_PAGES_TO_SCAN`` site pages using Graph nextLink."""
    accumulated: list[dict[str, Any]] = []
    data = ms_graph.graph_get(
        f"/sites/{site_id}/pages/microsoft.graph.sitePage",
        params={"$top": _PAGE_LIST_BATCH},
        timeout=timeout,
    )
    accumulated.extend(data.get("value") or [])
    rounds = 0
    while len(accumulated) < _MAX_SITE_PAGES_TO_SCAN and rounds < 25:
        next_link = data.get("@odata.nextLink")
        if not next_link:
            break
        rounds += 1
        data = ms_graph.graph_get_url(str(next_link), timeout=timeout)
        accumulated.extend(data.get("value") or [])
    return accumulated[:_MAX_SITE_PAGES_TO_SCAN]


def resolve_site_entries(
    settings: IntranetSettings,
) -> list[SharePointSiteEntry]:
    """Resolve YAML site entries to Graph site ids using /sites/... lookups."""
    timeout = max(30, settings.graph_timeout_seconds)
    resolved: list[SharePointSiteEntry] = []
    for raw in settings.raw_sharepoint_sites:
        label = str(raw.get("label") or "site").strip() or "site"
        graph_site_id = raw.get("graph_site_id")
        site_path = raw.get("site_path")
        if graph_site_id:
            path = f"/sites/{graph_site_id}"
        elif site_path:
            path = f"/sites/{site_path}"
        else:
            raise ValueError(
                f"intranet.sharepoint_pages.sites entry {label!r} requires "
                "'graph_site_id' or 'site_path' (see registry/intranet.yaml)."
            )
        site = ms_graph.graph_get(path, timeout=timeout)
        sid = site.get("id")
        if not sid:
            raise RuntimeError(f"Graph site response missing id for {label!r}")
        web_url = str(site.get("webUrl") or "")
        resolved.append(SharePointSiteEntry(label=label, graph_site_id=str(sid), web_url=web_url))
    return resolved


def effective_allow_hosts(settings: IntranetSettings, resolved: list[SharePointSiteEntry]) -> set[str]:
    """Hosts permitted for page webUrl checks."""
    if settings.allow_hosts:
        return set(settings.allow_hosts)
    derived: set[str] = set()
    for s in resolved:
        h = _host_of(s.web_url)
        if h:
            derived.add(h)
    return derived


class SharePointPagesProvider:
    """List and fetch SharePoint site pages within configured sites.

    This provider owns its own Microsoft Graph token cache so that it remains
    independent of other MCP servers (e.g. sharepoint_docs) that may share the
    same workspace.  Pass ``workspace_root`` to isolate the cache under
    ``workspace_root/.auth/intranet_token_cache.json``.
    """

    def __init__(
        self,
        *,
        settings: IntranetSettings,
        sites: list[SharePointSiteEntry] | None = None,
        allowed_hosts: set[str] | None = None,
        workspace_root: "Path | None" = None,
    ) -> None:
        if workspace_root is not None:
            # Configure the intranet-specific Graph token cache before any API
            # calls so this provider's credentials are isolated from other
            # MCP servers that also use ms_graph.
            ms_graph.configure_workspace(workspace_root, namespace="intranet")
        self._settings = settings
        self._workspace_root = workspace_root
        # Site resolution is deferred to the first tool call (_ensure_sites).
        # Resolving here would block on interactive auth during server startup,
        # preventing the MCP server from responding to protocol handshakes.
        self._sites: list[SharePointSiteEntry] | None = sites
        self._allowed_hosts: set[str] | None = allowed_hosts
        self._timeout = max(30, settings.graph_timeout_seconds)

    def _ensure_sites(self) -> None:
        """Resolve site entries on first use (lazy auth)."""
        if self._sites is not None:
            return
        self._sites = (
            resolve_site_entries(self._settings)
            if self._settings.raw_sharepoint_sites
            else []
        )
        self._allowed_hosts = effective_allow_hosts(self._settings, self._sites)

    # ------------------------------------------------------------------
    # Auth interface (satisfies IntranetProvider protocol)
    # ------------------------------------------------------------------

    def login(self) -> str:
        """Trigger interactive Microsoft Graph login for the intranet token cache."""
        ms_graph.acquire_token(force_interactive=True)
        info = ms_graph.read_token_info()
        return (
            f"Intranet (SharePoint pages) login successful. "
            f"Account={info.get('account')} Scopes={info.get('scope')}"
        )

    def auth_status(self) -> dict[str, Any]:
        """Return Microsoft Graph delegated auth status without prompting."""
        return ms_graph.delegated_auth_status()

    def _ensure_page_host_allowed(self, web_url: str) -> None:
        self._ensure_sites()
        host = _host_of(web_url)
        if not host:
            raise RuntimeError("Page has no webUrl host; refusing fetch.")
        if self._allowed_hosts and host not in self._allowed_hosts:
            raise RuntimeError(
                f"Page host {host!r} is not in the intranet allow list. "
                "Update registry/intranet.yaml allow_hosts or site configuration."
            )

    def _list_pages_for_site(self, site_id: str, query: str, per_site_cap: int) -> list[dict[str, Any]]:
        """List site pages; match query against titles with OData when possible, then token fallback.

        Graph ``contains(title,'integration pattern')`` requires that **exact** substring in the
        title. Real titles often have only ``Integration`` or ``Patterns``, so an empty OData
        result falls back to a capped unfiltered list and **any-token** matching on
        title, file name, and description.
        """
        q = (query or "").strip().lower()
        fetch_limit = min(max(per_site_cap * 4, 20), 100)

        if q:
            safe = q.replace("'", "''")
            try:
                data = ms_graph.graph_get(
                    f"/sites/{site_id}/pages/microsoft.graph.sitePage",
                    params={"$top": per_site_cap, "$filter": f"contains(title,'{safe}')"},
                    timeout=self._timeout,
                )
                odata_hits = list(data.get("value") or [])[:per_site_cap]
                if odata_hits:
                    return odata_hits
            except RuntimeError as exc:
                # Some tenants reject OData filters on sitePage; fall back to a capped list.
                if "400" not in str(exc) and "501" not in str(exc):
                    raise

        if not q:
            data = ms_graph.graph_get(
                f"/sites/{site_id}/pages/microsoft.graph.sitePage",
                params={"$top": fetch_limit},
                timeout=self._timeout,
            )
            pages = list(data.get("value") or [])
            return pages[:per_site_cap]

        # Paginate: leaf pages (for example integration-patterns.aspx) are often beyond the first batch.
        pages = _fetch_site_pages_paginated(site_id, self._timeout)

        tokens = [t for t in re.split(r"\s+", q) if len(t) >= 2]
        if not tokens:
            tokens = [q]

        def _blob(page: dict[str, Any]) -> str:
            return (
                str(page.get("title") or "")
                + " "
                + str(page.get("name") or "")
                + " "
                + str(page.get("description") or "")
                + " "
                + str(page.get("webUrl") or "")
            ).lower()

        scored: list[tuple[int, dict[str, Any]]] = []
        for page in pages:
            blob = _blob(page)
            score = sum(1 for token in tokens if token in blob)
            if score:
                scored.append((score, page))
        scored.sort(key=lambda item: -item[0])
        return [page for _, page in scored][:per_site_cap]

    def search(self, query: str, max_hits: int) -> list[dict[str, Any]]:
        self._ensure_sites()
        if not self._sites:
            return []
        per_site = max(3, min(25, max(1, max_hits // max(1, len(self._sites)))))
        hits: list[dict[str, Any]] = []
        for site in self._sites:
            if len(hits) >= max_hits:
                break
            try:
                pages = self._list_pages_for_site(site.graph_site_id, query, per_site_cap=per_site)
            except RuntimeError:
                continue
            for page in pages:
                if len(hits) >= max_hits:
                    break
                web_url = str(page.get("webUrl") or "")
                host = _host_of(web_url)
                if self._allowed_hosts and host not in self._allowed_hosts:
                    continue
                title = str(page.get("title") or page.get("name") or "")
                desc = str(page.get("description") or "")
                snippet = (desc or title)[:280]
                hits.append(
                    {
                        "site_label": site.label,
                        "graph_site_id": site.graph_site_id,
                        "graph_page_id": str(page.get("id") or ""),
                        "title": title,
                        "web_url": web_url,
                        "open_url": web_url,
                        "snippet": snippet,
                    }
                )
        return hits

    def fetch(self, graph_site_id: str, graph_page_id: str, max_chars: int) -> str:
        if not graph_site_id or not graph_page_id:
            raise ValueError("graph_site_id and graph_page_id are required.")
        self._ensure_sites()
        allowed_site_ids = {s.graph_site_id for s in self._sites}  # type: ignore[arg-type]
        if graph_site_id not in allowed_site_ids:
            raise RuntimeError(
                "graph_site_id is not one of the configured intranet sites. "
                "Use intranet_search hits only."
            )
        page = ms_graph.graph_get(
            f"/sites/{graph_site_id}/pages/{graph_page_id}/microsoft.graph.sitePage",
            params={"$expand": "canvasLayout"},
            timeout=self._timeout,
        )
        web_url = str(page.get("webUrl") or "")
        self._ensure_page_host_allowed(web_url)
        text = _page_text_from_graph(page)
        if not text:
            text = f"[No extractable text for page {graph_page_id!r}; open_url={web_url}]"
        if len(text) > max_chars:
            text = text[: max_chars - 20] + "\n...[truncated]"
        return text

    def list_page_links(self, graph_site_id: str, graph_page_id: str) -> list[dict[str, Any]]:
        """Return same-site Site Pages URLs linked from a page's web-part HTML (hub → child navigation)."""
        if not graph_site_id or not graph_page_id:
            raise ValueError("graph_site_id and graph_page_id are required.")
        self._ensure_sites()
        allowed_site_ids = {s.graph_site_id for s in self._sites}  # type: ignore[arg-type]
        if graph_site_id not in allowed_site_ids:
            raise RuntimeError(
                "graph_site_id is not one of the configured intranet sites. "
                "Use intranet_search hits only."
            )
        page = ms_graph.graph_get(
            f"/sites/{graph_site_id}/pages/{graph_page_id}/microsoft.graph.sitePage",
            params={"$expand": "canvasLayout"},
            timeout=self._timeout,
        )
        web_url = str(page.get("webUrl") or "")
        self._ensure_page_host_allowed(web_url)
        canvas = page.get("canvasLayout")
        raw_hrefs = _collect_hrefs_from_canvas(canvas if isinstance(canvas, dict) else None)
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href in raw_hrefs:
            h = href.strip()
            if not h or h.startswith("#") or h.lower().startswith("javascript:"):
                continue
            absolute = urljoin(web_url, h)
            parsed = urlparse(absolute)
            host = (parsed.hostname or "").lower()
            path_l = (parsed.path or "").lower()
            if self._allowed_hosts and host not in self._allowed_hosts:
                continue
            if "sitepages" not in path_l:
                continue
            norm = absolute.split("?")[0].rstrip("/")
            base_norm = web_url.split("?")[0].rstrip("/")
            if norm == base_norm:
                continue
            if norm not in seen:
                seen.add(norm)
                results.append({"web_url": norm, "open_url": norm})
        return results

    # ------------------------------------------------------------------
    # Full-catalogue listing with on-disk cache
    # ------------------------------------------------------------------

    def _page_cache_path(self) -> Path | None:
        """Return the path for the on-disk page catalogue cache, or None if no workspace_root."""
        if self._workspace_root is None:
            return None
        return self._workspace_root / ".cache" / "intranet_pages_cache.json"

    def _load_cached_pages(self) -> list[dict[str, Any]] | None:
        """Return cached pages if they exist and are within the configured TTL, else None."""
        path = self._page_cache_path()
        if path is None or not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw_ts = data.get("fetched_at", "")
            fetched_at = datetime.datetime.fromisoformat(raw_ts)
            # Ensure comparison is timezone-aware on both sides.
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            age_hours = (now - fetched_at).total_seconds() / 3600
            ttl = self._settings.page_cache_ttl_hours
            if age_hours <= ttl:
                return list(data.get("pages") or [])
        except (KeyError, ValueError, OSError):
            pass
        return None

    def _save_page_cache(self, pages: list[dict[str, Any]]) -> None:
        """Persist page catalogue to disk; silently ignores write errors."""
        path = self._page_cache_path()
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "ttl_hours": self._settings.page_cache_ttl_hours,
                "pages": pages,
            }
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            pass

    def list_all_pages(self) -> list[dict[str, Any]]:
        """Return the complete page catalogue for all configured sites.

        Results are served from an on-disk cache (``workspace/.cache/intranet_pages_cache.json``)
        when the cache is younger than ``page_cache_ttl_hours`` (default 4 h, configurable via
        ``INTRANET_PAGE_CACHE_TTL_HOURS`` env var or ``registry/intranet.yaml``).  A cache miss
        triggers a full Graph paginated scan.

        Each returned dict has: ``title``, ``web_url``, ``graph_site_id``, ``graph_page_id``,
        ``site_label``.
        """
        self._ensure_sites()

        cached = self._load_cached_pages()
        if cached is not None:
            return cached

        all_pages: list[dict[str, Any]] = []
        for site in self._sites or []:
            raw_pages = _fetch_site_pages_paginated(site.graph_site_id, self._timeout)
            for page in raw_pages:
                all_pages.append(
                    {
                        "title": str(page.get("title") or ""),
                        "web_url": str(page.get("webUrl") or ""),
                        "graph_site_id": site.graph_site_id,
                        "graph_page_id": str(page.get("id") or ""),
                        "site_label": site.label,
                    }
                )

        self._save_page_cache(all_pages)
        return all_pages
