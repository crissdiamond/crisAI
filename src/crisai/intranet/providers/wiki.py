"""Placeholder wiki provider for multi-institution configuration."""

from __future__ import annotations

from typing import Any


class WikiProvider:
    """Reserved adapter for wiki-style intranets (not implemented yet)."""

    def search(self, query: str, max_hits: int) -> list[dict[str, Any]]:
        raise RuntimeError(
            "intranet.provider is set to 'wiki', but the wiki adapter is not implemented yet. "
            "Use provider: sharepoint_pages or contribute a wiki backend."
        )

    def fetch(self, graph_site_id: str, graph_page_id: str, max_chars: int) -> str:
        raise RuntimeError(
            "intranet.provider is set to 'wiki', but the wiki adapter is not implemented yet."
        )
