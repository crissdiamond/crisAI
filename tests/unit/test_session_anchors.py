from __future__ import annotations

from pathlib import Path

from crisai.orchestration.request_contract import infer_request_contract
from crisai.orchestration.session_anchors import (
    SessionSourceCandidate,
    dedupe_source_candidates_by_logical_document,
    extract_session_anchors_from_history,
    render_resolved_sources,
    resolve_anchor_references,
    resolve_session_sources,
)

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registry"


def test_extracts_option_anchors_from_priority_table() -> None:
    history = [
        (
            "assistant",
            """
| Priority | Option | Summary | Recommendation |
|---|---|---|---|
| 1 | Controlled interim pipeline | Quick controlled route | Preferred short-term option |
| 2 | Target-state governed reporting data product | Governed data product | Preferred end state |
| 3 | Direct Excel-to-Power BI connection | Tactical bridge | Short-lived bridge only |
""",
        )
    ]

    registry = extract_session_anchors_from_history(history, registry_dir=REGISTRY_DIR)

    assert [(a.label, a.title) for a in registry.anchors] == [
        ("Option 1", "Controlled interim pipeline"),
        ("Option 2", "Target-state governed reporting data product"),
        ("Option 3", "Direct Excel-to-Power BI connection"),
    ]


def test_resolves_numbered_option_references_without_domain_semantics() -> None:
    registry = extract_session_anchors_from_history(
        [
            (
                "assistant",
                """
| Priority | Option | Summary | Recommendation |
|---|---|---|---|
| 1 | Interim controlled ingestion | Fast bridge | Preferred short-term option |
| 2 | Target-state governed reporting data product | Strategic end state | Preferred end state |
| 3 | Direct Excel-to-Power BI connection | Tactical bridge | Short-lived bridge only |
""",
            )
        ],
        registry_dir=REGISTRY_DIR,
    )

    refs = resolve_anchor_references(
        "Please generate HLDs for option 2 and 3.",
        registry,
        registry_dir=REGISTRY_DIR,
    )

    assert [(ref.anchor.label, ref.anchor.title) for ref in refs] == [
        ("Option 2", "Target-state governed reporting data product"),
        ("Option 3", "Direct Excel-to-Power BI connection"),
    ]


def test_request_contract_carries_resolved_anchors() -> None:
    registry = extract_session_anchors_from_history(
        [
            (
                "assistant",
                """
| Priority | Option | Summary |
|---|---|---|
| 1 | Interim controlled ingestion | Fast bridge |
| 2 | Target-state governed reporting data product | Strategic end state |
""",
            )
        ],
        registry_dir=REGISTRY_DIR,
    )

    contract = infer_request_contract(
        "Create an artefact for option 2.",
        registry_dir=REGISTRY_DIR,
        anchor_registry=registry,
    )

    assert len(contract.referenced_anchors) == 1
    assert contract.referenced_anchors[0].anchor.title == "Target-state governed reporting data product"


def _onedrive_candidate(title: str, guid: str, *, turn: int, evidence: str = "metadata_read") -> SessionSourceCandidate:
    return SessionSourceCandidate(
        title=title,
        source_family="sharepoint_docs",
        source_type="sharepoint_document",
        source_scope="personal_onedrive",
        open_url=f"https://liveuclac-my.sharepoint.com/personal/x/_layouts/15/Doc.aspx?sourcedoc=%7B{guid}%7D&file={title}",
        evidence_level=evidence,
        read_status=evidence,
        source_turn=turn,
    )


def test_logical_dedup_collapses_rediscovered_document_copies() -> None:
    # CRISAI-ADR-015: the same document re-discovered across turns carries a
    # different provider GUID each time; identity-only de-dup let those copies
    # accumulate. Logical-document de-dup collapses them to one anchor and keeps
    # the strongest copy (highest evidence level).
    candidates = [
        _onedrive_candidate("Deck v3_cd.pptx", "AAAAAAAA-0000-0000-0000-000000000001", turn=1, evidence="search_hit_only"),
        _onedrive_candidate("Deck v3_cd.pptx", "BBBBBBBB-0000-0000-0000-000000000002", turn=2, evidence="content_read"),
        _onedrive_candidate("Deck v3_cd.pptx", "CCCCCCCC-0000-0000-0000-000000000003", turn=3, evidence="metadata_read"),
        _onedrive_candidate("Deck v2.pptx", "DDDDDDDD-0000-0000-0000-000000000004", turn=1),
    ]

    merged = dedupe_source_candidates_by_logical_document(candidates)

    titles = [c.title for c in merged]
    assert titles == ["Deck v3_cd.pptx", "Deck v2.pptx"]
    kept_v3 = next(c for c in merged if c.title == "Deck v3_cd.pptx")
    assert kept_v3.evidence_level == "content_read"  # strongest copy survives the merge


def test_duplicate_copies_do_not_starve_a_distinct_named_source() -> None:
    # Reproduces the Test001 failure: three copies of one deck filled the top-3
    # resolution slots and starved the distinct, explicitly-named v2 deck, which
    # then triggered the live search that hit an Office lock file. After logical
    # de-dup, the named v2 source binds to its persisted candidate (CRISAI-ADR-015).
    candidates = [
        _onedrive_candidate("UCL Integration Strategy full deck v3_cd.pptx", "11111111-0000-0000-0000-000000000001", turn=1),
        _onedrive_candidate("UCL Integration Strategy full deck v3_cd.pptx", "22222222-0000-0000-0000-000000000002", turn=2),
        _onedrive_candidate("UCL Integration Strategy full deck v3_cd.pptx", "33333333-0000-0000-0000-000000000003", turn=3),
        _onedrive_candidate("UCL Integration Strategy_Full Presentation v2.pptx", "44444444-0000-0000-0000-000000000004", turn=1),
    ]
    message = (
        "Compare the two versions: UCL Integration Strategy_Full Presentation v2.pptx "
        "and UCL Integration Strategy full deck v3_cd.pptx, slide by slide."
    )

    merged = dedupe_source_candidates_by_logical_document(candidates)
    resolved = resolve_session_sources(message, tuple(merged), registry_dir=REGISTRY_DIR, limit=3)

    titles = [r.source.title for r in resolved]
    assert "UCL Integration Strategy_Full Presentation v2.pptx" in titles
    assert "UCL Integration Strategy full deck v3_cd.pptx" in titles
    # The named v2 source resolves to the persisted candidate (with a handle),
    # so the follow-up reuses it instead of live-searching into a lock file.
    v2 = next(r for r in resolved if "v2.pptx" in r.source.title)
    assert "44444444" in v2.source.open_url


def test_materialised_candidate_surfaces_cached_path_on_resolution() -> None:
    # ADR-015 2b slice 4b read-through: a candidate pointing at its readable cached
    # copy (workspace_path) resolves and surfaces that path in the handoff, so the
    # follow-up reads the local cache instead of re-querying live OneDrive.
    cached = SessionSourceCandidate(
        title="UCL Integration Strategy v2.pptx",
        source_family="sharepoint_docs",
        source_type="sharepoint_document",
        content_id="dd876d07",
        workspace_path="tasks/Test004/sources/dd876d07/rev-1/raw.pptx",
    )

    resolved = resolve_session_sources(
        "Summarise the UCL Integration Strategy v2 deck.",
        (cached,),
        registry_dir=REGISTRY_DIR,
        limit=3,
    )

    assert resolved
    assert resolved[0].source.workspace_path.endswith("raw.pptx")
    rendered = render_resolved_sources(resolved)
    assert "workspace_path:" in rendered
    assert "raw.pptx" in rendered
