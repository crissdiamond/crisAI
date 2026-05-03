"""Provider protocol for intranet MCP tools."""

from __future__ import annotations

from typing import Any, Protocol


class IntranetProvider(Protocol):
    """Search, fetch, and authenticate against an intranet content source.

    Concrete providers (e.g. SharePoint site pages, wiki adapters) implement
    this protocol so that the intranet MCP server remains decoupled from any
    specific authentication mechanism or backend technology.
    """

    def login(self) -> str:
        """Trigger interactive authentication and return a status string.

        Implementations should open a browser or device-code flow as
        appropriate for the provider's auth mechanism.  Called by the
        ``intranet_login`` MCP tool.
        """

    def auth_status(self) -> dict[str, Any]:
        """Return current authentication status without triggering a login.

        Called by the ``intranet_auth_status`` MCP tool.  Must not open a
        browser or block on user interaction.
        """

    def search(self, query: str, max_hits: int) -> list[dict[str, Any]]:
        """Return hit dicts with keys including graph_site_id, graph_page_id, title, web_url, snippet."""

    def fetch(self, graph_site_id: str, graph_page_id: str, max_chars: int) -> str:
        """Return normalized text for the page."""

    def list_page_links(self, graph_site_id: str, graph_page_id: str) -> list[dict[str, Any]]:
        """Return same-host Site Pages URLs linked from a hub or catalogue page."""

    def list_all_pages(self, query: str = "") -> list[dict[str, Any]]:
        """Return the complete page catalogue for all configured sites.

        When ``query`` is non-empty, only pages whose title or ``web_url``
        slug contain **any** token from the query are returned (case-insensitive
        substring match, no scoring cap).  Pass an empty string to return the
        full unfiltered catalogue.

        Results should be cached by the implementation to avoid repeated Graph
        API calls.  Each entry must contain at minimum: ``title``, ``web_url``,
        ``graph_site_id``, ``graph_page_id``, and ``site_label``.
        """
