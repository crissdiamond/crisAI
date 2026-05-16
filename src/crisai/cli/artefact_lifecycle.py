from __future__ import annotations

import re
from pathlib import Path

from crisai.config import load_settings
from crisai.orchestration.semantic_catalog import load_semantic_catalog
from crisai.orchestration.session_anchors import AnchorReference
from crisai.orchestration.task_contract import TaskContract, infer_task_contract
from crisai.workspace.artefact_validation import validate_workspace_artefact_paths

from .session_store import register_task_artefacts, sanitize_session_name, task_dir

_TASK_ARTEFACT_LINK_RE = re.compile(r"(?:file:///workspace/)?(tasks/[^)\s]+/artefacts/[^)\s]+\.md)")


def final_output_references_task_artefacts(final_output: str, session_name: str) -> list[str]:
    """Return task artefact paths linked by a final answer."""
    safe = sanitize_session_name(session_name)
    paths: list[str] = []
    for match in _TASK_ARTEFACT_LINK_RE.finditer(final_output or ""):
        path = match.group(1).strip()
        if path.startswith(f"tasks/{safe}/artefacts/"):
            paths.append(f"workspace/{path}")
    return sorted(dict.fromkeys(paths))


def persist_reusable_deliverable(
    *,
    session_name: str,
    user_input: str,
    final_output: str,
    registry_dir: Path | None = None,
) -> str:
    """Persist reusable chat deliverables as task artefacts and return final text."""
    if final_output_references_task_artefacts(final_output, session_name):
        return final_output
    content = (final_output or "").strip()
    if len(content) < 800 or "##" not in content:
        return final_output
    try:
        contract = infer_task_contract(user_input, registry_dir=registry_dir)
    except Exception:  # noqa: BLE001 - persistence is opportunistic and must not fail the user response.
        return final_output
    filename = _deliverable_filename(user_input, contract, registry_dir=registry_dir)
    if not filename:
        return final_output
    target = task_dir(session_name) / "artefacts" / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content + "\n", encoding="utf-8")
    rel = f"workspace/tasks/{sanitize_session_name(session_name)}/artefacts/{filename}"
    register_task_artefacts(
        session_name,
        [rel],
        request=user_input,
        deliverable_type=contract.deliverable_type,
        root_dir=Path(getattr(load_settings(), "root_dir", Path.cwd())),
    )
    return final_output.rstrip() + f"\n\nSaved artefact: [{filename}](file:///{rel})"


def validate_task_artefacts_for_request(
    *,
    user_input: str,
    paths: list[str],
    root_dir: Path,
    referenced_anchors: tuple[AnchorReference, ...] = (),
) -> list[str]:
    """Return deterministic conformance violations for generated task artefacts."""
    del user_input
    settings = load_settings()
    result = validate_workspace_artefact_paths(
        root_dir=root_dir,
        relative_paths=paths,
        registry_dir=Path(getattr(settings, "registry_dir", root_dir / "registry")),
    )
    violations = list(result.violations)
    violations.extend(_anchor_conformance_violations(paths, root_dir=root_dir, referenced_anchors=referenced_anchors))
    return violations


def _anchor_conformance_violations(
    paths: list[str],
    *,
    root_dir: Path,
    referenced_anchors: tuple[AnchorReference, ...],
) -> list[str]:
    """Return violations when generated artefacts do not preserve resolved anchors."""
    if not referenced_anchors:
        return []
    markdown_paths = [path for path in paths if path.lower().endswith(".md")]
    if len(markdown_paths) < len(referenced_anchors):
        return [
            "anchor_conformance: generated fewer Markdown artefacts than resolved user references "
            f"({len(markdown_paths)} files for {len(referenced_anchors)} reference(s))."
        ]
    contents: list[tuple[str, str]] = []
    for rel in markdown_paths:
        try:
            contents.append((rel, (root_dir / rel).read_text(encoding="utf-8").lower()))
        except OSError:
            continue
    violations: list[str] = []
    for ref in referenced_anchors:
        anchor = ref.anchor
        title = anchor.title.strip().lower()
        if not title:
            continue
        if not any(title in body for _rel, body in contents):
            violations.append(
                "anchor_conformance: no generated artefact preserves resolved reference "
                f"'{anchor.label}: {anchor.title}'."
            )
    return violations


def _deliverable_filename(user_input: str, contract: TaskContract, *, registry_dir: Path | None = None) -> str:
    del user_input
    try:
        catalog = load_semantic_catalog(str(registry_dir) if registry_dir is not None else None)
    except Exception:  # noqa: BLE001 - lifecycle persistence must fail open.
        return ""
    return catalog.artifact_lifecycle.persisted_deliverable_filenames.get(contract.deliverable_type, "")
