"""Per-task workspace evidence cache for materialised sources (CRISAI-ADR-015).

When a source is confirmed, its raw bytes and an extracted sidecar are cached
under the task's ``.crisai/sources/<source-id>/<revision>/`` directory so later
turns read a stable copy instead of re-fetching live, mutable provider state
(locks, renames, permissions, transient failures). The cache is keyed by source
identity **and** provider revision, so a changed upstream revision is a miss and
triggers re-materialisation; stale revisions can be pruned.

This is a bounded evidence cache, not a document management system (a VISION
non-goal): it is scoped per task, addressable only by source identity, and never
a system of record.

This module is the deterministic core: callers pass in already-fetched bytes and
an extracted sidecar, so it has no network or MCP dependency and is fully unit
testable. Wiring the live fetch at the retrieval checkpoint and the read-through
into the retrieval loop is a separate slice.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from crisai import powerpoint

SOURCE_CACHE_DIRNAME = "sources"
_META_NAME = "meta.json"
_EXTRACTED_NAME = "extracted.json"


@dataclass(frozen=True, slots=True)
class MaterialisedSource:
    """A source cached in the per-task workspace evidence store."""

    source_id: str
    revision: str
    title: str = ""
    source_family: str = ""
    source_type: str = ""
    raw_path: str = ""
    extracted_path: str = ""
    byte_size: int = 0
    materialised_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> MaterialisedSource:
        """Build a record from persisted JSON."""
        return cls(
            source_id=str(payload.get("source_id") or "").strip(),
            revision=str(payload.get("revision") or "").strip(),
            title=str(payload.get("title") or "").strip(),
            source_family=str(payload.get("source_family") or "").strip(),
            source_type=str(payload.get("source_type") or "").strip(),
            raw_path=str(payload.get("raw_path") or "").strip(),
            extracted_path=str(payload.get("extracted_path") or "").strip(),
            byte_size=_optional_int(payload.get("byte_size")),
            materialised_at=str(payload.get("materialised_at") or "").strip(),
        )


def cache_root(task_state_dir: Path) -> Path:
    """Return the source cache root for a task's ``.crisai`` directory."""
    return task_state_dir / SOURCE_CACHE_DIRNAME


def materialise_source(
    *,
    task_state_dir: Path,
    workspace_root: Path,
    source_id: str,
    revision: str,
    raw_bytes: bytes,
    suffix: str,
    extracted: dict[str, Any],
    title: str = "",
    source_family: str = "",
    source_type: str = "",
    materialised_at: str = "",
) -> MaterialisedSource:
    """Cache a source's raw bytes and extracted sidecar, keyed by id + revision.

    Returns the cache record. The raw file and ``extracted.json`` sidecar are
    written under ``<.crisai>/sources/<source-id>/<revision>/`` and a ``meta.json``
    record is written alongside. Re-materialising the same id + revision overwrites
    in place (idempotent).
    """
    if not source_id.strip():
        raise ValueError("source_id is required to materialise a source")
    if not revision.strip():
        raise ValueError("revision is required to materialise a source")
    base = _entry_dir(task_state_dir, source_id, revision)
    base.mkdir(parents=True, exist_ok=True)

    raw_file = base / f"raw{_normalise_suffix(suffix)}"
    raw_file.write_bytes(raw_bytes)
    extracted_file = base / _EXTRACTED_NAME
    extracted_file.write_text(
        json.dumps(extracted, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )

    record = MaterialisedSource(
        source_id=source_id.strip(),
        revision=revision.strip(),
        title=title.strip(),
        source_family=source_family.strip(),
        source_type=source_type.strip(),
        raw_path=_relative(raw_file, workspace_root),
        extracted_path=_relative(extracted_file, workspace_root),
        byte_size=len(raw_bytes),
        materialised_at=materialised_at.strip(),
    )
    (base / _META_NAME).write_text(
        json.dumps(record.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )
    return record


def lookup_materialised(
    *,
    task_state_dir: Path,
    source_id: str,
    revision: str,
) -> MaterialisedSource | None:
    """Return the cached record for a source at a revision, or None on a miss.

    A miss includes the revision-invalidation case: if the requested revision was
    never cached (e.g. the upstream file changed), there is no entry and the
    caller should re-materialise.
    """
    meta = _entry_dir(task_state_dir, source_id, revision) / _META_NAME
    if not meta.is_file():
        return None
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    record = MaterialisedSource.from_dict(data)
    if record.revision != revision.strip() or record.source_id != source_id.strip():
        return None
    return record


def read_extracted(*, workspace_root: Path, record: MaterialisedSource) -> dict[str, Any]:
    """Load the extracted sidecar for a cached source; empty dict if unreadable."""
    if not record.extracted_path:
        return {}
    try:
        data = json.loads((workspace_root / record.extracted_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def prune_stale_revisions(
    *,
    task_state_dir: Path,
    source_id: str,
    keep_revision: str,
) -> list[str]:
    """Remove cached revisions of a source other than ``keep_revision``.

    Keeps the cache bounded after an upstream change. Returns the names of the
    removed revision directories.
    """
    source_dir = cache_root(task_state_dir) / _safe_segment(source_id)
    if not source_dir.is_dir():
        return []
    keep = _safe_segment(keep_revision)
    removed: list[str] = []
    for child in sorted(source_dir.iterdir()):
        if child.is_dir() and child.name != keep:
            shutil.rmtree(child, ignore_errors=True)
            removed.append(child.name)
    return removed


def extract_pptx_evidence(raw_bytes: bytes) -> dict[str, Any]:
    """Build the extracted sidecar for a PowerPoint deck (slides/tables/notes)."""
    return powerpoint.extract_powerpoint_from_bytes(raw_bytes).to_dict()


def _entry_dir(task_state_dir: Path, source_id: str, revision: str) -> Path:
    return cache_root(task_state_dir) / _safe_segment(source_id) / _safe_segment(revision)


def _safe_segment(value: str) -> str:
    """Sanitise an identity/revision into a filesystem-safe directory segment."""
    segment = re.sub(r"[^a-z0-9._-]+", "-", (value or "").strip().lower()).strip("-.")
    return segment or "unknown"


def _normalise_suffix(suffix: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "", (suffix or "").strip().lower().lstrip("."))
    return f".{cleaned}" if cleaned else ".bin"


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _optional_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
