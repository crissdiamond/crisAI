"""Tests for the interaction patterns loaded from semantic_catalog.yaml."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from crisai.orchestration.semantic_catalog import (
    build_semantic_catalog_from_dict,
    load_semantic_catalog,
)


def _base_dict() -> dict:
    path = Path(__file__).resolve().parents[2] / "registry" / "semantic_catalog.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_explicit_mode_patterns_load_from_catalog():
    """interaction.explicit_mode_patterns has peer, pipeline, and single keys."""
    catalog = load_semantic_catalog()
    modes = catalog.interaction.explicit_mode_patterns
    assert "peer" in modes
    assert "pipeline" in modes
    assert "single" in modes
    assert len(modes["peer"]) > 0
    assert all(isinstance(p, re.Pattern) for p in modes["peer"])


def test_generative_peer_patterns_compile_without_error():
    """interaction.generative_peer_patterns contains compiled re.Pattern objects."""
    catalog = load_semantic_catalog()
    patterns = catalog.interaction.generative_peer_patterns
    assert len(patterns) > 0
    assert all(isinstance(p, re.Pattern) for p in patterns)


def test_continuation_patterns_load_from_catalog():
    """interaction.continuation_patterns contains compiled bare continuation patterns."""
    catalog = load_semantic_catalog()
    patterns = catalog.interaction.continuation_patterns
    assert len(patterns) > 0
    assert all(isinstance(p, re.Pattern) for p in patterns)
    assert any(pattern.search("continue") for pattern in patterns)
    assert any(pattern.search("continua") for pattern in patterns)


def test_continuation_intent_template_loads_from_catalog():
    """lexicon.continuation_intent_template owns continuation wrapper wording."""
    catalog = load_semantic_catalog()
    template = catalog.lexicon.continuation_intent_template
    assert template["preamble"]
    assert template["previous_user_label"].endswith(":")
    assert template["previous_assistant_label"].endswith(":")
    assert template["current_user_label"].endswith(":")


def test_peer_retrieval_force_patterns_include_intranet():
    catalog = load_semantic_catalog()
    patterns = catalog.interaction.peer_retrieval_force_patterns
    intranet_matches = [p for p in patterns if p.search("use intranet sources")]
    assert intranet_matches, "expected at least one pattern to match 'intranet'"


def test_interaction_section_absent_yields_empty_collections():
    """Catalogs without an interaction block still load; all collections are empty."""
    data = _base_dict()
    data.pop("interaction", None)
    catalog = build_semantic_catalog_from_dict(data)
    assert catalog.interaction.explicit_mode_patterns == {}
    assert catalog.interaction.continuation_patterns == ()
    assert catalog.interaction.generative_peer_patterns == ()
    assert catalog.interaction.retrieval_required_patterns == ()
    assert catalog.interaction.peer_retrieval_force_patterns == ()


def test_detect_explicit_mode_reads_catalog(monkeypatch):
    """_detect_explicit_mode uses catalog patterns, not hardcoded constants."""
    import crisai.cli.main as main_mod
    from crisai.cli.main import _detect_explicit_mode

    data = _base_dict()
    data["interaction"]["explicit_mode_patterns"] = {
        "peer": [r"\bactivate\s+custom\s+mode\b"],
    }
    custom_catalog = build_semantic_catalog_from_dict(data)

    load_semantic_catalog.cache_clear()
    monkeypatch.setattr(main_mod, "load_semantic_catalog", lambda *a, **kw: custom_catalog)

    assert _detect_explicit_mode("please activate custom mode now") == "peer"
    # original peer trigger no longer works
    assert _detect_explicit_mode("use peer mode") is None


def test_retrieval_required_patterns_loaded():
    catalog = load_semantic_catalog()
    patterns = catalog.interaction.retrieval_required_patterns
    retrieve_match = [p for p in patterns if p.search("please retrieve the document")]
    assert retrieve_match, "expected a pattern to match 'retrieve'"
