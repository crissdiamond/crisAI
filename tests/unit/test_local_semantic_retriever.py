from __future__ import annotations

from pathlib import Path

import pytest

from crisai.retrieval.local_semantic import (
    LocalSemanticRetriever,
    chunk_text,
    format_results_for_context,
)


def test_chunk_text_preserves_source_and_line_references() -> None:
    text = "\n".join([f"line {index}" for index in range(1, 11)])

    chunks = chunk_text(text, source_path="docs/example.md", max_chars=35, overlap_chars=10)

    assert len(chunks) > 1
    assert chunks[0].source_path == "docs/example.md"
    assert chunks[0].start_line == 1
    assert chunks[0].end_line >= chunks[0].start_line
    assert chunks[0].id == "docs/example.md#0"


def test_chunk_text_validates_chunk_settings() -> None:
    with pytest.raises(ValueError, match="max_chars"):
        chunk_text("hello", source_path="a.md", max_chars=0)

    with pytest.raises(ValueError, match="overlap_chars"):
        chunk_text("hello", source_path="a.md", max_chars=10, overlap_chars=10)


def test_local_semantic_retriever_ranks_relevant_document_first(tmp_path: Path) -> None:
    (tmp_path / "integration.md").write_text(
        "The solution exposes REST API endpoints for student data integration.\n"
        "The design uses canonical data contracts and event topics.",
        encoding="utf-8",
    )
    (tmp_path / "finance.md").write_text(
        "The finance dashboard uses spreadsheet extracts and monthly controls.",
        encoding="utf-8",
    )

    retriever = LocalSemanticRetriever.from_directory(tmp_path)
    results = retriever.search("draft an API integration architecture", top_k=2)

    assert results
    assert results[0].chunk.source_path == "integration.md"
    assert results[0].score > 0
    assert "api" in results[0].matched_terms or "integration" in results[0].matched_terms


def test_local_semantic_retriever_returns_empty_for_empty_query(tmp_path: Path) -> None:
    (tmp_path / "doc.md").write_text("Architecture content", encoding="utf-8")

    retriever = LocalSemanticRetriever.from_directory(tmp_path)

    assert retriever.search("   ") == []


def test_format_results_for_context_includes_source_score_and_text(tmp_path: Path) -> None:
    (tmp_path / "design.md").write_text("A solution design should be grounded in evidence.", encoding="utf-8")
    retriever = LocalSemanticRetriever.from_directory(tmp_path)
    results = retriever.search("solution design evidence", top_k=1)

    formatted = format_results_for_context(results)

    assert "## Evidence 1" in formatted
    assert "Source: design.md:" in formatted
    assert "Score:" in formatted
    assert "solution design" in formatted.lower()
