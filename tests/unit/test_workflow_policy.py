from __future__ import annotations

from pathlib import Path
import time

import pytest

from crisai.cli.workflow_policy import (
    WorkflowPolicyViolation,
    changed_paths,
    enforce_intranet_fetch_policy,
    enforce_workspace_write_policy,
    has_intranet_fetch_evidence,
    infer_workflow_policy,
    snapshot_tree,
)


def test_infer_workflow_policy_detects_intranet_and_artifact_capabilities():
    policy = infer_workflow_policy(
        "Use intranet site pages only and write_workspace_file under workspace/context_staging/patterns."
    )
    assert policy.require_intranet_fetch is True
    assert policy.require_workspace_write is True
    assert "intranet_grounded" in policy.capabilities
    assert "produce_artifacts" in policy.capabilities


def test_has_intranet_fetch_evidence_detects_negative_marker():
    text = "Intranet sources\n- None were retrieved in this turn."
    assert has_intranet_fetch_evidence(text) is False


def test_enforce_intranet_fetch_policy_raises_when_required_and_missing():
    policy = infer_workflow_policy("intranet site pages only")
    with pytest.raises(WorkflowPolicyViolation):
        enforce_intranet_fetch_policy(policy, "Intranet sources\n- None were retrieved in this turn.")


def test_snapshot_and_changed_paths_detect_file_update(tmp_path: Path):
    root = tmp_path
    target = root / "workspace" / "context_staging"
    target.mkdir(parents=True)
    file_path = target / "a.md"
    file_path.write_text("one", encoding="utf-8")
    before = snapshot_tree(root, "workspace/context_staging")
    time.sleep(0.01)
    file_path.write_text("two", encoding="utf-8")
    after = snapshot_tree(root, "workspace/context_staging")
    changed = changed_paths(before, after)
    assert "workspace/context_staging/a.md" in changed


def test_enforce_workspace_write_policy_raises_when_required_and_no_changes(tmp_path: Path):
    root = tmp_path
    target = root / "workspace" / "context_staging"
    target.mkdir(parents=True)
    before = snapshot_tree(root, "workspace/context_staging")
    policy = infer_workflow_policy("create files under workspace/context_staging/")
    with pytest.raises(WorkflowPolicyViolation):
        enforce_workspace_write_policy(policy, root, before)
