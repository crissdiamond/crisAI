"""Placeholder wiki provider for multi-institution configuration."""

from __future__ import annotations

from typing import Any

_NOT_IMPLEMENTED_MSG = """\
intranet.provider is set to 'wiki', but the wiki adapter is not implemented.

Supported providers:
  - sharepoint_pages  (configure sites in registry/intranet.yaml)
  - custom            (set intranet.custom.class_path to your own adapter)

To build a wiki adapter, implement the IntranetProvider protocol:
  src/crisai/intranet/providers/base.py\
"""


class WikiProvider:
    """Reserved adapter for wiki-style intranets (not implemented yet)."""

    def login(self) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def auth_status(self) -> dict[str, Any]:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def search(self, query: str, max_hits: int) -> list[dict[str, Any]]:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def fetch(self, content_id: str, max_chars: int) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def list_links(self, content_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def list_all(self, query: str = "") -> list[dict[str, Any]]:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def list_page_links(self, graph_site_id: str, graph_page_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def list_all_pages(self, query: str = "") -> list[dict[str, Any]]:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)
