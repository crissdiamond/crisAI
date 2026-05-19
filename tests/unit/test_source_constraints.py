from pathlib import Path

from crisai.orchestration.evidence_contract import EvidenceBundle
from crisai.orchestration.source_constraints import (
    evidence_bundle_satisfies_constraints,
    infer_source_fit_constraints,
)

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registry"


def _bundle(title: str, open_url: str) -> EvidenceBundle:
    return EvidenceBundle.from_dict(
        {
            "schema_version": "evidence_bundle_v1",
            "request": "Summarise the deck",
            "items": [
                {
                    "source": {
                        "source_type": "sharepoint_document",
                        "title": title,
                        "open_url": open_url,
                        "read_handle": "sharepoint_doc:abc",
                    },
                    "evidence_level": "content_read",
                    "read_status": "read",
                    "read_tool": "read_sharepoint_document_by_handle",
                    "content_excerpt": "Readable content.",
                    "raw_error": "",
                }
            ],
            "gaps": [],
        }
    )


def test_infers_title_phrase_before_document_type() -> None:
    constraints = infer_source_fit_constraints(
        "Summarise in 4 paragraphs the content of the most recent Integration Strategy document.",
        registry_dir=REGISTRY_DIR,
    )

    assert constraints.required_title_phrases == ("Integration Strategy",)


def test_infers_trailing_version_tokens_after_document_type() -> None:
    constraints = infer_source_fit_constraints(
        "Please summarise the Integration Strategy full deck v3 1 in detail.",
        registry_dir=REGISTRY_DIR,
    )

    assert constraints.required_title_phrases == ("Integration Strategy full v3 1",)
    assert evidence_bundle_satisfies_constraints(
        _bundle(
            "UCL Integration Strategy full deck v3 1.pptx",
            "https://liveuclac.sharepoint.com/sites/Architecture/Shared%20Documents/v3-1.pptx",
        ),
        constraints,
    )
    assert not evidence_bundle_satisfies_constraints(
        _bundle(
            "UCL Integration Strategy_Full Presentation v2_data.pptx",
            "https://liveuclac.sharepoint.com/sites/Architecture/Shared%20Documents/v2-data.pptx",
        ),
        constraints,
    )


def test_infers_quoted_title_phrase_and_onedrive_scope() -> None:
    constraints = infer_source_fit_constraints(
        "Find all 'Integration Strategy' documents in my onedrive.",
        registry_dir=REGISTRY_DIR,
    )

    assert "Integration Strategy" in constraints.required_title_phrases
    assert "personal_onedrive" in constraints.source_scopes


def test_does_not_infer_title_for_generic_this_document_request() -> None:
    constraints = infer_source_fit_constraints("Can you summarise this document?", registry_dir=REGISTRY_DIR)

    assert constraints.required_title_phrases == ()


def test_does_not_infer_prompt_framing_word_as_title_phrase() -> None:
    constraints = infer_source_fit_constraints(
        "Using the latest document, please provide me with a summary of 4 paragraphs about the strategy.",
        registry_dir=REGISTRY_DIR,
    )

    assert constraints.required_title_phrases == ()


def test_evidence_constraints_reject_wrong_title_even_when_content_read() -> None:
    constraints = infer_source_fit_constraints(
        "Summarise the most recent Integration Strategy document.",
        registry_dir=REGISTRY_DIR,
    )

    assert not evidence_bundle_satisfies_constraints(
        _bundle(
            "Local people planning guide.pptx",
            "https://liveuclac.sharepoint.com/sites/UCLPeopleandCulture/guide.pptx",
        ),
        constraints,
    )


def test_evidence_constraints_accept_matching_title_and_onedrive_scope() -> None:
    constraints = infer_source_fit_constraints(
        "Summarise the most recent Integration Strategy document in my OneDrive.",
        registry_dir=REGISTRY_DIR,
    )

    assert evidence_bundle_satisfies_constraints(
        _bundle(
            "UCL Integration Strategy full deck v3 1.pptx",
            "https://liveuclac-my.sharepoint.com/personal/user/_layouts/15/Doc.aspx?file=UCL%20Integration%20Strategy.pptx",
        ),
        constraints,
    )


def test_evidence_constraints_reject_matching_title_in_wrong_scope() -> None:
    constraints = infer_source_fit_constraints(
        "Summarise the most recent Integration Strategy document in my OneDrive.",
        registry_dir=REGISTRY_DIR,
    )

    assert not evidence_bundle_satisfies_constraints(
        _bundle(
            "UCL Integration Strategy full deck v3 1.pptx",
            "https://liveuclac.sharepoint.com/sites/Architecture/Shared%20Documents/UCL%20Integration%20Strategy.pptx",
        ),
        constraints,
    )
