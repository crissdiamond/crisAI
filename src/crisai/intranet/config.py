"""Load and validate ``registry/intranet.yaml``."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class SharePointSiteEntry:
    """One SharePoint site root (pages are listed under this site)."""

    label: str
    graph_site_id: str
    web_url: str


@dataclass(slots=True)
class IntranetSettings:
    """Normalized intranet configuration."""

    provider: str
    allow_hosts: list[str]
    max_fetch_chars: int
    graph_timeout_seconds: int
    sharepoint_sites: list[SharePointSiteEntry] = field(default_factory=list)
    raw_sharepoint_sites: list[dict[str, Any]] = field(default_factory=list)
    # TTL for the intranet_list_all_pages local disk cache (in hours).
    # Override with INTRANET_PAGE_CACHE_TTL_HOURS env variable.
    page_cache_ttl_hours: int = 4
    # Absolute path to search_synonyms.yaml; None disables synonym expansion.
    synonyms_path: Path | None = None


def load_intranet_settings(registry_dir: Path) -> IntranetSettings:
    """Parse intranet.yaml and return settings (sites are not resolved to Graph ids here)."""
    path = registry_dir / "intranet.yaml"
    if not path.exists():
        return IntranetSettings(
            provider="sharepoint_pages",
            allow_hosts=[],
            max_fetch_chars=120_000,
            graph_timeout_seconds=90,
            sharepoint_sites=[],
            raw_sharepoint_sites=[],
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    block = data.get("intranet") or {}
    limits = block.get("limits") or {}
    sp = block.get("sharepoint_pages") or {}
    sites_raw = list(sp.get("sites") or [])
    # Env var overrides YAML; YAML overrides hard-coded default of 4 hours.
    _ttl_env = os.getenv("INTRANET_PAGE_CACHE_TTL_HOURS")
    page_cache_ttl_hours = int(_ttl_env) if _ttl_env and _ttl_env.strip().isdigit() else int(limits.get("page_cache_ttl_hours") or 4)

    # Resolve synonyms file: explicit YAML key overrides the default location.
    synonyms_filename = str(block.get("search_synonyms_file") or "search_synonyms.yaml").strip()
    synonyms_path: Path | None = registry_dir / synonyms_filename
    if not synonyms_path.exists():
        synonyms_path = None

    return IntranetSettings(
        provider=str(block.get("provider") or "sharepoint_pages").strip(),
        allow_hosts=[str(h).strip().lower() for h in (block.get("allow_hosts") or []) if str(h).strip()],
        max_fetch_chars=int(limits.get("max_fetch_chars") or 120_000),
        graph_timeout_seconds=int(limits.get("graph_timeout_seconds") or 90),
        sharepoint_sites=[],
        raw_sharepoint_sites=sites_raw,
        page_cache_ttl_hours=page_cache_ttl_hours,
        synonyms_path=synonyms_path,
    )
