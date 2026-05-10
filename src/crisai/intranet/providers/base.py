"""Provider protocol and shared models for intranet MCP tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class IntranetPage:
    """Provider-neutral page reference returned by intranet adapters."""

    content_id: str
    provider: str
    title: str
    web_url: str = ""
    open_url: str = ""
    source_label: str = ""
    snippet: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable page reference for MCP responses."""
        payload: dict[str, Any] = {
            "content_id": self.content_id,
            "provider": self.provider,
            "title": self.title,
            "web_url": self.web_url,
            "open_url": self.open_url or self.web_url,
            "source_label": self.source_label,
            "snippet": self.snippet,
            "metadata": dict(self.metadata),
        }
        # Preserve legacy top-level fields for existing SharePoint prompts and tests.
        for key in ("graph_site_id", "graph_page_id", "site_label", "name", "description"):
            if key in self.metadata:
                payload[key] = self.metadata[key]
        return payload


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
        """Return page hits with provider-neutral ``content_id`` references."""

    def fetch(self, content_id: str, max_chars: int) -> str:
        """Return normalized text for the page identified by ``content_id``."""

    def list_links(self, content_id: str) -> list[dict[str, Any]]:
        """Return same-source page links discovered from a hub or catalogue page."""

    def list_all(self, query: str = "") -> list[dict[str, Any]]:
        """Return the complete page catalogue for all configured sources.

        When ``query`` is non-empty, only pages whose title or ``web_url``
        slug contain **any** token from the query are returned (case-insensitive
        substring match, no scoring cap).  Pass an empty string to return the
        full unfiltered catalogue.

        Results should be cached by the implementation when the backend makes
        catalogue enumeration expensive.  Each entry must contain at minimum:
        ``content_id``, ``provider``, ``title``, and ``web_url``.
        """
