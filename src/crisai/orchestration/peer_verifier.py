from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from crisai.orchestration.peer_contract import PeerRunContract
from crisai.orchestration.semantic_catalog import load_semantic_catalog


_WORKSPACE_FILE_PATTERN = re.compile(r"(workspace/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)")


@lru_cache(maxsize=1)
def _pattern_gap_line_regex() -> re.Pattern[str]:
    pattern = load_semantic_catalog().peer_verifier.pattern_gap_line
    return re.compile(pattern, re.IGNORECASE)


@lru_cache(maxsize=1)
def _leaf_file_pattern_regex() -> re.Pattern[str]:
    pattern = load_semantic_catalog().peer_verifier.leaf_file_pattern
    return re.compile(pattern, re.IGNORECASE)


@lru_cache(maxsize=1)
def _leaf_file_terms() -> frozenset[str]:
    return load_semantic_catalog().peer_verifier.leaf_file_terms


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


def _is_placeholder_leaf_content(markdown_text: str) -> bool:
    lower = (markdown_text or "").lower()
    if "[grounded details to be added" in lower:
        return True
    if "details coming soon" in lower:
        return True
    return False


def _has_grounded_leaf_content(markdown_text: str) -> bool:
    if "## Design overview" not in markdown_text:
        return False
    if _is_placeholder_leaf_content(markdown_text):
        return False
    lower = markdown_text.lower()
    signal_markers = (
        "- name:",
        "- description:",
        "- version / status / date:",
        "- classification:",
        "- nfrs:",
        "- security:",
    )
    return any(marker in lower for marker in signal_markers)


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


def _extract_gap_patterns(markdown_text: str) -> set[str]:
    patterns: set[str] = set()
    in_gaps_section = False
    for raw_line in (markdown_text or "").splitlines():
        line = raw_line.strip()
        if line.lower().startswith("## "):
            in_gaps_section = line.lower().startswith("## retrieval gap")
            continue
        if not in_gaps_section:
            continue
        match = _pattern_gap_line_regex().match(raw_line)
        if not match:
            continue
        family = match.group(1).capitalize()
        number = match.group(2)
        patterns.add(f"{family} Pattern {number}")
    return patterns


def _pattern_name_from_leaf_path(rel_path: str) -> str | None:
    match = _leaf_file_pattern_regex().search(rel_path)
    if not match:
        return None
    family = match.group(1).capitalize()
    number = match.group(2)
    return f"{family} Pattern {number}"


def _is_semantic_leaf_file(rel_path: str) -> bool:
    """Return whether a file path matches configured leaf-file semantics."""
    if _leaf_file_pattern_regex().search(rel_path):
        return True
    terms = _leaf_file_terms()
    if not terms:
        return False
    # Match against filename in a separator-normalized form.
    name = Path(rel_path).name.lower()
    normalized = " ".join(name.replace("-", " ").replace("_", " ").split())
    return any(term in normalized for term in terms)


def _requires_source_section(rel_path: str) -> bool:
    """Return whether a markdown artefact must include a `## Source` section."""
    name = Path(rel_path).name.lower()
    if "retrieval-gap" in name or "retrieval-gaps" in name:
        return False
    return _is_semantic_leaf_file(rel_path) or "index" in name


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

    # Close-out fidelity check: if final output references files, it must not
    # omit files that changed in this run.
    normalized_changed = sorted(
        {
            path
            for path in (changed_paths or [])
            if path.startswith("workspace/") and Path(path).suffix.lower() in {".md", ".txt"}
        }
    )
    if existing_files and normalized_changed:
        changed_set = set(normalized_changed)
        referenced_set = set(existing_files)
        missing_from_summary = sorted(changed_set - referenced_set)
        if missing_from_summary:
            violations.append(
                "Final output close-out omitted changed files from this run: "
                + ", ".join(missing_from_summary)
            )

    markdown_files = [p for p in existing_files if p.lower().endswith(".md")]
    front_matter_ids: dict[str, str] = {}
    for rel_path in markdown_files:
        abs_path = (root_dir / rel_path).resolve()
        content = _read_text(abs_path)
        if _requires_source_section(rel_path) and "## Source" not in content:
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

    # Cross-file consistency for gap-driven artefact packages:
    # if a pattern is marked as missing grounded content in a gaps file, its
    # leaf file must not carry grounded detail content; conversely if the leaf
    # file is placeholder/stub, it should appear in retrieval gaps.
    gap_files = [p for p in markdown_files if "retrieval-gaps" in Path(p).name]
    leaf_files = [p for p in markdown_files if _is_semantic_leaf_file(p)]
    if gap_files and leaf_files:
        gap_patterns: set[str] = set()
        for gap_file in gap_files:
            gap_patterns.update(_extract_gap_patterns(_read_text((root_dir / gap_file).resolve())))

        for leaf_file in leaf_files:
            pattern_name = _pattern_name_from_leaf_path(leaf_file)
            if not pattern_name:
                continue
            text = _read_text((root_dir / leaf_file).resolve())
            has_grounded = _has_grounded_leaf_content(text)
            is_placeholder = _is_placeholder_leaf_content(text)

            if pattern_name in gap_patterns and has_grounded:
                violations.append(
                    f"Gap inconsistency: '{pattern_name}' is listed as missing grounded content, "
                    f"but '{leaf_file}' contains grounded detail fields."
                )
            if pattern_name not in gap_patterns and is_placeholder:
                violations.append(
                    f"Gap omission: '{leaf_file}' is placeholder/stub content but '{pattern_name}' "
                    "is not listed in retrieval gaps."
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
