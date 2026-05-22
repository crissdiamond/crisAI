"""Source-selection policy for latest/master retrieval requests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from crisai.orchestration import evidence_contract as evidence_module
from crisai.orchestration import source_constraints as constraints_module


@dataclass(frozen=True, slots=True)
class SourceCandidate:
    """Comparable source candidate extracted from an evidence bundle."""

    item: evidence_module.EvidenceItem
    title: str
    modified_at: datetime | None
    version: int | None
    master_score: int

    @property
    def identity(self) -> str:
        """Return a stable identity for conflict comparison."""
        source = self.item.source
        return source.read_handle or source.open_url or source.workspace_path or source.content_id or self.title


def latest_source_conflict_message(
    message: str,
    bundle: evidence_module.EvidenceBundle,
    constraints: constraints_module.SourceFitConstraints,
) -> str | None:
    """Return a clarification message when latest/master signals conflict."""
    if not _asks_for_latest_or_master(message):
        return None
    candidates = _candidate_items(bundle, constraints)
    if len(candidates) < 2:
        return None

    by_date = [candidate for candidate in candidates if candidate.modified_at is not None]
    by_version = [candidate for candidate in candidates if candidate.version is not None]
    if not by_date or not by_version:
        return None

    latest_by_date = max(by_date, key=lambda c: (c.modified_at or datetime.min.replace(tzinfo=timezone.utc), c.version or -1))
    strongest_by_version = max(by_version, key=lambda c: (c.version or -1, c.master_score, c.modified_at or datetime.min.replace(tzinfo=timezone.utc)))
    if latest_by_date.identity == strongest_by_version.identity:
        return None
    if (strongest_by_version.version or -1) <= (latest_by_date.version or -1):
        return None

    return _render_conflict_message(latest_by_date, strongest_by_version)


def _asks_for_latest_or_master(message: str) -> bool:
    text = (message or "").lower()
    markers = (
        "latest",
        "most recent",
        "newest",
        "current",
        "master",
        "likely master",
        "ultimo",
        "ultima",
        "piu recente",
        "più recente",
    )
    return any(marker in text for marker in markers)


def _candidate_items(bundle: evidence_module.EvidenceBundle, constraints: constraints_module.SourceFitConstraints) -> list[SourceCandidate]:
    candidates: list[SourceCandidate] = []
    for item in bundle.items:
        if constraints.is_active and not constraints_module.evidence_item_satisfies_constraints(item, constraints):
            continue
        title = item.source.title.strip()
        if not title:
            continue
        candidates.append(
            SourceCandidate(
                item=item,
                title=title,
                modified_at=_item_modified_at(item),
                version=_title_version(title),
                master_score=_master_score(title),
            )
        )
    return candidates


def _item_modified_at(item: evidence_module.EvidenceItem) -> datetime | None:
    metadata = item.source.metadata
    for key in ("lastModifiedDateTime", "modifiedDateTime", "modified_at", "last_modified", "createdDateTime"):
        raw = metadata.get(key)
        if not raw:
            continue
        parsed = _parse_datetime(str(raw))
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(raw: str) -> datetime | None:
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _title_version(title: str) -> int | None:
    matches = re.findall(r"\bv\s*([0-9]+)\b", title, flags=re.IGNORECASE)
    if not matches:
        return None
    return max(int(match) for match in matches)


def _master_score(title: str) -> int:
    lowered = title.lower()
    score = 0
    if "master" in lowered:
        score += 3
    if "full deck" in lowered:
        score += 2
    if "full presentation" in lowered:
        score += 1
    for penalty in ("data", "shared", "update", "lt presentation", "original", "copy"):
        if penalty in lowered:
            score -= 1
    return score


def _render_conflict_message(latest_by_date: SourceCandidate, strongest_by_version: SourceCandidate) -> str:
    date_label = _format_candidate(latest_by_date)
    version_label = _format_candidate(strongest_by_version)
    return (
        "Source resolution needs confirmation before summarising: the newest modified file and the strongest "
        "version/master candidate are different.\n\n"
        f"- Newest modified file: {date_label}\n"
        f"- Strongest version/master candidate: {version_label}\n\n"
        "Please choose which one to summarise."
    )


def _format_candidate(candidate: SourceCandidate) -> str:
    parts = [candidate.title]
    if candidate.version is not None:
        parts.append(f"v{candidate.version}")
    if candidate.modified_at is not None:
        parts.append(candidate.modified_at.date().isoformat())
    return " | ".join(parts)
