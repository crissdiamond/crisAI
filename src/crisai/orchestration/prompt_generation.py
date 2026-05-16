from __future__ import annotations

from pathlib import Path

from crisai.cli.prompt_contracts import (
    DOCUMENT_EXTRACTION_CONTRACT,
    EVIDENCE_BUNDLE_CONTRACT,
    LINK_FORMATTING_CONTRACT,
    RETRIEVAL_EVIDENCE_POLICY_CONTRACT,
    SHAREPOINT_READ_HANDLE_CONTRACT,
)
from crisai.config import load_settings
from crisai.orchestration.retrieval_association_graph import (
    DeterministicRetrievalContext,
    build_deterministic_retrieval_context,
    format_retrieval_expansion_block,
    load_retrieval_association_graph,
)
from crisai.orchestration.source_constraints import (
    infer_source_fit_constraints,
    render_source_fit_constraints,
)
from crisai.orchestration.task_contract import (
    TaskContract,
    render_task_contract_summary,
)
from crisai.workspace.spaces import load_workspace_spaces


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


def _deterministic_handoff_block(context: DeterministicRetrievalContext, *, include_terms: bool = True) -> str:
    if not context.is_active:
        return "None."
    query_terms = ", ".join(sorted(context.suggested_terms)[:24]) if include_terms else "(suppressed: explicit source constraints active)"
    return (
        f"schema_version: {context.schema_version}\n"
        f"graph_loaded: {'yes' if context.graph_loaded else 'no'}\n"
        f"graph_version: {context.graph_version}\n"
        f"topics_activated: {', '.join(sorted(context.activated_topic_ids)) or '(none)'}\n"
        f"queries_expanded: {query_terms or '(none)'}\n"
        f"source_priority: {', '.join(sorted(context.suggested_sources)) or '(none)'}"
    )


def _advisory_mcp_guidance(enabled: bool) -> str:
    if not enabled:
        return "None."
    return (
        "Advisory lookup is enabled. You may call `expand_associations` for extra analysis context.\n"
        "- Advisory MCP output is optional and non-authoritative.\n"
        "- Do not override deterministic canonical context from workflow runtime.\n"
        "- If the tool fails or is unavailable, continue without it."
    )


def _is_intranet_scoped_request(message: str) -> bool:
    text = (message or "").lower()
    markers = (
        "intranet",
        "site pages",
        "sitepages",
        "intranet_fetch_page",
        "intranet_search_pages",
    )
    return any(marker in text for marker in markers)


def _requires_workspace_writes(message: str) -> bool:
    text = (message or "").lower()
    markers = (
        "write_workspace_file",
        "knowledge_staging/",
        "tasks/",
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
    task_contract: TaskContract | None = None,
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
    source_constraints = infer_source_fit_constraints(message, registry_dir=registry_dir)
    expansion = (
        ""
        if source_constraints.is_active
        else _retrieval_expansion_section(
            message,
            registry_dir=registry_dir,
            deterministic_context=context,
        ).strip()
    )
    blocks = [_section("User request", message)]
    if task_contract is not None:
        blocks.append(_section("Task Contract", render_task_contract_summary(task_contract)))
    blocks.append(_section("Source Fit Constraints", render_source_fit_constraints(source_constraints)))
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
            "- Preserve the Task Contract's primary deliverable. Retrieval is a support step, not the final answer.\n"
            "- Preserve Source Fit Constraints exactly: explicit title phrases and source scopes outrank semantic expansion hints.\n"
            "- Do **not** retrieve or read source documents in this stage.\n"
            "- Provide only what helps search: 3–7 concrete angles (folders, doc "
            "types, product areas, keywords, standards IDs), ambiguities that change "
            "search strategy, and user constraints that materially affect retrieval.\n"
            "- Skip generic restatements of the user goal unless they add a retrieval "
            "signal the routing line did not cover.\n"
            "- When the user names explicit workspace-relative paths (for example "
            "``knowledge/patterns/foo.txt`` or ``tasks/<task>/artefacts/foo.md``), list them verbatim under **Paths to open** "
            "so the retrieval stage can call ``read_workspace_file`` immediately.\n"
            "- End with a **Retrieval handoff summary** using plain bullets for activated topics, query terms, and source priority.\n"
            "- Do not output JSON; machine-readable deterministic context is already supplied separately by the runtime.\n"
            "Keep the response brief (about one screen of tight bullets).",
            _section(
                "Deterministic retrieval handoff (pre-computed)",
                _deterministic_handoff_block(context, include_terms=not source_constraints.is_active),
            ),
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
    source_constraints = infer_source_fit_constraints(message, registry_dir=registry_dir)
    expansion = (
        ""
        if source_constraints.is_active
        else _retrieval_expansion_section(
            message,
            registry_dir=registry_dir,
            deterministic_context=context,
        ).strip()
    )
    blocks = [_section("User request", message)]
    blocks.append(_section("Source Fit Constraints", render_source_fit_constraints(source_constraints)))
    if expansion:
        blocks.append(expansion)
    blocks.extend(
        [
            "Task:\nPerform retrieval now and return concrete results for the user request.",
            "Execution rules:\n"
            "- Use available retrieval tools for OneDrive/SharePoint/workspace as needed.\n"
            "- Preserve Source Fit Constraints exactly: explicit title phrases and source scopes are hard filters.\n"
            "- **SharePoint vs OneDrive:** if the user asks for SharePoint (not personal OneDrive only), "
            "prefer `search_sharepoint_site_documents` or `list_sites` + `search_site_drive_documents`; "
            "do not use only `list_my_drives` + `search_drive_documents` for that case.\n"
            "- Authenticate when required (for example interactive Microsoft Entra login when cached tokens are missing or expired).\n"
            "- If any retrieval/auth tool fails, report the exact failing tool name and include the raw error text verbatim in a fenced code block.\n"
            "- Do not replace tool errors with generic wording like 'unable to access' or 'login failed' when a concrete tool error is available.\n"
            "- List or search first, then inspect only matching results.\n"
            "- Do not return a planning brief, workflow framing, or clarifying questionnaire unless the request is truly ambiguous.\n"
            "- Return grounded results with file names/paths and concise relevance notes.\n"
            "- For one or two files, a short bullet with the same link rules is acceptable.",
            SHAREPOINT_READ_HANDLE_CONTRACT,
            RETRIEVAL_EVIDENCE_POLICY_CONTRACT,
            LINK_FORMATTING_CONTRACT,
            EVIDENCE_BUNDLE_CONTRACT,
        ]
    )
    return "\n\n".join(blocks)


def build_context_retrieval_prompt(
    message: str,
    discovery_text: str,
    *,
    registry_dir: Path | None = None,
    deterministic_context: DeterministicRetrievalContext | None = None,
    task_contract: TaskContract | None = None,
) -> str:
    """Build the runtime prompt for the context retrieval stage.

    This stage performs source lookup only. It should return evidence and source
    references that the context stage can structure, without drafting the final
    design response.
    """
    context = _resolve_deterministic_context(
        message,
        registry_dir=registry_dir,
        deterministic_context=deterministic_context,
    )
    spaces = load_workspace_spaces(registry_dir)
    knowledge_root = spaces.knowledge_root
    staging_root = spaces.knowledge_staging_root
    intranet_rules = ""
    if _is_intranet_scoped_request(message):
        intranet_rules = (
            "Intranet-scoped hard rules:\n"
            "- This request is scoped to intranet pages. You MUST run intranet tools (`intranet_search_pages`, `intranet_list_pages`, `intranet_list_page_links_by_id`, `intranet_fetch_page`) in this stage.\n"
            f"- Do NOT treat existing workspace draft files under `{staging_root}/` or `tasks/*/artefacts/` as evidence for factual claims outside the active task.\n"
            "- If no successful intranet fetch happened in this turn, report retrieval failure clearly rather than producing a workspace-only evidence set.\n"
        )
    source_constraints = infer_source_fit_constraints(message, registry_dir=registry_dir)
    expansion = (
        ""
        if source_constraints.is_active
        else _retrieval_expansion_section(
            message,
            registry_dir=registry_dir,
            deterministic_context=context,
        ).strip()
    )
    blocks = [_section("User request", message)]
    if task_contract is not None:
        blocks.append(_section("Task Contract", render_task_contract_summary(task_contract)))
    blocks.append(_section("Source Fit Constraints", render_source_fit_constraints(source_constraints)))
    if expansion:
        blocks.append(expansion)
    blocks.extend(
        [
            _section("Retrieval handoff (from retrieval planner)", discovery_text),
            _section(
                "Deterministic retrieval context",
                _deterministic_handoff_block(context, include_terms=not source_constraints.is_active),
            ),
            "Task:\nRetrieve the most relevant material for this request from available context sources. "
            "Prefer context-specific retrieval tools such as build_context_index, search_context_chunks, and get_context_index_summary when available. "
            "If those tools are unavailable, list or search before reading files. "
            "When a **Deterministic retrieval expansion** block appears above, treat it as optional query hints from `registry/semantic_graph.yaml`; still validate fit to the user request. "
            "Workspace semantics:\n"
            "- ``search_workspace_text`` matches a **literal substring on one line**; long sentences often return nothing. "
            f"Use **short** queries (distinctive words or path fragments) or ``subdir`` scoped to ``{knowledge_root}`` / ``{knowledge_root}/patterns`` / the active task path, "
            "or call ``read_workspace_file`` / ``read_document`` when the user request or handoff names a concrete relative path.\n"
            f"- When in doubt, ``list_workspace_files('{knowledge_root}')`` (or a deeper subfolder) and the active task artefact folder, then open the best candidates.\n"
            + intranet_rules
            + "Return only grounded findings, source paths, relevant extracts, and any retrieval limitations. "
            "Do not create, update, or append workspace artefacts during retrieval; never call write-capable workspace tools from this stage. "
            "When source selection is needed, keep selection rationale short and make the read content prominent. "
            "Enforce Source Fit Constraints before reading: title phrases and user-scoped sources are hard filters, while deterministic expansion terms are optional hints. "
            "For SharePoint (not OneDrive-only) use `search_sharepoint_site_documents` or site-scoped search after `list_sites`. "
            "When the user asks for a summary of a document/deck/file, read the content first and mark the item `content_read`; if the read fails, mark it `read_failed` and include the raw error. "
            "For document/deck/file summary requests, always end with the required fenced `evidence_bundle_v1` JSON block; never rely on prose-only retrieval notes. "
            "Do not draft, recommend, or optimise the final design response.",
            SHAREPOINT_READ_HANDLE_CONTRACT,
            RETRIEVAL_EVIDENCE_POLICY_CONTRACT,
            LINK_FORMATTING_CONTRACT,
            EVIDENCE_BUNDLE_CONTRACT,
        ]
    )
    return "\n\n".join(blocks)


def build_context_retrieval_repair_prompt(
    message: str,
    retrieval_plan_text: str,
    invalid_output: str,
    validation_error: str,
) -> str:
    """Build a generic retry prompt for invalid retrieval evidence transport."""
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Retrieval handoff", retrieval_plan_text),
            _section("Previous retrieval output that failed validation", invalid_output),
            _section("Validation error", validation_error),
            "Task:\nRepair the retrieval evidence contract for the same user request. "
            "If the previous output does not contain enough source metadata and content evidence to construct a valid bundle, use the available retrieval tools again before answering. "
            "Return concise grounded retrieval prose, then end with a fenced `json` block containing `schema_version: \"evidence_bundle_v1\"`. "
            "For document/deck/file summary requests, the bundle must include at least one `content_read` item backed by a successful read or inspect tool call. "
            "Do not draft the final answer; only provide retrieval findings and the evidence bundle.",
            SHAREPOINT_READ_HANDLE_CONTRACT,
            RETRIEVAL_EVIDENCE_POLICY_CONTRACT,
            EVIDENCE_BUNDLE_CONTRACT,
        ]
    )


def build_design_prompt(message: str, discovery_text: str, task_contract: TaskContract | None = None) -> str:
    """Build the runtime prompt for the design stage."""
    blocks = [_section("User request", message)]
    if task_contract is not None:
        blocks.append(_section("Task Contract", render_task_contract_summary(task_contract)))
    blocks.extend(
        [
            _section("Discovery findings", discovery_text),
            "Task:\nProduce the best possible architecture, design, or documentation response for the user's request.",
            DOCUMENT_EXTRACTION_CONTRACT,
        ]
    )
    return "\n\n".join(blocks)


def build_summary_prompt(message: str, discovery_text: str, task_contract: TaskContract) -> str:
    """Build the runtime prompt for the summary stage."""
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Task Contract", render_task_contract_summary(task_contract)),
            _section("Grounded context and evidence", discovery_text),
            "Task:\nProduce the requested summary as the main answer.",
            "Summary rules:\n"
            "- Use only content that was read or directly supplied in the grounded context.\n"
            "- Start with summary content, not candidate ranking or retrieval caveats.\n"
            "- If source resolution was required, add a short Source Note after the summary.\n"
            "- Mention gaps only when they block the requested summary.\n"
            "- Do not add architecture/design recommendations unless the user asked for them.",
            DOCUMENT_EXTRACTION_CONTRACT,
        ]
    )


def build_review_prompt(
    message: str,
    discovery_text: str,
    design_text: str,
    task_contract: TaskContract | None = None,
) -> str:
    """Build the runtime prompt for the review stage."""
    blocks = [_section("User request", message)]
    if task_contract is not None:
        blocks.append(_section("Task Contract", render_task_contract_summary(task_contract)))
    draft_label = "Draft summary response" if task_contract and task_contract.is_summary else "Draft design response"
    blocks.extend(
        [
            _section("Discovery findings", discovery_text),
            _section(draft_label, design_text),
            "Task:\nCritically review the draft against the Task Contract when present.",
        ]
    )
    return "\n\n".join(blocks)


def build_pipeline_final_prompt(
    message: str,
    discovery_text: str,
    design_text: str,
    review_text: str,
    task_contract: TaskContract | None = None,
) -> str:
    """Build the runtime prompt for the pipeline final stage."""
    blocks = [_section("User request", message)]
    if task_contract is not None:
        blocks.append(_section("Task Contract", render_task_contract_summary(task_contract)))
    main_body_label = "Draft summary response" if task_contract and task_contract.is_summary else "Draft design response"
    main_body_guidance = (
        "- Use the summary output as the main body and preserve its answer-first structure.\n"
        "- Do not turn a summary request back into candidate selection or retrieval analysis.\n"
        if task_contract and task_contract.is_summary
        else "- Use the design output as the main body.\n"
    )
    blocks.extend(
        [
            _section("Discovery findings", discovery_text),
            _section(main_body_label, design_text),
            _section("Review feedback", review_text),
            "Task:\nProduce the final answer to the user.",
            "Handoff guidance:\n"
            + main_body_guidance
            + "- Incorporate review feedback only where it improves the answer.\n"
            + DOCUMENT_EXTRACTION_CONTRACT
            + "\n",
            "- do not mention internal pipeline stages unless the user explicitly asked to see them.",
        ]
    )
    return "\n\n".join(blocks)


def build_author_prompt(
    message: str,
    discovery_text: str,
    run_contract_text: str = "",
    *,
    deterministic_context: DeterministicRetrievalContext | None = None,
    deterministic_advisory_enabled: bool = False,
) -> str:
    """Build the runtime prompt for the author stage.

    This stage must remain isolated from later peer roles. The author receives
    the full user request, but must only produce the initial proposal or first
    draft. Later critique, refinement, judgement, and final packaging are
    handled by separate agents.
    """
    context = _resolve_deterministic_context(
        message,
        registry_dir=None,
        deterministic_context=deterministic_context,
    )
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Run contract", run_contract_text),
            _section("Deterministic retrieval context", _deterministic_handoff_block(context)),
            _section("Advisory MCP guidance", _advisory_mcp_guidance(deterministic_advisory_enabled)),
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
    *,
    deterministic_context: DeterministicRetrievalContext | None = None,
    deterministic_advisory_enabled: bool = False,
) -> str:
    """Build the runtime prompt for the challenger stage."""
    context = _resolve_deterministic_context(
        message,
        registry_dir=None,
        deterministic_context=deterministic_context,
    )
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Run contract", run_contract_text),
            _section("Draft", author_text),
            _section("Deterministic retrieval context", _deterministic_handoff_block(context)),
            _section("Advisory MCP guidance", _advisory_mcp_guidance(deterministic_advisory_enabled)),
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
    *,
    deterministic_context: DeterministicRetrievalContext | None = None,
    deterministic_advisory_enabled: bool = False,
) -> str:
    """Build the runtime prompt for the refiner stage."""
    context = _resolve_deterministic_context(
        message,
        registry_dir=None,
        deterministic_context=deterministic_context,
    )
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Run contract", run_contract_text),
            _section("Original draft", author_text),
            _section("Challenge", challenger_text),
            _section("Deterministic retrieval context", _deterministic_handoff_block(context)),
            _section("Advisory MCP guidance", _advisory_mcp_guidance(deterministic_advisory_enabled)),
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
    *,
    deterministic_context: DeterministicRetrievalContext | None = None,
    deterministic_advisory_enabled: bool = False,
) -> str:
    """Build the runtime prompt for the judge stage."""
    context = _resolve_deterministic_context(
        message,
        registry_dir=None,
        deterministic_context=deterministic_context,
    )
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Run contract", run_contract_text),
            _section("Challenge", challenger_text),
            _section("Refined draft", refiner_text),
            _section("Deterministic retrieval context", _deterministic_handoff_block(context)),
            _section("Advisory MCP guidance", _advisory_mcp_guidance(deterministic_advisory_enabled)),
            "Task:\nDecide whether the refined answer is good enough.",
            "Stage boundary:\n"
            "- You are only the judge stage in a peer workflow.\n"
            "- Do not rewrite the answer.\n"
            "- Do not simulate the orchestrator.\n"
            "- Do not output a peer transcript or final recommendation.\n"
            "- Output only the judgement, reasons, and any remaining issues.\n"
            "- Judge against run-contract dimensions first; reject outputs that are coherent but fail expected deliverable type.",
            "Decision contract:\n"
            "- First line must be exactly `Decision: accept`, `Decision: revise`, or `Decision: rework`.\n"
            "- Use `accept` when the refined draft is ready to ship.\n"
            "- Use `revise` when the same core proposal needs correction, strengthening, or clearer evidence handling.\n"
            "- Use `rework` when the core proposal, assumptions, option choice, structure, or evidence use is fundamentally wrong and needs a fresh author pass.",
        ]
    )


def build_judge_quality_gate_prompt(
    message: str,
    discovery_text: str,
    challenger_text: str,
    refiner_text: str,
    prior_judge_text: str,
    run_contract_text: str = "",
    *,
    deterministic_context: DeterministicRetrievalContext | None = None,
    deterministic_advisory_enabled: bool = False,
) -> str:
    """Build a strict acceptance-audit prompt for peer mode.

    This is a structural quality gate: when the initial judge decision is
    "accept", we run a second adjudication pass that specifically checks for
    silent information loss, weak evidence retention, and missing critical
    constraints.
    """
    context = _resolve_deterministic_context(
        message,
        registry_dir=None,
        deterministic_context=deterministic_context,
    )
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Run contract", run_contract_text),
            _section("Challenge", challenger_text),
            _section("Refined draft", refiner_text),
            _section("Initial judge output", prior_judge_text),
            _section("Deterministic retrieval context", _deterministic_handoff_block(context)),
            _section("Advisory MCP guidance", _advisory_mcp_guidance(deterministic_advisory_enabled)),
            "Task:\nRun a strict acceptance audit on the refined draft.",
            "Acceptance audit rules:\n"
            "- Compare the refined draft against discovery findings and challenge notes.\n"
            "- If material evidence present in discovery/challenge is omitted, weakened, or replaced with generic wording, return `Decision: revise`.\n"
            "- If critical constraints, implementation details, assumptions, risks, or retrieval gaps are missing despite being available in evidence, return `Decision: revise`.\n"
            "- If unsupported claims appear, return `Decision: revise`.\n"
            "- If the core proposal, assumptions, option choice, structure, or evidence use is fundamentally wrong, return `Decision: rework`.\n"
            "- If run contract expects concrete deliverables (files/code/final answer), do not accept outputs that are mainly process critique, uncertainty narration, or 'needs verification' checklists.\n"
            "- Return `Decision: accept` only when the refined draft preserves material evidence and is ready to ship.\n"
            "Output contract:\n"
            "- First line must be exactly `Decision: accept`, `Decision: revise`, or `Decision: rework`.\n"
            "- Then provide concise `Reason:` and, when revising or reworking, a `Missing or weak items:` bullet list.",
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


def build_context_synthesizer_prompt(
    message: str,
    discovery_text: str,
    task_contract: TaskContract | None = None,
) -> str:
    """Build a grounded prompt for the context synthesizer agent.

    The context_synthesizer stage is intentionally separate from both the retrieval
    planner and design: context_retrieval fetches sources from the planner handoff,
    while context_synthesizer converts that material into an evidence-led brief that
    a downstream design agent can use.
    """
    return f"""You are the Context Synthesizer agent in the crisAI workflow.

Your job is to transform retrieved source material into a concise, grounded context brief for a downstream solution design agent.

## Original user request

```text
{message}
```

## Task Contract

```text
{render_task_contract_summary(task_contract) if task_contract is not None else "None."}
```

## Context retrieval output

```text
{discovery_text}
```

## Task

Create a context brief that helps the next agent satisfy the Task Contract using only the information available in the context retrieval output.

## Rules

- Use only facts supported by the context retrieval output.
- Treat the `Validated Evidence Summary` section as authoritative when present.
- Preserve file names, paths, document titles, sections, links, citations, or other source references when they are available.
- Separate confirmed facts from assumptions and uncertainties.
- Remove irrelevant findings, duplication, and low-value noise.
- Do not invent missing details.
- Do not draft, recommend, or optimise the solution design.
- If the Task Contract asks for a summary, organise facts around answer-ready summary content and keep source-selection rationale separate.
- If the context retrieval output is empty, weak, or not relevant, say so clearly and explain what is missing.

## Runtime contracts

{RETRIEVAL_EVIDENCE_POLICY_CONTRACT}

{DOCUMENT_EXTRACTION_CONTRACT}

## Output format

```markdown
## Context Summary
A short paragraph explaining what relevant context was found and how strong the source basis is.

## Relevant Facts
- Fact: ...
  Source: ...

## Constraints and Dependencies
- Constraint/dependency: ...
  Source: ...

## Assumptions
- Assumption: ...
  Basis: ...

## Gaps and Uncertainties
- Gap/uncertainty: ...
  Why it matters: ...

## Source Notes
- Source: ...
  Relevance: ...
```
"""
