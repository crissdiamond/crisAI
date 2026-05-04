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
