from __future__ import annotations

from pathlib import Path

from crisai.orchestration.request_contract import infer_request_contract
from crisai.orchestration.session_anchors import (
    extract_session_anchors_from_history,
    resolve_anchor_references,
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
