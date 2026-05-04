"""Tests for registry retrieval association graph expansion."""

from pathlib import Path

import pytest

from crisai.orchestration.retrieval_association_graph import (
    expand_retrieval_hints,
    format_retrieval_expansion_block,
    load_retrieval_association_graph,
)


@pytest.fixture
def registry_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "registry"


def test_load_graph_from_repo_registry(registry_dir: Path):
    graph = load_retrieval_association_graph(registry_dir)
    assert graph is not None
    assert "intranet_site_pages" in graph.vertex_terms
    assert graph.max_hops >= 0


def test_expand_intranet_and_pattern_triggers_neighbor_terms(registry_dir: Path):
    graph = load_retrieval_association_graph(registry_dir)
    assert graph is not None
    seeds, terms = expand_retrieval_hints("Use intranet site pages for consumer pattern", graph)
    assert "intranet_site_pages" in seeds
    assert "integration_patterns_area" in seeds
    assert "intranet_list_page_links" in terms


def test_format_block_empty_when_no_match(registry_dir: Path):
    graph = load_retrieval_association_graph(registry_dir)
    text = format_retrieval_expansion_block("hello world unrelated xyz", graph)
    assert text == ""


def test_missing_yaml_returns_none(tmp_path: Path):
    assert load_retrieval_association_graph(tmp_path) is None


def test_enterprise_architecture_triggers_catalogue_and_data_hints(registry_dir: Path):
    graph = load_retrieval_association_graph(registry_dir)
    assert graph is not None
    _, terms = expand_retrieval_hints("We need a business capability map for the enterprise architecture roadmap.", graph)
    assert "intranet_list_all_pages" in terms
    assert "data architecture" in terms or "application portfolio" in terms


def test_data_governance_triggers_lineage_and_catalogue_hints(registry_dir: Path):
    graph = load_retrieval_association_graph(registry_dir)
    assert graph is not None
    _, terms = expand_retrieval_hints("Assess data lineage and data catalogue maturity.", graph)
    assert "data lineage" in terms or "data catalog" in terms
    assert "intranet_list_page_links" in terms or "hub page" in terms
