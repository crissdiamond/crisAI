from __future__ import annotations

import time
from pathlib import Path

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
from crisai.orchestration.retrieval_association_graph import (
    DeterministicRetrievalContext,
)


def test_infer_workflow_policy_detects_intranet_and_artifact_capabilities():
    policy = infer_workflow_policy(
        "Use intranet site pages only and write_workspace_file under workspace/tasks/demo/artefacts/patterns."
    )
    assert policy.require_intranet_fetch is True
    assert policy.require_workspace_write is True
    assert "intranet_grounded" in policy.capabilities
    assert "produce_artifacts" in policy.capabilities


def test_infer_workflow_policy_uses_registry_configuration(tmp_path: Path):
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir(parents=True)
    (registry_dir / "workflow_policy.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "workflow_policy:",
                "  capability_markers:",
                "    strict_docs:",
                "      - source-only",
                "  requirements:",
                "    intranet_fetch_for_capabilities: []",
                "    workspace_write_for_capabilities:",
                "      - strict_docs",
                "  write_target_subdir: workspace/custom_staging",
            ]
        ),
        encoding="utf-8",
    )

    policy = infer_workflow_policy("Please run source-only mode.", registry_dir=registry_dir)
    assert "strict_docs" in policy.capabilities
    assert policy.require_workspace_write is True
    assert policy.write_target_subdir == "workspace/custom_staging"


def test_has_intranet_fetch_evidence_detects_negative_marker():
    text = "Intranet sources\n- None were retrieved in this turn."
    assert has_intranet_fetch_evidence(text) is False


def test_enforce_intranet_fetch_policy_raises_when_required_and_missing():
    policy = infer_workflow_policy("intranet site pages only")
    with pytest.raises(WorkflowPolicyViolation):
        enforce_intranet_fetch_policy(policy, "Intranet sources\n- None were retrieved in this turn.")


def test_snapshot_and_changed_paths_detect_file_update(tmp_path: Path):
    root = tmp_path
    target = root / "workspace" / "tasks"
    target.mkdir(parents=True)
    file_path = target / "a.md"
    file_path.write_text("one", encoding="utf-8")
    before = snapshot_tree(root, "workspace/tasks")
    time.sleep(0.01)
    file_path.write_text("two", encoding="utf-8")
    after = snapshot_tree(root, "workspace/tasks")
    changed = changed_paths(before, after)
    assert "workspace/tasks/a.md" in changed


def test_enforce_workspace_write_policy_raises_when_required_and_no_changes(tmp_path: Path):
    root = tmp_path
    target = root / "workspace" / "tasks"
    target.mkdir(parents=True)
    before = snapshot_tree(root, "workspace/tasks")
    policy = infer_workflow_policy("create files under workspace/tasks/")
    with pytest.raises(WorkflowPolicyViolation):
        enforce_workspace_write_policy(policy, root, before)


def test_infer_workflow_policy_uses_deterministic_source_nudge():
    context = DeterministicRetrievalContext(
        schema_version="deterministic_context_v1",
        activated_topic_ids=frozenset({"integration_principles_corpus"}),
        suggested_terms=frozenset({"integration principles"}),
        suggested_sources=frozenset({"intranet"}),
        graph_loaded=True,
        graph_version="test",
    )
    policy = infer_workflow_policy("plain request", deterministic_context=context)
    assert policy.require_intranet_fetch is False


def test_infer_workflow_policy_requires_intranet_when_explicit_and_deterministic():
    context = DeterministicRetrievalContext(
        schema_version="deterministic_context_v1",
        activated_topic_ids=frozenset({"intranet_site_pages"}),
        suggested_terms=frozenset({"intranet_list_all_pages"}),
        suggested_sources=frozenset({"intranet"}),
        graph_loaded=True,
        graph_version="test",
    )
    policy = infer_workflow_policy(
        "Use intranet site pages and fetch integration principles.",
        deterministic_context=context,
    )
    assert policy.require_intranet_fetch is True


def test_has_intranet_fetch_evidence_reads_markers_from_catalog(monkeypatch):
    """has_intranet_fetch_evidence uses catalog markers, not hardcoded strings."""
    from pathlib import Path

    import yaml

    from crisai.orchestration import semantic_catalog as sc_mod
    from crisai.orchestration.semantic_catalog import build_semantic_catalog_from_dict

    base = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "registry" / "semantic_catalog.yaml").read_text(encoding="utf-8")
    )
    base["peer_verifier"]["intranet_evidence_positive_marker"] = "custom marker present"
    base["peer_verifier"]["intranet_evidence_negative_markers"] = ["custom negative"]
    custom_catalog = build_semantic_catalog_from_dict(base)

    sc_mod.load_semantic_catalog.cache_clear()
    monkeypatch.setattr(sc_mod, "load_semantic_catalog", lambda *a, **kw: custom_catalog)

    # positive marker present, no negative → evidence found
    assert has_intranet_fetch_evidence("custom marker present and data") is True
    # positive + negative → no evidence
    assert has_intranet_fetch_evidence("custom marker present custom negative") is False
    # original hardcoded string no longer works
    assert has_intranet_fetch_evidence("intranet sources fetched") is False
