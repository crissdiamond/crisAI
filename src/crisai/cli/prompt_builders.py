from __future__ import annotations

from pathlib import Path

from crisai.config import load_settings
from crisai.orchestration.retrieval_association_graph import (
    DeterministicRetrievalContext,
    build_deterministic_retrieval_context,
    format_retrieval_expansion_block,
    load_retrieval_association_graph,
)


def _resolve_deterministic_context(
    message: str,
    *,
    registry_dir: Path | None,
    deterministic_context: DeterministicRetrievalContext | None = None,
) -> DeterministicRetrievalContext:
    if deterministic_context is not None:
        return deterministic_context
    root = registry_dir if registry_dir is not None else load_settings().registry_dir
    graph = load_retrieval_association_graph(root)
    return build_deterministic_retrieval_context(message, graph)


def _retrieval_expansion_section(
    message: str,
    *,
    registry_dir: Path | None,
    deterministic_context: DeterministicRetrievalContext | None = None,
) -> str:
    """Pre-computed association-graph hints (empty when graph absent or no match)."""
    context = _resolve_deterministic_context(
        message,
        registry_dir=registry_dir,
        deterministic_context=deterministic_context,
    )
    return format_retrieval_expansion_block(message, context=context)


def _deterministic_handoff_block(context: DeterministicRetrievalContext) -> str:
    if not context.is_active:
        return "None."
    return (
        f"topics_activated: {', '.join(sorted(context.activated_topic_ids)) or '(none)'}\n"
        f"queries_expanded: {', '.join(sorted(context.suggested_terms)[:24]) or '(none)'}\n"
        f"source_priority: {', '.join(sorted(context.suggested_sources)) or '(none)'}"
    )


def _is_intranet_scoped_request(message: str) -> bool:
    text = (message or "").lower()
    markers = (
        "intranet",
        "site pages",
        "sitepages",
        "intranet_fetch",
        "intranet_search",
    )
    return any(marker in text for marker in markers)


def _requires_workspace_writes(message: str) -> bool:
    text = (message or "").lower()
    markers = (
        "write_workspace_file",
        "context_staging/",
        "create files",
        "deliver files",
        "under workspace/",
    )
    return any(marker in text for marker in markers)


def _section(title: str, body: str) -> str:
    """Render a stable prompt section with trimmed content."""
    clean = (body or "").strip() or "None."
    return f"{title}:\n{clean}"


def build_retrieval_planner_prompt(
    message: str,
    *,
    registry_dir: Path | None = None,
    deterministic_context: DeterministicRetrievalContext | None = None,
) -> str:
    """Build the runtime prompt for the retrieval planner stage.

    The retrieval planner prepares a **retrieval handoff** for ``context_retrieval``. The CLI
    router already surfaces mode, pipeline shape, and retrieval intent, so this
    stage must not repeat that recap.

    Args:
        message: User text for this stage.
        registry_dir: Optional registry root; defaults to ``load_settings().registry_dir``.
    """
    context = _resolve_deterministic_context(
        message,
        registry_dir=registry_dir,
        deterministic_context=deterministic_context,
    )
    expansion = _retrieval_expansion_section(
        message,
        registry_dir=registry_dir,
        deterministic_context=context,
    ).strip()
    blocks = [
        _section("User request", message),
    ]
    if expansion:
        blocks.append(expansion)
    blocks.extend(
        [
            "Session context:\n"
            "The crisAI router has already shown the user a routing decision (mode, "
            "pipeline vs single, retrieval on/off, and a short rationale). Treat "
            "that summary as authoritative for workflow shape.\n"
            "**Do not** repeat, paraphrase, or re-argue that routing recap.",
            "Task:\n"
            "Produce a **compact retrieval handoff** for the Context Retrieval stage.\n"
            "- Do **not** retrieve or read source documents in this stage.\n"
            "- Provide only what helps search: 3–7 concrete angles (folders, doc "
            "types, product areas, keywords, standards IDs), ambiguities that change "
            "search strategy, and user constraints that materially affect retrieval.\n"
            "- Skip generic restatements of the user goal unless they add a retrieval "
            "signal the routing line did not cover.\n"
            "- When the user names explicit workspace-relative paths (for example "
            "``context/patterns/foo.txt``), list them verbatim under **Paths to open** "
            "so the retrieval stage can call ``read_workspace_file`` immediately.\n"
            "- Include a **Structured retrieval handoff** block with keys: "
            "`topics_activated`, `queries_expanded`, `source_priority`.\n"
            "Keep the response brief (about one screen of tight bullets).",
            _section("Deterministic retrieval handoff (pre-computed)", _deterministic_handoff_block(context)),
        ]
    )
    return "\n\n".join(blocks)


def build_single_retrieval_planner_prompt(
    message: str,
    *,
    registry_dir: Path | None = None,
    deterministic_context: DeterministicRetrievalContext | None = None,
) -> str:
    """Build the runtime prompt for single-mode retrieval-planner execution.

    In single mode, the retrieval planner agent is the terminal agent for retrieval-only asks, so
    it must perform retrieval now instead of only framing a downstream stage.

    Args:
        message: User text for this stage.
        registry_dir: Optional registry root; defaults to ``load_settings().registry_dir``.
    """
    context = _resolve_deterministic_context(
        message,
        registry_dir=registry_dir,
        deterministic_context=deterministic_context,
    )
    expansion = _retrieval_expansion_section(
        message,
        registry_dir=registry_dir,
        deterministic_context=context,
    ).strip()
    blocks = [_section("User request", message)]
    if expansion:
        blocks.append(expansion)
    blocks.extend(
        [
            "Task:\nPerform retrieval now and return concrete results for the user request.",
            "Execution rules:\n"
            "- Use available retrieval tools for OneDrive/SharePoint/workspace as needed.\n"
            "- **SharePoint vs OneDrive:** if the user asks for SharePoint (not personal OneDrive only), "
            "prefer `search_sharepoint_site_documents` or `list_sites` + `search_site_drive_documents`; "
            "do not use only `list_my_drives` + `search_drive_documents` for that case.\n"
            "- Authenticate when required (for example interactive Microsoft Entra login when cached tokens are missing or expired).\n"
            "- If any retrieval/auth tool fails, report the exact failing tool name and include the raw error text verbatim in a fenced code block.\n"
            "- Do not replace tool errors with generic wording like 'unable to access' or 'login failed' when a concrete tool error is available.\n"
            "- List or search first, then inspect only matching results.\n"
            "- Do not return a planning brief, workflow framing, or clarifying questionnaire unless the request is truly ambiguous.\n"
            "- Return grounded results with file names/paths and concise relevance notes.\n"
            "- When listing **three or more** files (or the user asked for a list), use one **markdown table** with header row and separator: "
            "columns **File** | **Location** | **Note**.\n"
            "  - **File:** `[file_name](url)` only — visible text is the **file name**; URL **only** inside `(...)` (no raw URL as text). "
            "Graph: `open_url`/`webUrl`. Workspace: `file_uri` / `workspace_file_link`. Never put `&action=edit` on the visible name.\n"
            "  - **Location:** site or library name, drive, or folder (plain text).\n"
            "  - **Note:** one short relevance line (for example matched query); do not repeat the full file name.\n"
            "- For one or two files, a short bullet with the same link rules is acceptable.",
        ]
    )
    return "\n\n".join(blocks)


def build_context_retrieval_prompt(
    message: str,
    discovery_text: str,
    *,
    registry_dir: Path | None = None,
    deterministic_context: DeterministicRetrievalContext | None = None,
) -> str:
    """Build the runtime prompt for the context retrieval stage.

    This stage performs source lookup only. It should return evidence and source
    references that the context stage can structure, without drafting the final
    design response.
    """
    intranet_rules = ""
    if _is_intranet_scoped_request(message):
        intranet_rules = (
            "Intranet-scoped hard rules:\n"
            "- This request is scoped to intranet Site Pages. You MUST run intranet tools (`intranet_search`, `intranet_list_all_pages`, `intranet_list_page_links`, `intranet_fetch`) in this stage.\n"
            "- Do NOT treat existing workspace draft files under `context_staging/` as evidence for factual claims.\n"
            "- If no successful intranet fetch happened in this turn, report retrieval failure clearly rather than producing a workspace-only evidence set.\n"
        )
    context = _resolve_deterministic_context(
        message,
        registry_dir=registry_dir,
        deterministic_context=deterministic_context,
    )
    expansion = _retrieval_expansion_section(
        message,
        registry_dir=registry_dir,
        deterministic_context=context,
    ).strip()
    blocks = [
        _section("User request", message),
    ]
    if expansion:
        blocks.append(expansion)
    blocks.extend(
        [
            _section("Retrieval handoff (from retrieval planner)", discovery_text),
            _section("Deterministic retrieval context", _deterministic_handoff_block(context)),
            "Task:\nRetrieve the most relevant material for this request from available context sources. "
            "Prefer context-specific retrieval tools such as build_context_index, search_context_chunks, and get_context_index_summary when available. "
            "If those tools are unavailable, list or search before reading files. "
            "When a **Deterministic retrieval expansion** block appears above, treat it as optional query hints from `registry/retrieval_association_graph.yaml`; still validate fit to the user request. "
            "Workspace semantics:\n"
            "- ``search_workspace_text`` matches a **literal substring on one line**; long sentences often return nothing. "
            "Use **short** queries (distinctive words or path fragments) or ``subdir`` scoped to ``context`` / ``context/patterns`` etc., "
            "or call ``read_workspace_file`` / ``read_document`` when the user request or handoff names a concrete relative path.\n"
            "- When in doubt, ``list_workspace_files('context')`` (or a deeper subfolder) then open the best candidates.\n"
            + intranet_rules
            + "Return only grounded findings, source paths, relevant extracts, and any retrieval limitations. "
            "For each source row, include **Link:** `[file_name](url)` only — visible text is the **file name**, URL **only** inside parentheses; do not duplicate the URL as plain text "
            "and never append `&action=edit` or other query text to the file name. "
            "Graph: use `open_url`/`webUrl`; workspace: use `file_uri` from `search_workspace_text` or `workspace_file_link`. "
            "For SharePoint (not OneDrive-only) use `search_sharepoint_site_documents` or site-scoped search after `list_sites`. "
            "Do not draft, recommend, or optimise the final design response.",
        ]
    )
    return "\n\n".join(blocks)


def build_design_prompt(message: str, discovery_text: str) -> str:
    """Build the runtime prompt for the design stage."""
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            "Task:\nProduce the best possible architecture, design, or documentation response for the user's request.",
        ]
    )


def build_review_prompt(message: str, discovery_text: str, design_text: str) -> str:
    """Build the runtime prompt for the review stage."""
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Draft design response", design_text),
            "Task:\nCritically review the draft.",
        ]
    )


def build_pipeline_final_prompt(message: str, discovery_text: str, design_text: str, review_text: str) -> str:
    """Build the runtime prompt for the pipeline final stage."""
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Draft design response", design_text),
            _section("Review feedback", review_text),
            "Task:\nProduce the final answer to the user.",
            "Handoff guidance:\n"
            "- Use the design output as the main body.\n"
            "- Incorporate review feedback only where it improves the answer.\n"
            "- do not mention internal pipeline stages unless the user explicitly asked to see them.",
        ]
    )


def build_author_prompt(message: str, discovery_text: str, run_contract_text: str = "") -> str:
    """Build the runtime prompt for the author stage.

    This stage must remain isolated from later peer roles. The author receives
    the full user request, but must only produce the initial proposal or first
    draft. Later critique, refinement, judgement, and final packaging are
    handled by separate agents.
    """
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Run contract", run_contract_text),
            "Task:\nProduce the best possible first draft for the user's request.",
            "Stage boundary:\n"
            "- You are only the author stage in a peer workflow.\n"
            "- Do not simulate the challenger, refiner, judge, or orchestrator.\n"
            "- Do not output a peer transcript or role-labelled conversation.\n"
            "- Do not include sections such as 'Challenger', 'Refiner', 'Judge', 'Peer conversation', or 'Final recommendation'.\n"
            "- Output only the initial draft or proposal that later peer stages will inspect.\n"
            "- If the run contract expects a concrete deliverable (answer/files/code), do not output a meta-assessment about process quality.",
        ]
    )


def build_challenger_prompt(
    message: str,
    discovery_text: str,
    author_text: str,
    run_contract_text: str = "",
) -> str:
    """Build the runtime prompt for the challenger stage."""
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Run contract", run_contract_text),
            _section("Draft", author_text),
            "Task:\nCritique the draft rigorously.",
            "Stage boundary:\n"
            "- You are only the challenger stage in a peer workflow.\n"
            "- Do not rewrite the draft directly.\n"
            "- Do not simulate the refiner, judge, or orchestrator.\n"
            "- Do not output a peer transcript or final recommendation.\n"
            "- Output only critique for later stages to use.\n"
            "- Critique against run-contract dimensions and missing deliverable outcomes, not writing style alone.",
        ]
    )


def build_refiner_prompt(
    message: str,
    discovery_text: str,
    author_text: str,
    challenger_text: str,
    run_contract_text: str = "",
) -> str:
    """Build the runtime prompt for the refiner stage."""
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Run contract", run_contract_text),
            _section("Original draft", author_text),
            _section("Challenge", challenger_text),
            "Task:\nRefine the draft using the critique.",
            "Stage boundary:\n"
            "- You are only the refiner stage in a peer workflow.\n"
            "- Do not simulate the judge or orchestrator.\n"
            "- Do not output a peer transcript or final recommendation.\n"
            "- Output only the improved draft that should be judged next.\n"
            "- Preserve material evidence/detail from discovery; do not collapse deliverables into generic assessment text.",
        ]
    )


def build_judge_prompt(
    message: str,
    discovery_text: str,
    challenger_text: str,
    refiner_text: str,
    run_contract_text: str = "",
) -> str:
    """Build the runtime prompt for the judge stage."""
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Run contract", run_contract_text),
            _section("Challenge", challenger_text),
            _section("Refined draft", refiner_text),
            "Task:\nDecide whether the refined answer is good enough.",
            "Stage boundary:\n"
            "- You are only the judge stage in a peer workflow.\n"
            "- Do not rewrite the answer.\n"
            "- Do not simulate the orchestrator.\n"
            "- Do not output a peer transcript or final recommendation.\n"
            "- Output only the judgement, reasons, and any remaining issues.\n"
            "- Judge against run-contract dimensions first; reject outputs that are coherent but fail expected deliverable type.",
        ]
    )


def build_judge_quality_gate_prompt(
    message: str,
    discovery_text: str,
    challenger_text: str,
    refiner_text: str,
    prior_judge_text: str,
    run_contract_text: str = "",
) -> str:
    """Build a strict acceptance-audit prompt for peer mode.

    This is a structural quality gate: when the initial judge decision is
    "accept", we run a second adjudication pass that specifically checks for
    silent information loss, weak evidence retention, and missing critical
    constraints.
    """
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Run contract", run_contract_text),
            _section("Challenge", challenger_text),
            _section("Refined draft", refiner_text),
            _section("Initial judge output", prior_judge_text),
            "Task:\nRun a strict acceptance audit on the refined draft.",
            "Acceptance audit rules:\n"
            "- Compare the refined draft against discovery findings and challenge notes.\n"
            "- If material evidence present in discovery/challenge is omitted, weakened, or replaced with generic wording, return `Decision: revise`.\n"
            "- If critical constraints, implementation details, assumptions, risks, or retrieval gaps are missing despite being available in evidence, return `Decision: revise`.\n"
            "- If unsupported claims appear, return `Decision: revise`.\n"
            "- If run contract expects concrete deliverables (files/code/final answer), do not accept outputs that are mainly process critique, uncertainty narration, or 'needs verification' checklists.\n"
            "- Return `Decision: accept` only when the refined draft preserves material evidence and is ready to ship.\n"
            "Output contract:\n"
            "- First line must be exactly `Decision: accept` or `Decision: revise`.\n"
            "- Then provide concise `Reason:` and, when revising, a `Missing or weak items:` bullet list.",
        ]
    )


def build_peer_final_prompt(
    message: str,
    discovery_text: str,
    author_text: str,
    challenger_text: str,
    refiner_text: str,
    judge_text: str,
    run_contract_text: str = "",
    runtime_changed_files_text: str = "",
) -> str:
    """Build the runtime prompt for the peer final stage."""
    execution_gate = ""
    if _requires_workspace_writes(message):
        runtime_file_guidance = ""
        if runtime_changed_files_text.strip():
            runtime_file_guidance = (
                "Runtime changed files:\n"
                f"{runtime_changed_files_text.strip()}\n"
                "- Reuse these file paths verbatim in the close-out.\n"
                "- Do not rename, normalize, or substitute path variants.\n"
            )
        execution_gate = (
            "Execution gate:\n"
            "- The user request requires filesystem side effects (creating/updating files in workspace).\n"
            "- Before finalising, ensure required files are actually written via workspace tools in this turn.\n"
            "- If previous peer stages only produced critique text, perform the missing write actions now instead of returning another critique-only answer.\n"
            "- Final response must include a concise created/updated file list with source provenance.\n"
            + runtime_file_guidance
        )
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Run contract", run_contract_text),
            _section("Original draft", author_text),
            _section("Challenge", challenger_text),
            _section("Refined draft", refiner_text),
            _section("Judge decision", judge_text),
            "Task:\nProduce the final answer to the user.",
            "Handoff guidance:\n"
            "- Use the refined draft as the main body.\n"
            "- Incorporate only improvements justified by the critique and judge decision.\n"
            "- Show the peer conversation only if the user explicitly asked to see it.\n"
            "- If the user asked to see the peer conversation, present it only here in the final stage, not in earlier stages.\n"
            "- Do not mention internal peer stages unless the user explicitly asked to see them.\n"
            + execution_gate,
        ]
    )
