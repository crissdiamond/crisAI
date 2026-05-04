"""Generic workflow policy layer for runtime capability gates."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class WorkflowPolicy:
    """Runtime policy inferred from user intent.

    Attributes:
        capabilities: High-level inferred capabilities for this run.
        require_intranet_fetch: True when evidence must include successful
            intranet page retrieval in this turn.
        require_workspace_write: True when the run must create/update files.
        write_target_subdir: Relative directory expected to change when writes
            are required.
    """

    capabilities: frozenset[str]
    require_intranet_fetch: bool = False
    require_workspace_write: bool = False
    write_target_subdir: str | None = None


class WorkflowPolicyViolation(RuntimeError):
    """Raised when a hard workflow policy gate is violated."""


def infer_workflow_policy(message: str) -> WorkflowPolicy:
    """Infer policy capabilities from a user request.

    This intentionally uses broad, reusable capability cues rather than
    request-specific wording.
    """
    text = (message or "").lower()
    capabilities: set[str] = set()

    intranet_markers = ("intranet", "site pages", "sitepages", "intranet_fetch")
    if any(marker in text for marker in intranet_markers):
        capabilities.add("intranet_grounded")

    artifact_markers = (
        "write_workspace_file",
        "create file",
        "create files",
        "deliver files",
        "context_staging/",
        "under workspace/",
    )
    if any(marker in text for marker in artifact_markers):
        capabilities.add("produce_artifacts")

    require_intranet_fetch = "intranet_grounded" in capabilities
    require_workspace_write = "produce_artifacts" in capabilities
    write_target_subdir = (
        "workspace/context_staging" if require_workspace_write else None
    )
    return WorkflowPolicy(
        capabilities=frozenset(capabilities),
        require_intranet_fetch=require_intranet_fetch,
        require_workspace_write=require_workspace_write,
        write_target_subdir=write_target_subdir,
    )


def snapshot_tree(root: Path, target_subdir: str | None) -> dict[str, int]:
    """Return a simple file mtime snapshot for a relative subtree."""
    if not target_subdir:
        return {}
    base = (root / target_subdir).resolve()
    if not base.exists() or not base.is_dir():
        return {}
    snapshot: dict[str, int] = {}
    for path in base.rglob("*"):
        if path.is_file():
            try:
                snapshot[str(path.relative_to(root))] = path.stat().st_mtime_ns
            except OSError:
                continue
    return snapshot


def changed_paths(
    before: dict[str, int],
    after: dict[str, int],
) -> list[str]:
    """Return relative file paths that changed between snapshots."""
    changed: list[str] = []
    before_keys = set(before)
    after_keys = set(after)
    for path in sorted(before_keys | after_keys):
        if path not in before or path not in after:
            changed.append(path)
            continue
        if before[path] != after[path]:
            changed.append(path)
    return changed


def has_intranet_fetch_evidence(context_retrieval_text: str) -> bool:
    """Best-effort check that retrieval output contains successful intranet fetches."""
    text = (context_retrieval_text or "").lower()
    if "intranet sources" not in text:
        return False
    negative_markers = (
        "none were retrieved in this turn",
        "no successful intranet fetches",
        "no intranet retrieval tools were invoked successfully",
    )
    return not any(marker in text for marker in negative_markers)


def enforce_intranet_fetch_policy(policy: WorkflowPolicy, context_retrieval_text: str) -> None:
    """Raise when policy requires intranet fetch evidence but none exists."""
    if not policy.require_intranet_fetch:
        return
    if has_intranet_fetch_evidence(context_retrieval_text):
        return
    raise WorkflowPolicyViolation(
        "Policy gate failed: this request requires intranet-grounded evidence, "
        "but context retrieval did not report successful intranet fetches in this run."
    )


def enforce_workspace_write_policy(
    policy: WorkflowPolicy,
    root: Path,
    before_snapshot: dict[str, int],
) -> list[str]:
    """Raise when policy requires workspace writes but no files changed."""
    if not policy.require_workspace_write:
        return []
    after_snapshot = snapshot_tree(root, policy.write_target_subdir)
    changed = changed_paths(before_snapshot, after_snapshot)
    if changed:
        return changed
    target = policy.write_target_subdir or "workspace"
    raise WorkflowPolicyViolation(
        "Policy gate failed: this request requires artefact creation/update, "
        f"but no file changes were detected under '{target}' during this run."
    )
