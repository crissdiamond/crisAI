from pathlib import Path

import yaml

from crisai.orchestration.prompt_generation import (
    build_author_prompt,
    build_challenger_prompt,
    build_context_retrieval_prompt,
    build_context_synthesizer_prompt,
    build_design_prompt,
    build_judge_prompt,
    build_judge_quality_gate_prompt,
    build_peer_final_prompt,
    build_pipeline_final_prompt,
    build_refiner_prompt,
    build_retrieval_planner_prompt,
    build_review_prompt,
    build_single_retrieval_planner_prompt,
)
from crisai.cli.prompt_contracts import (
    DOCUMENT_EXTRACTION_CONTRACT,
    EVIDENCE_BUNDLE_CONTRACT,
    LINK_FORMATTING_CONTRACT,
    PROMPT_CONTRACT_TOOL_REFERENCES,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_build_retrieval_planner_prompt_contains_only_runtime_context():
    text = build_retrieval_planner_prompt("Find the latest design note")
    assert "User request:\nFind the latest design note" in text
    assert "Do not" in text and "repeat" in text.lower()
    assert "retrieval handoff" in text.lower()
    assert "Retrieval handoff summary" in text
    assert "Do not output JSON" in text
    assert "Deterministic retrieval handoff (pre-computed)" in text
    assert "Paths to open" in text
    assert "Rules:" not in text
    assert "Return:" not in text


def test_build_retrieval_planner_prompt_includes_association_graph_hints():
    text = build_retrieval_planner_prompt(
        "Fetch consumer pattern guidance from the architecture corpus.",
    )
    assert "Deterministic retrieval expansion" in text
    assert "semantic_graph.yaml" in text
    assert "consumer pattern" in text.lower() or "intranet_list_page_links" in text


def test_build_retrieval_prompts_include_source_fit_constraints():
    planner_text = build_retrieval_planner_prompt(
        "Summarise the most recent Integration Strategy document in my OneDrive."
    )
    retrieval_text = build_context_retrieval_prompt(
        "Summarise the most recent Integration Strategy document in my OneDrive.",
        "handoff text",
    )

    assert "Source Fit Constraints" in planner_text
    assert "Integration Strategy" in planner_text
    assert "personal_onedrive" in planner_text
    assert "Source Fit Constraints" in retrieval_text
    assert "title phrases" in retrieval_text
    assert "queries_expanded: (suppressed: explicit source constraints active)" in planner_text
    assert "api strategy" not in planner_text.lower()


def test_build_context_retrieval_prompt_documents_workspace_search_semantics():
    text = build_context_retrieval_prompt("hello", "handoff text")
    assert "search_workspace_text" in text
    assert "one line" in text.lower() or "single line" in text.lower()
    assert "Deterministic retrieval context" in text
    assert "evidence_bundle_v1" in text
    assert "read_handle" in text
    assert EVIDENCE_BUNDLE_CONTRACT in text
    assert LINK_FORMATTING_CONTRACT in text
    assert "always end with the required fenced `evidence_bundle_v1` JSON block" in text
    assert "this fenced JSON block is mandatory" in text
    assert "`source` must be an object" in text
    assert '"source_type": "sharepoint_document"' in text


def test_build_context_retrieval_prompt_enforces_intranet_tools_for_intranet_scope():
    text = build_context_retrieval_prompt(
        "Use intranet site pages only and fetch pattern pages.",
        "handoff text",
    )
    assert "Intranet-scoped hard rules" in text
    assert "MUST run intranet tools" in text
    assert "Do NOT treat existing workspace draft files" in text


def test_build_single_retrieval_planner_prompt_requires_verbatim_tool_errors():
    text = build_single_retrieval_planner_prompt("Find files in OneDrive")

    assert "report the exact failing tool name" in text
    assert "raw error text verbatim in a fenced code block" in text
    assert "evidence_bundle_v1" in text
    assert "read_sharepoint_document_by_handle" in text
    assert EVIDENCE_BUNDLE_CONTRACT in text
    assert LINK_FORMATTING_CONTRACT in text
    assert "`source` must be an object" in text


def test_build_design_prompt_normalises_empty_discovery():
    text = build_design_prompt("Draft an approach", "")
    assert "Discovery findings:\nNone." in text
    assert "Task:\nProduce the best possible architecture, design, or documentation response" in text
    assert DOCUMENT_EXTRACTION_CONTRACT in text
    assert "inspect_sharepoint_powerpoint_by_handle" in text


def test_build_review_prompt_includes_inputs_without_policy_duplication():
    text = build_review_prompt("Review this", "facts", "draft")
    assert "User request:\nReview this" in text
    assert "Discovery findings:\nfacts" in text
    assert "Draft design response:\ndraft" in text
    assert "Rules:" not in text
    assert "Highlight:" not in text


def test_build_pipeline_final_prompt_keeps_only_transition_specific_guidance():
    text = build_pipeline_final_prompt("Question", "facts", "design", "review")
    assert "Handoff guidance:" in text
    assert "Do not mention internal pipeline stages" not in text
    assert "do not mention internal pipeline stages unless the user explicitly asked" in text.lower()
    assert DOCUMENT_EXTRACTION_CONTRACT in text


def test_peer_builders_use_stable_section_labels():
    challenger = build_challenger_prompt("Question", "facts", "draft", "contract")
    refiner = build_refiner_prompt("Question", "facts", "draft", "challenge", "contract")
    judge = build_judge_prompt("Question", "facts", "challenge", "refined", "contract")
    peer_final = build_peer_final_prompt(
        "Question",
        "facts",
        "draft",
        "challenge",
        "refined",
        "accept",
        "contract",
    )

    assert "Draft:\ndraft" in challenger
    assert "Original draft:\ndraft" in refiner
    assert "Refined draft:\nrefined" in judge
    assert "Judge decision:\naccept" in peer_final
    assert "Run contract:\ncontract" in challenger
    assert "Run contract:\ncontract" in refiner
    assert "Run contract:\ncontract" in judge
    assert "Run contract:\ncontract" in peer_final
    assert "Deterministic retrieval context:" in challenger
    assert "Advisory MCP guidance:" in judge


def test_build_peer_final_prompt_adds_execution_gate_when_writes_required():
    text = build_peer_final_prompt(
        "Write with write_workspace_file under workspace/context_staging/patterns/",
        "facts",
        "draft",
        "challenge",
        "refined",
        "accept",
        runtime_changed_files_text=(
            "- workspace/context_staging/patterns/a.md\n"
            "- workspace/context_staging/patterns/b.md"
        ),
    )
    assert "Execution gate" in text
    assert "ensure required files are actually written" in text
    assert "created/updated file list" in text
    assert "Runtime changed files:" in text
    assert "workspace/context_staging/patterns/a.md" in text
    assert "Reuse these file paths verbatim in the close-out." in text


def test_build_judge_quality_gate_prompt_enforces_strict_acceptance_audit():
    text = build_judge_quality_gate_prompt(
        "Question",
        "facts",
        "challenge",
        "refined",
        "Decision: accept",
    )
    assert "Task:\nRun a strict acceptance audit" in text
    assert "If material evidence present in discovery/challenge is omitted" in text
    assert "Decision: accept" in text and "Decision: revise" in text
    assert "Missing or weak items" in text


def test_challenger_prompt_shows_advisory_guidance_when_enabled():
    text = build_challenger_prompt(
        "Question",
        "facts",
        "draft",
        deterministic_advisory_enabled=True,
    )
    assert "expand_associations" in text
    assert "non-authoritative" in text


def test_author_prompt_is_minimal_runtime_handoff():
    text = build_author_prompt("Draft it", "retrieved")
    assert "User request:\nDraft it" in text
    assert "Discovery findings:\nretrieved" in text
    assert "Rules:" not in text


def test_build_context_synthesizer_prompt_includes_request_and_retrieval():
    text = build_context_synthesizer_prompt("Summarise the design", "retrieved context here")
    assert "Summarise the design" in text
    assert "retrieved context here" in text
    assert "Context Synthesizer" in text
    assert "Do not draft" in text
    assert "Validated Evidence Summary" in text
    assert "fenced JSON `evidence_bundle_v1`" not in text
    assert DOCUMENT_EXTRACTION_CONTRACT in text
    assert "inspect_powerpoint_document" in text


def test_runtime_prompts_do_not_include_known_trace_patch_phrases():
    combined = "\n\n".join(
        [
            build_single_retrieval_planner_prompt("Find files in OneDrive"),
            build_context_retrieval_prompt("Use intranet site pages only and fetch pattern pages.", "handoff"),
            build_context_synthesizer_prompt("Summarise the design", "retrieved context here"),
            build_design_prompt("Draft an approach", ""),
            build_pipeline_final_prompt("Question", "facts", "design", "review"),
        ]
    )

    banned = ("slide-by-slide", "Integration Strategy", "v3 1")
    assert not any(phrase in combined for phrase in banned)


def test_prompt_contract_tool_references_are_exposed_by_registry():
    payload = yaml.safe_load((REPO_ROOT / "registry" / "servers.yaml").read_text(encoding="utf-8"))
    servers = {server["id"]: set(server["tools"]["allow"]) for server in payload["servers"]}

    missing = []
    for server_id, tool_names in PROMPT_CONTRACT_TOOL_REFERENCES.items():
        for tool_name in tool_names:
            if tool_name not in servers.get(server_id, set()):
                missing.append(f"{server_id}:{tool_name}")

    assert missing == []
