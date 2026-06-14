"""Orchestrate confirmed-source materialisation (CRISAI-ADR-015 Phase 2b).

Ties the deterministic fetch (``orchestration.source_fetch``) to the workspace
evidence cache (``workspace.source_cache``): for a confirmed source, fetch its raw
bytes once, build an extracted sidecar, and cache both keyed by source-id +
revision — reusing an existing cache entry when the revision already matches so a
source is fetched at most once per revision.

This module is deterministic and side-effect-scoped to the per-task cache; the
fetch is injected so it is fully unit-testable without a live MCP server. Wiring
this into the retrieval checkpoint flow is a separate slice.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from crisai import registry
from crisai.orchestration import source_fetch
from crisai.workspace import source_cache


@dataclass(frozen=True, slots=True)
class MaterialisationOutcome:
    """Result of attempting to materialise one confirmed source."""

    source_id: str
    record: source_cache.MaterialisedSource | None
    cache_hit: bool
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.record is not None


async def materialise_source(
    *,
    source_id: str,
    read_handle: str,
    server_spec: registry.ServerSpec,
    runtime: Any,
    task_state_dir: Path,
    workspace_root: Path,
    known_revision: str = "",
    materialised_at: str = "",
    env_overrides: dict[str, str] | None = None,
) -> MaterialisationOutcome:
    """Materialise one confirmed source into the per-task evidence cache.

    Reuses an existing cache entry when ``known_revision`` already matches (no
    fetch). Otherwise fetches the raw bytes once, and — if that revision is in
    fact already cached — reuses it rather than re-writing. A fetch failure is
    returned as an outcome error, never raised, so one bad source does not abort
    materialising the others.
    """
    if not source_id.strip() or not read_handle.strip():
        return MaterialisationOutcome(
            source_id=source_id, record=None, cache_hit=False,
            error="missing source_id or read_handle",
        )

    # Cheap path: a known provider revision already in the cache needs no fetch.
    if known_revision.strip():
        cached = source_cache.lookup_materialised(
            task_state_dir=task_state_dir, source_id=source_id, revision=known_revision
        )
        if cached is not None:
            return MaterialisationOutcome(source_id=source_id, record=cached, cache_hit=True)

    try:
        fetched = await source_fetch.fetch_source_bytes(
            server_spec, read_handle, runtime=runtime, env_overrides=env_overrides
        )
    except source_fetch.SourceFetchError as exc:
        return MaterialisationOutcome(source_id=source_id, record=None, cache_hit=False, error=str(exc))

    revision = fetched.revision or "unknown"

    # The fetch revealed the revision; if it is already cached, reuse it.
    existing = source_cache.lookup_materialised(
        task_state_dir=task_state_dir, source_id=source_id, revision=revision
    )
    if existing is not None:
        return MaterialisationOutcome(source_id=source_id, record=existing, cache_hit=True)

    record = source_cache.materialise_source(
        task_state_dir=task_state_dir,
        workspace_root=workspace_root,
        source_id=source_id,
        revision=revision,
        raw_bytes=fetched.raw_bytes,
        suffix=fetched.suffix,
        extracted=_extract_sidecar(fetched),
        title=fetched.name,
        source_family=_first_source_family(server_spec),
        materialised_at=materialised_at,
    )
    # Bound the cache: keep only the current revision of this source.
    source_cache.prune_stale_revisions(
        task_state_dir=task_state_dir, source_id=source_id, keep_revision=record.revision
    )
    return MaterialisationOutcome(source_id=source_id, record=record, cache_hit=False)


def _extract_sidecar(fetched: source_fetch.FetchedSource) -> dict[str, Any]:
    """Build the extracted sidecar for a fetched source (best-effort)."""
    if fetched.suffix == ".pptx":
        try:
            return source_cache.extract_pptx_evidence(fetched.raw_bytes)
        except Exception:  # noqa: BLE001 - extraction is best-effort; the raw file is still cached
            return {"format": "pptx", "extraction_error": True}
    return {"format": (fetched.suffix.lstrip(".") or "binary"), "extraction": "raw_only"}


def _first_source_family(server_spec: registry.ServerSpec) -> str:
    cap = getattr(server_spec, "capabilities", None)
    families = getattr(cap, "source_families", ()) if cap is not None else ()
    return families[0] if families else ""
