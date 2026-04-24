from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

_TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_\-/]*")
_DEFAULT_FILE_PATTERNS = ("*.md", "*.txt", "*.rst")
_DEFAULT_EXCLUDED_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules"}


@dataclass(frozen=True)
class TextChunk:
    """A searchable piece of source text.

    Attributes:
        id: Stable chunk identifier within a retrieval run.
        source_path: Path of the source document relative to the indexed root.
        start_line: One-based start line in the source document.
        end_line: One-based end line in the source document.
        text: Chunk text.
    """

    id: str
    source_path: str
    start_line: int
    end_line: int
    text: str


@dataclass(frozen=True)
class RetrievalResult:
    """A ranked retrieval result.

    Attributes:
        chunk: Retrieved text chunk.
        score: Cosine similarity score between the query and chunk vectors.
        matched_terms: Query terms present in the chunk, useful for debugging.
    """

    chunk: TextChunk
    score: float
    matched_terms: tuple[str, ...]


class LocalSemanticRetriever:
    """Small local semantic retriever for workspace documents.

    This implementation provides a deterministic TF-IDF cosine retrieval
    baseline. It is intentionally dependency-light and suitable as the first
    local retrieval core before adding embedding-backed vector search.
    """

    def __init__(self, chunks: Sequence[TextChunk]) -> None:
        """Initialise the retriever from pre-built chunks.

        Args:
            chunks: Searchable text chunks.
        """
        self._chunks = list(chunks)
        self._chunk_tokens = [_tokenise(chunk.text) for chunk in self._chunks]
        self._idf = _calculate_idf(self._chunk_tokens)
        self._chunk_vectors = [_tfidf_vector(tokens, self._idf) for tokens in self._chunk_tokens]

    @classmethod
    def from_directory(
        cls,
        root_dir: Path,
        *,
        patterns: Sequence[str] = _DEFAULT_FILE_PATTERNS,
        max_chars: int = 1800,
        overlap_chars: int = 250,
        excluded_dirs: set[str] | None = None,
    ) -> "LocalSemanticRetriever":
        """Build a retriever by scanning supported local text files.

        Args:
            root_dir: Directory to index.
            patterns: Glob patterns to include.
            max_chars: Approximate maximum chunk size in characters.
            overlap_chars: Characters of overlap between neighbouring chunks.
            excluded_dirs: Directory names to skip.

        Returns:
            A retriever populated with chunks from the matching files.
        """
        root_dir = root_dir.resolve()
        skipped_dirs = excluded_dirs or _DEFAULT_EXCLUDED_DIRS
        chunks: list[TextChunk] = []

        for path in _iter_matching_files(root_dir, patterns, skipped_dirs):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="utf-8", errors="ignore")
            relative_path = str(path.relative_to(root_dir))
            chunks.extend(
                chunk_text(
                    text,
                    source_path=relative_path,
                    max_chars=max_chars,
                    overlap_chars=overlap_chars,
                )
            )

        return cls(chunks)

    @property
    def chunks(self) -> tuple[TextChunk, ...]:
        """Return the indexed chunks."""
        return tuple(self._chunks)

    def search(self, query: str, *, top_k: int = 5, min_score: float = 0.0) -> list[RetrievalResult]:
        """Return the highest scoring chunks for a natural-language query.

        Args:
            query: User query or design task.
            top_k: Maximum number of results to return.
            min_score: Minimum score threshold.

        Returns:
            Ranked retrieval results, highest score first.
        """
        if top_k <= 0 or not query.strip() or not self._chunks:
            return []

        query_tokens = _expand_query_tokens(_tokenise(query))
        query_vector = _tfidf_vector(query_tokens, self._idf)
        query_terms = set(query_tokens)
        results: list[RetrievalResult] = []

        for chunk, chunk_tokens, chunk_vector in zip(self._chunks, self._chunk_tokens, self._chunk_vectors, strict=True):
            score = _cosine_similarity(query_vector, chunk_vector)
            if score < min_score:
                continue
            matched_terms = tuple(sorted(query_terms.intersection(chunk_tokens)))
            if score > 0:
                results.append(RetrievalResult(chunk=chunk, score=score, matched_terms=matched_terms))

        return sorted(results, key=lambda item: item.score, reverse=True)[:top_k]


def chunk_text(text: str, *, source_path: str, max_chars: int = 1800, overlap_chars: int = 250) -> list[TextChunk]:
    """Split source text into overlapping chunks with line references.

    Args:
        text: Source document text.
        source_path: Relative source path used in chunk metadata.
        max_chars: Approximate maximum chunk size in characters.
        overlap_chars: Character overlap between chunks.

    Returns:
        A list of chunks preserving source path and line range metadata.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")
    if overlap_chars < 0:
        raise ValueError("overlap_chars cannot be negative")
    if overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be smaller than max_chars")

    lines = text.splitlines()
    chunks: list[TextChunk] = []
    current_lines: list[str] = []
    current_start_line = 1
    current_length = 0

    for line_number, line in enumerate(lines, start=1):
        projected_length = current_length + len(line) + 1
        if current_lines and projected_length > max_chars:
            chunks.append(_make_chunk(source_path, len(chunks), current_start_line, line_number - 1, current_lines))
            current_lines, current_start_line, current_length = _overlap_tail(
                current_lines,
                current_start_line,
                overlap_chars,
            )
        current_lines.append(line)
        current_length += len(line) + 1

    if current_lines:
        chunks.append(_make_chunk(source_path, len(chunks), current_start_line, len(lines), current_lines))

    return chunks


def format_results_for_context(results: Sequence[RetrievalResult]) -> str:
    """Format retrieval results as evidence for the context agent.

    Args:
        results: Ranked retrieval results.

    Returns:
        Markdown evidence block with scores and source line references.
    """
    if not results:
        return "No relevant local evidence found."

    sections: list[str] = []
    for index, result in enumerate(results, start=1):
        chunk = result.chunk
        sections.append(
            "\n".join(
                [
                    f"## Evidence {index}",
                    f"Source: {chunk.source_path}:{chunk.start_line}-{chunk.end_line}",
                    f"Score: {result.score:.4f}",
                    f"Matched terms: {', '.join(result.matched_terms) if result.matched_terms else 'None'}",
                    "",
                    chunk.text.strip(),
                ]
            )
        )
    return "\n\n".join(sections)


def _iter_matching_files(root_dir: Path, patterns: Sequence[str], excluded_dirs: set[str]) -> Iterable[Path]:
    for pattern in patterns:
        for path in root_dir.rglob(pattern):
            if not path.is_file():
                continue
            if any(part in excluded_dirs for part in path.parts):
                continue
            yield path


def _make_chunk(source_path: str, index: int, start_line: int, end_line: int, lines: Sequence[str]) -> TextChunk:
    return TextChunk(
        id=f"{source_path}#{index}",
        source_path=source_path,
        start_line=start_line,
        end_line=end_line,
        text="\n".join(lines).strip(),
    )


def _overlap_tail(lines: Sequence[str], start_line: int, overlap_chars: int) -> tuple[list[str], int, int]:
    if overlap_chars == 0:
        return [], start_line + len(lines), 0

    selected: list[str] = []
    total = 0
    for line in reversed(lines):
        selected.insert(0, line)
        total += len(line) + 1
        if total >= overlap_chars:
            break
    new_start_line = start_line + max(0, len(lines) - len(selected))
    return selected, new_start_line, total


def _tokenise(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def _expand_query_tokens(tokens: Sequence[str]) -> list[str]:
    """Expand query tokens with a small architecture-focused vocabulary."""
    expansions = {
        "api": ("endpoint", "integration", "interface"),
        "apis": ("endpoint", "integration", "interface"),
        "architecture": ("design", "blueprint", "solution"),
        "design": ("architecture", "solution", "blueprint"),
        "retrieval": ("search", "evidence", "context"),
        "rag": ("retrieval", "context", "evidence"),
        "solution": ("architecture", "design", "blueprint"),
    }
    expanded = list(tokens)
    for token in tokens:
        expanded.extend(expansions.get(token, ()))
    return expanded


def _calculate_idf(documents: Sequence[Sequence[str]]) -> dict[str, float]:
    document_count = len(documents)
    document_frequency: Counter[str] = Counter()
    for tokens in documents:
        document_frequency.update(set(tokens))
    return {
        token: math.log((1 + document_count) / (1 + frequency)) + 1
        for token, frequency in document_frequency.items()
    }


def _tfidf_vector(tokens: Sequence[str], idf: dict[str, float]) -> dict[str, float]:
    token_counts = Counter(tokens)
    total_terms = sum(token_counts.values()) or 1
    return {
        token: (count / total_terms) * idf.get(token, 1.0)
        for token, count in token_counts.items()
    }


def _cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    shared_terms = set(left).intersection(right)
    dot_product = sum(left[token] * right[token] for token in shared_terms)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)
