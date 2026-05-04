from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from crisai.orchestration.peer_contract import PeerRunContract


_WORKSPACE_FILE_PATTERN = re.compile(r"(workspace/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)")


@dataclass(frozen=True)
class PeerVerificationResult:
    """Structured verifier output for peer final deliverables."""

    checked_files: tuple[str, ...]
    violations: tuple[str, ...]


class PeerVerificationViolation(RuntimeError):
    """Raised when post-run peer verification fails."""


def _extract_workspace_file_paths(text: str) -> list[str]:
    """Return deduplicated workspace-relative file paths mentioned in text."""
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _WORKSPACE_FILE_PATTERN.findall(text or ""):
        cleaned = match.strip().rstrip(".,;:")
        if cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _markdown_front_matter_id(markdown_text: str) -> str | None:
    if not markdown_text.startswith("---"):
        return None
    marker = "\n---"
    close_index = markdown_text.find(marker, 3)
    if close_index == -1:
        return None
    front_matter = markdown_text[3:close_index]
    for line in front_matter.splitlines():
        if line.strip().lower().startswith("id:"):
            value = line.split(":", 1)[1].strip()
            return value or None
    return None


def verify_peer_final_deliverable(
    *,
    root_dir: Path,
    contract: PeerRunContract,
    final_text: str,
    changed_paths: list[str],
) -> PeerVerificationResult:
    """Verify peer final output claims against on-disk artefacts.

    This is a generic post-run check focused on file-backed deliverables:
    - verifies referenced files actually exist
    - validates basic markdown artefact shape
    - enforces unique front-matter ids when present
    - validates "documented in-file" mismatch claims against file content
    """
    violations: list[str] = []
    mentioned_files = _extract_workspace_file_paths(final_text)
    existing_files: list[str] = []

    for rel_path in mentioned_files:
        abs_path = (root_dir / rel_path).resolve()
        if not abs_path.exists() or not abs_path.is_file():
            violations.append(f"Referenced output file does not exist: {rel_path}")
            continue
        existing_files.append(rel_path)

    if contract.must_create_or_update_files and changed_paths and not existing_files:
        violations.append(
            "Final output did not reference any concrete workspace files, "
            "but run contract requires file-backed deliverables."
        )

    markdown_files = [p for p in existing_files if p.lower().endswith(".md")]
    front_matter_ids: dict[str, str] = {}
    for rel_path in markdown_files:
        abs_path = (root_dir / rel_path).resolve()
        content = _read_text(abs_path)
        if "## Source" not in content:
            violations.append(f"Markdown file missing required '## Source' section: {rel_path}")
        if "## " not in content:
            violations.append(f"Markdown file missing any level-2 section headers: {rel_path}")
        doc_id = _markdown_front_matter_id(content)
        if not doc_id:
            continue
        if doc_id in front_matter_ids and front_matter_ids[doc_id] != rel_path:
            violations.append(
                "Duplicate front-matter id detected across output files: "
                f"{doc_id} ({front_matter_ids[doc_id]}, {rel_path})"
            )
        else:
            front_matter_ids[doc_id] = rel_path

    lower_final = (final_text or "").lower()
    claims_mismatch_documented = (
        ("documented in-file" in lower_final or "documented in file" in lower_final)
        and ("mismatch" in lower_final or "inconsisten" in lower_final)
    )
    if claims_mismatch_documented and markdown_files:
        mismatch_found = False
        for rel_path in markdown_files:
            text = _read_text((root_dir / rel_path).resolve()).lower()
            if "mismatch" in text or "inconsisten" in text:
                mismatch_found = True
                break
        if not mismatch_found:
            violations.append(
                "Final output claims mismatch/inconsistency was documented in files, "
                "but no referenced markdown file contains mismatch/inconsistency notes."
            )

    return PeerVerificationResult(
        checked_files=tuple(existing_files),
        violations=tuple(violations),
    )


def enforce_peer_final_deliverable_verification(
    *,
    root_dir: Path,
    contract: PeerRunContract,
    final_text: str,
    changed_paths: list[str],
) -> PeerVerificationResult:
    """Raise when peer final output fails post-run filesystem verification."""
    result = verify_peer_final_deliverable(
        root_dir=root_dir,
        contract=contract,
        final_text=final_text,
        changed_paths=changed_paths,
    )
    if not result.violations:
        return result
    joined = "\n- ".join(result.violations)
    raise PeerVerificationViolation(
        "Peer verifier gate failed:\n- " + joined
    )
