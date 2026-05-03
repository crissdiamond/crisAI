"""Placeholder wiki provider for multi-institution configuration."""

from __future__ import annotations

from typing import Any


class WikiProvider:
    """Reserved adapter for wiki-style intranets (not implemented yet)."""

    def login(self) -> str:
        raise NotImplementedError(
            "intranet.provider is set to 'wiki', but the wiki adapter is not implemented yet."
        )

    def auth_status(self) -> dict[str, Any]:
        raise NotImplementedError(
            "intranet.provider is set to 'wiki', but the wiki adapter is not implemented yet."
        )

    def search(self, query: str, max_hits: int) -> list[dict[str, Any]]:
        raise RuntimeError(
            "intranet.provider is set to 'wiki', but the wiki adapter is not implemented yet. "
            "Use provider: sharepoint_pages or contribute a wiki backend."
        )

    def fetch(self, graph_site_id: str, graph_page_id: str, max_chars: int) -> str:
        raise RuntimeError(
            "intranet.provider is set to 'wiki', but the wiki adapter is not implemented yet."
        )

    def list_page_links(self, graph_site_id: str, graph_page_id: str) -> list[dict[str, Any]]:
        raise RuntimeError(
            "intranet.provider is set to 'wiki', but list_page_links is not implemented for wiki."
        )

    def list_all_pages(self) -> list[dict[str, Any]]:
        raise RuntimeError(
            "intranet.provider is set to 'wiki', but list_all_pages is not implemented for wiki."
        )
