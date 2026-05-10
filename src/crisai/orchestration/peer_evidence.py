"""Filesystem evidence collection and repair-prompt helpers for peer workflows."""

from __future__ import annotations

from pathlib import Path

from crisai.cli.workflow_policy import FileSnapshot, changed_paths, snapshot_tree


def _build_peer_filesystem_evidence(
    *,
    root_dir: Path,
    before_snapshot: dict[str, FileSnapshot],
    target_subdir: str | None,
    max_files: int = 20,
) -> str:
    """Return compact runtime evidence about changed workspace artefacts."""
    def _extract_excerpt_lines(rel_path: str, text: str, *, max_lines: int = 8) -> list[str]:
        """Return a compact, content-bearing excerpt for judge verification."""
        body = text.strip()
        if not body:
            return []
        lines = [line.rstrip() for line in body.splitlines()]
        # Prefer meaningful markdown structure and facts over raw front matter.
        candidates: list[str] = []
        body_lines: list[str] = []
        in_front_matter = False
        front_matter_delims_seen = 0
        for line in lines:
            stripped = line.strip()
            if stripped == "---":
                front_matter_delims_seen += 1
                in_front_matter = front_matter_delims_seen == 1
                if front_matter_delims_seen >= 2:
                    in_front_matter = False
                continue
            if in_front_matter or not stripped:
                continue
            body_lines.append(stripped)
        if not body_lines:
            return []

        lower_path = rel_path.lower()

        # For index-style artefacts, include the Design overview section slice so
        # judge can see grouped lists and representative pattern entries.
        if "index" in lower_path:
            for idx, line in enumerate(body_lines):
                if line.lower() == "## design overview":
                    return body_lines[idx : idx + min(max_lines, 20)]

        # For gap-style artefacts, include the Retrieval gaps section directly.
        if "gap" in lower_path or "retrieval-gaps" in lower_path:
            for idx, line in enumerate(body_lines):
                if line.lower() == "## retrieval gaps":
                    return body_lines[idx : idx + min(max_lines, 14)]

        for stripped in body_lines:
            if stripped.startswith("## ") or stripped.startswith("- "):
                candidates.append(stripped)
            elif not candidates:
                # Fallback to the first non-empty body lines if headings/bullets
                # are not yet available.
                candidates.append(stripped)
            if len(candidates) >= max_lines:
                break
        return candidates[:max_lines]

    after_snapshot = snapshot_tree(root_dir, target_subdir)
    changed = changed_paths(before_snapshot, after_snapshot)
    changed_md = [
        p
        for p in changed
        if p.startswith("workspace/") and Path(p).suffix.lower() in {".md", ".txt"}
    ]
    if not changed_md:
        return "No changed workspace markdown/txt files detected yet in this run."

    result_lines = [f"Changed markdown/txt files ({len(changed_md)}):"]
    for rel_path in changed_md[:max_files]:
        abs_path = (root_dir / rel_path).resolve()
        if not abs_path.exists():
            result_lines.append(f"- {rel_path} | exists: no")
            continue
        text = abs_path.read_text(encoding="utf-8", errors="ignore")
        has_front_matter = text.startswith("---") and "\n---" in text[3:]
        has_source = "## Source" in text
        header_count = sum(1 for line in text.splitlines() if line.strip().startswith("## "))
        result_lines.append(
            "- "
            + rel_path
            + f" | exists: yes | front_matter: {'yes' if has_front_matter else 'no'}"
            + f" | has_source: {'yes' if has_source else 'no'} | h2_sections: {header_count}"
        )
        excerpt_lines = _extract_excerpt_lines(rel_path, text, max_lines=8)
        if excerpt_lines:
            result_lines.append("  excerpt:")
            for excerpt_line in excerpt_lines:
                result_lines.append(f"    - {excerpt_line}")
    omitted = len(changed_md) - min(len(changed_md), max_files)
    if omitted > 0:
        result_lines.append(f"- ... {omitted} additional changed files omitted from evidence summary")
    return "\n".join(result_lines)


def _format_runtime_changed_files_manifest(paths: list[str]) -> str:
    """Render a stable, verbatim manifest of changed workspace artefact paths."""
    normalized = [
        path
        for path in sorted(set(paths or []))
        if path.startswith("workspace/") and Path(path).suffix.lower() in {".md", ".txt"}
    ]
    if not normalized:
        return "None."
    return "\n".join(f"- {path}" for path in normalized)


def _prompt_section(title: str, body: str) -> str:
    """Render a stable prompt section with trimmed content."""
    clean = (body or "").strip() or "None."
    return f"{title}:\n{clean}"


def _is_repairable_peer_verifier_failure(message: str) -> bool:
    """Return whether verifier failures are repairable via final-text rewrite."""
    lower = (message or "").lower()
    repairable_markers = (
        "referenced output file does not exist",
        "final output close-out omitted changed files",
        "final output did not reference any concrete workspace files",
    )
    return any(marker in lower for marker in repairable_markers)


def _build_peer_final_repair_prompt(
    *,
    message: str,
    discovery_basis: str,
    run_contract_text: str,
    judge_text: str,
    prior_final_text: str,
    runtime_changed_manifest: str,
    verifier_failures: str,
) -> str:
    """Build a bounded repair prompt for verifier mismatch classes."""
    return "\n\n".join(
        [
            _prompt_section("User request", message),
            _prompt_section("Discovery findings", discovery_basis),
            _prompt_section("Run contract", run_contract_text),
            _prompt_section("Judge decision", judge_text),
            _prompt_section("Previous final output", prior_final_text),
            _prompt_section("Runtime changed files", runtime_changed_manifest),
            _prompt_section("Verifier failures", verifier_failures),
            "Task:\nRepair the final output so verifier checks pass without changing on-disk artefacts.",
            "Repair rules:\n"
            "- Do not claim files that do not exist.\n"
            "- Use runtime changed file paths verbatim.\n"
            "- Ensure close-out file list exactly covers changed markdown/txt files.\n"
            "- Keep source mappings aligned to those exact file paths.\n"
            "- Do not introduce new file paths, aliases, or renamed variants.\n"
            "- Keep the response concise and user-facing.",
        ]
    )
