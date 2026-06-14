"""Generic source-fit constraints inferred from user retrieval requests."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from crisai.orchestration import evidence_contract as evidence_module
from crisai.orchestration import semantic_catalog as catalog_module


@dataclass(frozen=True, slots=True)
class SourceFitConstraints:
    """Constraints that retrieved evidence must satisfy before downstream use."""

    required_title_phrases: tuple[str, ...] = field(default_factory=tuple)
    source_scopes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_active(self) -> bool:
        """Return whether any concrete source-fit constraint was inferred."""
        return bool(self.required_title_phrases or self.source_scopes)


def infer_source_fit_constraints(
    message: str,
    *,
    registry_dir: Path | str | None = None,
) -> SourceFitConstraints:
    """Infer title and source-scope constraints from a user request.

    The term lists live in ``registry/semantic_catalog.yaml``. Python only
    performs deterministic extraction and matching mechanics.
    """
    text = message or ""
    try:
        catalog = catalog_module.load_semantic_catalog(str(registry_dir) if registry_dir is not None else None)
    except Exception:  # noqa: BLE001 - fail open; retrieval still has prompt guidance.
        return SourceFitConstraints()

    # An explicit quoted phrase (e.g. "with 'UCL integration strategy' in the
    # title") is the unambiguous title constraint. Trust it alone and skip the
    # relation/object heuristics, which otherwise scrape instruction and
    # formatting words ("linkable name", "authoritative version. Present …") into
    # spurious title phrases (TODO-055). Heuristic extraction is the fallback only
    # when the user did not quote a phrase.
    quoted = _quoted_phrases(text)
    if quoted:
        title_phrases = _unique_preserve_order(quoted)
    else:
        title_phrases = _unique_preserve_order(
            [
                *_relation_title_phrases(text, catalog.retrieval_constraints, catalog.lexicon),
                *_object_title_phrases(text, catalog.retrieval_constraints, catalog.lexicon),
            ]
        )
    scopes = _source_scopes(text, catalog.retrieval_constraints)
    return SourceFitConstraints(
        required_title_phrases=tuple(title_phrases),
        source_scopes=tuple(scopes),
    )


def render_source_fit_constraints(constraints: SourceFitConstraints) -> str:
    """Render constraints for prompts and policy traces."""
    if not constraints.is_active:
        return "None."
    lines: list[str] = []
    if constraints.required_title_phrases:
        lines.append("required_title_phrases:")
        lines.extend(f"- {phrase}" for phrase in constraints.required_title_phrases)
    if constraints.source_scopes:
        lines.append("source_scopes:")
        lines.extend(f"- {scope}" for scope in constraints.source_scopes)
    return "\n".join(lines)


def evidence_bundle_satisfies_constraints(
    bundle: evidence_module.EvidenceBundle,
    constraints: SourceFitConstraints,
) -> bool:
    """Return whether at least one content-read item satisfies active constraints."""
    if not constraints.is_active:
        return True
    return any(
        item.evidence_level == "content_read" and evidence_item_satisfies_constraints(item, constraints)
        for item in bundle.items
    )


def evidence_item_satisfies_constraints(item: evidence_module.EvidenceItem, constraints: SourceFitConstraints) -> bool:
    """Return whether one evidence item satisfies inferred title and source scope."""
    return _title_matches(item, constraints) and _scope_matches(item, constraints)


def source_fit_failure_message(bundle: evidence_module.EvidenceBundle, constraints: SourceFitConstraints) -> str:
    """Return a concise diagnostic for a failed source-fit validation."""
    titles = [
        item.source.title
        for item in bundle.items
        if item.evidence_level == "content_read" and item.source.title
    ]
    parts = ["Policy gate failed: retrieved content does not match the user's source constraints."]
    if constraints.required_title_phrases:
        parts.append("Required title phrase(s): " + ", ".join(constraints.required_title_phrases) + ".")
    if constraints.source_scopes:
        parts.append("Required source scope(s): " + ", ".join(constraints.source_scopes) + ".")
    if titles:
        parts.append("Content-read source title(s): " + ", ".join(titles[:5]) + ".")
    return " ".join(parts)


def source_inventory_failure_message(content: str, constraints: SourceFitConstraints) -> str:
    """Return a policy diagnostic when source inventory rows miss constraints."""
    if not constraints.is_active:
        return ""
    candidates = _source_inventory_candidates(content)
    if not candidates:
        return ""
    rejected = [
        candidate.source.title
        for candidate in candidates
        if not evidence_item_satisfies_constraints(candidate, constraints)
    ]
    if not rejected:
        return ""
    parts = ["Policy gate failed: source inventory contains item(s) outside the user's source constraints."]
    if constraints.required_title_phrases:
        parts.append("Required title phrase(s): " + ", ".join(constraints.required_title_phrases) + ".")
    if constraints.source_scopes:
        parts.append("Required source scope(s): " + ", ".join(constraints.source_scopes) + ".")
    parts.append("Rejected source title(s): " + ", ".join(rejected[:5]) + ".")
    return " ".join(parts)


def _quoted_phrases(text: str) -> list[str]:
    phrases: list[str] = []
    for match in re.finditer(r"[\"'`“”‘’]([^\"'`“”‘’]{2,80})[\"'`“”‘’]", text):
        phrase = _clean_phrase(match.group(1))
        if _is_useful_title_phrase(phrase):
            phrases.append(phrase)
    return phrases


def _object_title_phrases(
    text: str,
    terms: catalog_module.RetrievalConstraintTerms,
    lexicon: catalog_module.LexiconTerms,
) -> list[str]:
    token_matches = list(re.finditer(r"[A-Za-z0-9][A-Za-z0-9._&/-]*", text or ""))
    if not token_matches:
        return []
    phrases: list[str] = []
    object_terms = terms.object_type_terms
    for index, match in enumerate(token_matches):
        if match.group(0).lower().strip("._-/") not in object_terms:
            continue
        start = max(0, index - 8)
        previous = [m.group(0) for m in token_matches[start:index]]
        phrase = _significant_suffix(
            previous,
            lexicon,
            title_position_terms=terms.title_position_terms,
            extra_stop_tokens=lexicon.forward_title_relation_terms,
        )
        trailing = _trailing_version_suffix(token_matches[index + 1 : index + 5], lexicon)
        if trailing:
            phrase = f"{phrase} {trailing}".strip()
        if _is_useful_title_phrase(phrase):
            phrases.append(phrase)
    return phrases


def _relation_title_phrases(
    text: str,
    terms: catalog_module.RetrievalConstraintTerms,
    lexicon: catalog_module.LexiconTerms,
) -> list[str]:
    token_matches = list(re.finditer(r"[A-Za-z0-9][A-Za-z0-9._&/-]*", text or ""))
    if not token_matches:
        return []
    position_tokens = {
        term
        for term in terms.title_position_terms
        if re.fullmatch(r"[a-z0-9._&/-]+", term)
    }
    forward_tokens = lexicon.forward_title_relation_terms
    stop_tokens = terms.object_type_terms | lexicon.prompt_noise_terms
    phrases: list[str] = []
    for index, match in enumerate(token_matches):
        relation_token = match.group(0).lower().strip("._-/")
        if relation_token not in position_tokens and relation_token not in forward_tokens:
            continue
        if relation_token in forward_tokens:
            phrase = _following_title_phrase(
                token_matches[index + 1 : index + 7],
                lexicon,
                title_position_terms=terms.title_position_terms,
                extra_stop_tokens=terms.object_type_terms,
            )
        else:
            start = max(0, index - 10)
            previous = [m.group(0) for m in token_matches[start:index]]
            phrase = _significant_suffix(
                previous,
                lexicon,
                title_position_terms=terms.title_position_terms,
                extra_stop_tokens=stop_tokens,
            )
        if _is_useful_title_phrase(phrase):
            phrases.append(phrase)
    return phrases


def _significant_suffix(
    tokens: list[str],
    lexicon: catalog_module.LexiconTerms,
    *,
    title_position_terms: frozenset[str] = frozenset(),
    extra_stop_tokens: frozenset[str] = frozenset(),
) -> str:
    chosen: list[str] = []
    noise = lexicon.all_function_words | lexicon.prompt_noise_terms
    connectors = lexicon.all_function_words | title_position_terms
    for token in reversed(tokens):
        lowered = token.lower().strip("._-/")
        if lowered in noise or lowered in connectors or lowered in extra_stop_tokens:
            if chosen:
                break
            continue
        chosen.append(token)
    chosen.reverse()
    return _clean_phrase(" ".join(chosen))


def _trailing_version_suffix(matches: list[re.Match[str]], lexicon: catalog_module.LexiconTerms) -> str:
    chosen: list[str] = []
    stop = lexicon.all_function_words | lexicon.prompt_noise_terms | lexicon.title_relation_terms
    for match in matches:
        token = match.group(0)
        lowered = token.lower().strip("._-/")
        if lowered in stop:
            break
        if re.fullmatch(r"v[0-9]+(?:[._-]?[0-9]+)?|[0-9]+", lowered):
            chosen.append(token)
            continue
        break
    return _clean_phrase(" ".join(chosen))


def _following_title_phrase(
    matches: list[re.Match[str]],
    lexicon: catalog_module.LexiconTerms,
    *,
    title_position_terms: frozenset[str] = frozenset(),
    extra_stop_tokens: frozenset[str] = frozenset(),
) -> str:
    chosen: list[str] = []
    stop = (
        lexicon.all_function_words
        | lexicon.prompt_noise_terms
        | lexicon.title_relation_terms
        | title_position_terms
        | extra_stop_tokens
    )
    for match in matches:
        token = match.group(0)
        lowered = token.lower().strip("._-/")
        if lowered in stop:
            if chosen:
                break
            continue
        chosen.append(token)
    return _clean_phrase(" ".join(chosen))


def _source_scopes(text: str, terms: catalog_module.RetrievalConstraintTerms) -> list[str]:
    lowered = (text or "").lower()
    scopes: list[str] = []
    for scope, markers in sorted(terms.source_scope_markers.items()):
        if any(marker in lowered for marker in markers):
            scopes.append(scope)
    return scopes


def _title_matches(item: evidence_module.EvidenceItem, constraints: SourceFitConstraints) -> bool:
    if not constraints.required_title_phrases:
        return True
    haystack = _normalise_match_text(item.source.title)
    return any(_phrase_tokens_match(phrase, haystack) for phrase in constraints.required_title_phrases)


def _scope_matches(item: evidence_module.EvidenceItem, constraints: SourceFitConstraints) -> bool:
    if not constraints.source_scopes:
        return True
    return any(_item_matches_scope(item, scope) for scope in constraints.source_scopes)


def _item_matches_scope(item: evidence_module.EvidenceItem, scope: str) -> bool:
    source = item.source
    haystack = f"{source.source_type} {source.open_url} {source.location} {source.workspace_path}".lower()
    if scope == "personal_onedrive":
        return "-my.sharepoint.com" in haystack or "/personal/" in haystack or "onedrive" in haystack
    if scope == "sharepoint":
        return "sharepoint" in haystack or source.source_type == "sharepoint_document"
    if scope == "intranet":
        return source.source_type == "intranet_page" or "intranet" in haystack
    if scope == "workspace":
        return source.source_type.startswith("workspace") or bool(source.workspace_path)
    return scope in haystack


def _phrase_tokens_match(phrase: str, haystack: str) -> bool:
    tokens = [token for token in _normalise_match_text(phrase).split() if token]
    if not tokens:
        return True
    return all(token in haystack for token in tokens)


def _normalise_match_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _clean_phrase(text: str) -> str:
    phrase = re.sub(r"\s+", " ", (text or "").strip(" \t\r\n,;:.!?()[]{}"))
    return phrase


def _source_inventory_candidates(content: str) -> list[evidence_module.EvidenceItem]:
    candidates: list[evidence_module.EvidenceItem] = []
    seen: set[tuple[str, str]] = set()
    for title, reference in _markdown_link_sources(content):
        key = (_normalise_match_text(title), reference.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            evidence_module.EvidenceItem(
                source=evidence_module.SourceReference(
                    source_type="sharepoint_document" if "sharepoint" in reference.lower() else "source",
                    title=title,
                    open_url=reference,
                    metadata={"normalised_from": "source_inventory_output"},
                ),
                evidence_level="metadata_read",
                read_status="metadata_read",
            )
        )
    return candidates


def _markdown_link_sources(content: str) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    for match in re.finditer(r"\[([^\]\n]{2,240})\]\(([^)\s]{2,1000})\)", content or ""):
        title = _clean_phrase(match.group(1))
        reference = match.group(2).strip()
        if title and reference:
            sources.append((title, reference))
    return sources


def _is_useful_title_phrase(phrase: str) -> bool:
    tokens = _normalise_match_text(phrase).split()
    if len(tokens) >= 2:
        return True
    return bool(tokens and len(tokens[0]) >= 4)


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = _normalise_match_text(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
