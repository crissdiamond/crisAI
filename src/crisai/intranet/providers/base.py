"""Provider protocol for intranet MCP tools."""

from __future__ import annotations

from typing import Any, Protocol


class IntranetProvider(Protocol):
    """Search and fetch intranet content using delegated or configured credentials."""

    def search(self, query: str, max_hits: int) -> list[dict[str, Any]]:
        """Return hit dicts with keys including graph_site_id, graph_page_id, title, web_url, snippet."""

    def fetch(self, graph_site_id: str, graph_page_id: str, max_chars: int) -> str:
        """Return normalized text for the page."""
