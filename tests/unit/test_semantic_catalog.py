from pathlib import Path

import yaml

from crisai.orchestration.semantic_catalog import (
    SemanticCatalogError,
    build_semantic_catalog_from_dict,
    load_semantic_catalog,
    merge_semantic_catalog_dicts,
)


def _repo_semantic_catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "registry" / "semantic_catalog.yaml"


def _load_base_catalog_dict() -> dict:
    return yaml.safe_load(_repo_semantic_catalog_path().read_text(encoding="utf-8"))


def _write_merged_catalog(registry_dir: Path, overlay: dict) -> None:
    base = _load_base_catalog_dict()
    merged = merge_semantic_catalog_dicts(base, overlay)
    registry_dir.mkdir(parents=True, exist_ok=True)
    (registry_dir / "semantic_catalog.yaml").write_text(
        yaml.safe_dump(merged, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def test_load_semantic_catalog_reads_registry_overrides(tmp_path: Path):
    registry_dir = tmp_path / "registry"
    _write_merged_catalog(
        registry_dir,
        {
            "router": {
                "discovery_terms": ["discover-me"],
                "source_markers": ["discover-me"],
            },
            "peer_verifier": {
                "pattern_gap_line": r"^\s*-\s*(Pattern)\s+(\d+)\s*:",
                "leaf_file_pattern": r"workspace/context_staging/patterns/custom-(\d+)\.md$",
                "leaf_file_terms": ["high level design", "playbook"],
                "data_architecture_terms": ["data mesh"],
            },
        },
    )

    catalog = load_semantic_catalog(str(registry_dir))

    assert "discover-me" in catalog.router.discovery_terms
    assert "discover-me" in catalog.router.source_markers
    assert "design" in catalog.router.design_terms
    assert "high accuracy" in catalog.router.criticality_terms
    assert "custom" in catalog.peer_verifier.leaf_file_pattern
    assert "high level design" in catalog.peer_verifier.leaf_file_terms
    assert "playbook" in catalog.peer_verifier.leaf_file_terms
    assert "data mesh" in catalog.peer_verifier.data_architecture_terms


def test_load_semantic_catalog_peer_contract_markers_override(tmp_path: Path):
    registry_dir = tmp_path / "registry"
    _write_merged_catalog(
        registry_dir,
        {"peer_contract": {"file_write_markers": ["my-custom-write-marker"]}},
    )

    catalog = load_semantic_catalog(str(registry_dir))

    assert "my-custom-write-marker" in catalog.peer_contract.file_write_markers
    assert "write_workspace_file" not in catalog.peer_contract.file_write_markers
    assert "implement" in catalog.peer_contract.code_change_markers


def test_load_semantic_catalog_missing_file_raises(tmp_path: Path):
    registry_dir = tmp_path / "empty_registry"
    registry_dir.mkdir(parents=True)
    try:
        load_semantic_catalog(str(registry_dir))
    except FileNotFoundError as exc:
        assert "semantic_catalog.yaml" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_build_semantic_catalog_from_dict_rejects_bad_peer_verifier():
    data = _load_base_catalog_dict()
    data["peer_verifier"]["pattern_gap_line"] = ""
    try:
        build_semantic_catalog_from_dict(data)
    except SemanticCatalogError as exc:
        assert "pattern_gap_line" in str(exc)
    else:
        raise AssertionError("expected SemanticCatalogError")
