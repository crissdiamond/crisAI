"""Generic workflow policy layer for runtime capability gates."""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Any

import yaml

from crisai.orchestration.request_contract import RequestContract
from crisai.orchestration.retrieval_association_graph import (
    DeterministicRetrievalContext,
)
from crisai.workspace.artefact_validation import validate_workspace_artefact_paths
from crisai.workspace.spaces import load_workspace_spaces

AUTHORIZED_WRITE_PATHS_ENV = "CRISAI_WORKSPACE_AUTHORIZED_WRITE_PATHS"


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


@dataclass(frozen=True)
class WorkspaceWriteAuthorization:
    """Per-run authorization for exact workspace write targets."""

    authorized_paths: tuple[str, ...] = ()
    validation_required: bool = False

    @property
    def is_active(self) -> bool:
        """Return whether any exact paths are authorized for this run."""
        return bool(self.authorized_paths)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable trace representation."""
        return {
            "authorized_paths": list(self.authorized_paths),
            "validation_required": self.validation_required,
        }

    def to_env(self) -> dict[str, str]:
        """Return environment overrides for MCP subprocesses."""
        if not self.authorized_paths:
            return {}
        return {AUTHORIZED_WRITE_PATHS_ENV: ",".join(self.authorized_paths)}


_STRUCTURAL_DEFAULTS: dict[str, Any] = {
    "capability_markers": {},
    "requirements": {
        "intranet_fetch_for_capabilities": ["intranet_grounded"],
        "workspace_write_for_capabilities": ["produce_artifacts"],
    },
    "write_target_subdir": "workspace/tasks",
}


def _workspace_relative(path: str | None) -> str | None:
    raw = (path or "").strip().strip("`").strip("/")
    if not raw:
        return None
    if raw.startswith("workspace/"):
        raw = raw[len("workspace/") :]
    return raw or None


def workspace_write_authorization_from_contract(
    contract: RequestContract | None,
    *,
    registry_dir: Path | None = None,
) -> WorkspaceWriteAuthorization:
    """Authorize exact knowledge writes explicitly requested by the user.

    Default workspace writes stay governed by configured writable roots. This
    grants a narrow exception only for an exact output path under the configured
    knowledge root when the workspace space registry requires explicit
    promotion requests.
    """
    if contract is None or not contract.output_path:
        return WorkspaceWriteAuthorization()
    rel = _workspace_relative(contract.output_path)
    if rel is None:
        return WorkspaceWriteAuthorization()
    spaces = load_workspace_spaces(registry_dir)
    knowledge_prefix = f"{spaces.knowledge_root}/"
    if rel == spaces.knowledge_root or rel.startswith(knowledge_prefix):
        return WorkspaceWriteAuthorization(
            authorized_paths=(rel,),
            validation_required=True,
        )
    return WorkspaceWriteAuthorization()


@contextmanager
def workspace_write_authorization_env(
    authorization: WorkspaceWriteAuthorization,
) -> Iterator[None]:
    """Expose per-run write authorization to MCP subprocesses via env."""
    previous = os.environ.get(AUTHORIZED_WRITE_PATHS_ENV)
    if authorization.authorized_paths:
        os.environ[AUTHORIZED_WRITE_PATHS_ENV] = ",".join(authorization.authorized_paths)
    else:
        os.environ.pop(AUTHORIZED_WRITE_PATHS_ENV, None)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(AUTHORIZED_WRITE_PATHS_ENV, None)
        else:
            os.environ[AUTHORIZED_WRITE_PATHS_ENV] = previous


def _resolve_registry_dir(registry_dir: Path | None) -> Path:
    if registry_dir is not None:
        return registry_dir
    try:
        from crisai.config import load_settings
        return Path(load_settings().registry_dir)
    except Exception:  # noqa: BLE001
        return Path("registry")


def _load_policy_config(registry_dir: Path | None) -> dict[str, Any]:
    """Load policy config from registry/workflow_policy.yaml, with structural defaults."""
    resolved = _resolve_registry_dir(registry_dir)
    path = resolved / "workflow_policy.yaml"
    if not path.exists():
        return dict(_STRUCTURAL_DEFAULTS)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return dict(_STRUCTURAL_DEFAULTS)
    block = data.get("workflow_policy") or {}
    merged = dict(_STRUCTURAL_DEFAULTS)
    merged.update({k: v for k, v in block.items() if v is not None})
    # Deep-merge nested blocks used by this module.
    merged_markers = dict(_STRUCTURAL_DEFAULTS.get("capability_markers", {}))
    merged_markers.update(block.get("capability_markers") or {})
    merged["capability_markers"] = merged_markers
    merged_requirements = dict(_STRUCTURAL_DEFAULTS.get("requirements", {}))
    merged_requirements.update(block.get("requirements") or {})
    merged["requirements"] = merged_requirements
    return merged


def infer_workflow_policy(
    message: str,
    registry_dir: Path | None = None,
    deterministic_context: DeterministicRetrievalContext | None = None,
    advisory_deterministic_context: DeterministicRetrievalContext | None = None,
    explicit_write_target_subdir: str | None = None,
) -> WorkflowPolicy:
    """Infer policy capabilities from a user request.

    This intentionally uses broad, reusable capability cues rather than
    request-specific wording.
    """
    text = (message or "").lower()
    config = _load_policy_config(registry_dir)
    capabilities: set[str] = set()
    markers = config.get("capability_markers") or {}
    for capability, phrases in markers.items():
        phrase_list = [str(p).lower().strip() for p in (phrases or []) if str(p).strip()]
        if any(phrase in text for phrase in phrase_list):
            capabilities.add(str(capability))
    # Canonical deterministic context is authoritative. Advisory contexts are intentionally ignored here.
    del advisory_deterministic_context
    # Important: intranet fetch requirements must only be enforced when intranet
    # discovery/retrieval is explicitly requested by user intent markers. A broad
    # deterministic hint alone is not sufficient to force the policy gate.
    if deterministic_context is not None and deterministic_context.is_active:
        if "intranet" in deterministic_context.suggested_sources and "intranet_grounded" in capabilities:
            capabilities.add("intranet_grounded")

    requirements = config.get("requirements") or {}
    require_intranet_fetch = any(
        capability in capabilities
        for capability in (requirements.get("intranet_fetch_for_capabilities") or [])
    )
    require_workspace_write = any(
        capability in capabilities
        for capability in (requirements.get("workspace_write_for_capabilities") or [])
    )
    if explicit_write_target_subdir:
        capabilities.add("produce_artifacts")
        require_workspace_write = True
    write_target_subdir = (
        explicit_write_target_subdir or str(config.get("write_target_subdir") or "workspace/tasks")
        if require_workspace_write
        else None
    )
    return WorkflowPolicy(
        capabilities=frozenset(capabilities),
        require_intranet_fetch=require_intranet_fetch,
        require_workspace_write=require_workspace_write,
        write_target_subdir=write_target_subdir,
    )


FileSnapshot = tuple[int, int, str]


def snapshot_tree(root: Path, target_subdir: str | None) -> dict[str, FileSnapshot]:
    """Return a content-aware file snapshot for a relative subtree."""
    if not target_subdir:
        return {}
    base = (root / target_subdir).resolve()
    if not base.exists() or not base.is_dir():
        return {}
    snapshot: dict[str, FileSnapshot] = {}
    for path in base.rglob("*"):
        if path.is_file():
            try:
                stat = path.stat()
                snapshot[str(path.relative_to(root))] = (
                    stat.st_mtime_ns,
                    stat.st_size,
                    sha1(path.read_bytes()).hexdigest(),
                )
            except OSError:
                continue
    return snapshot


def changed_paths(
    before: dict[str, FileSnapshot],
    after: dict[str, FileSnapshot],
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
    from crisai.orchestration.semantic_catalog import load_semantic_catalog

    verifier = load_semantic_catalog().peer_verifier
    text = (context_retrieval_text or "").lower()
    if verifier.intranet_evidence_positive_marker not in text:
        return False
    return not any(m in text for m in verifier.intranet_evidence_negative_markers)


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
    before_snapshot: dict[str, FileSnapshot],
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


def enforce_workspace_authorized_write_validation(
    authorization: WorkspaceWriteAuthorization,
    *,
    root_dir: Path,
    changed: list[str],
    registry_dir: Path | None = None,
) -> None:
    """Validate changed files written through explicit knowledge authorization."""
    if not authorization.validation_required:
        return
    authorized_repo_paths = {f"workspace/{path}" for path in authorization.authorized_paths}
    changed_authorized = [path for path in changed if path in authorized_repo_paths]
    if not changed_authorized:
        requested = ", ".join(sorted(authorized_repo_paths)) or "workspace/knowledge"
        raise WorkflowPolicyViolation(
            "Policy gate failed: this request authorized an exact knowledge write, "
            f"but the requested path was not changed: {requested}"
        )
    result = validate_workspace_artefact_paths(
        root_dir=root_dir,
        relative_paths=changed_authorized,
        registry_dir=registry_dir,
    )
    if result.ok:
        return
    raise WorkflowPolicyViolation(
        "Policy gate failed: promoted knowledge artefact validation failed. "
        + " ".join(result.violations)
    )
