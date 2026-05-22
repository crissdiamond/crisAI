from __future__ import annotations

import pathlib

from crisai import config as config_module
from crisai.cli import prompt_contracts as prompt_contracts_module
from crisai.orchestration import retrieval_association_graph as graph_module
from crisai.orchestration import session_anchors as anchors_module
from crisai.orchestration import source_constraints as constraints_module
from crisai.orchestration import task_contract as task_module
from crisai.workspace import spaces as spaces_module


def _resolve_deterministic_context(
    message: str,
    *,
    registry_dir: pathlib.Path | None,
    deterministic_context: graph_module.DeterministicRetrievalContext | None = None,
) -> graph_module.DeterministicRetrievalContext:
    """Resolve the deterministic retrieval context.

    Args:
        message: The user query/message.
        registry_dir: Optional registry directory.
        deterministic_context: Pre-computed retrieval context if available.

    Returns:
        The resolved DeterministicRetrievalContext instance.
    """
    if deterministic_context is not None:
        return deterministic_context
    root = registry_dir if registry_dir is not None else config_module.load_settings().registry_dir
    graph = graph_module.load_retrieval_association_graph(root)
    return graph_module.build_deterministic_retrieval_context(message, graph)


def _retrieval_expansion_section(
    message: str,
    *,
    registry_dir: pathlib.Path | None,
    deterministic_context: graph_module.DeterministicRetrievalContext | None = None,
) -> str:
    """Pre-computed association-graph hints (empty when graph absent or no match).

    Args:
        message: The user query/message.
        registry_dir: Optional registry directory.
        deterministic_context: Pre-computed retrieval context if available.

    Returns:
        A string block representing the retrieval expansion section.
    """
    context = _resolve_deterministic_context(
        message,
        registry_dir=registry_dir,
        deterministic_context=deterministic_context,
    )
    return graph_module.format_retrieval_expansion_block(message, context=context)


def _deterministic_handoff_block(
    context: graph_module.DeterministicRetrievalContext,
    *,
    include_terms: bool = True,
) -> str:
    """Render a handoff block from a deterministic retrieval context.

    Args:
        context: The retrieval context instance.
        include_terms: Whether to list the query expansion terms.

    Returns:
        A string handoff block.
    """
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
    """Generate advisory MCP guidance instructions.

    Args:
        enabled: True if advisory MCP lookup is enabled.

    Returns:
        A string containing the guidance notes.
    """
    if not enabled:
        return "None."
    return (
        "Advisory lookup is enabled. You may call `expand_associations` for extra analysis context.\n"
        "- Advisory MCP output is optional and non-authoritative.\n"
        "- Do not override deterministic canonical context from workflow runtime.\n"
        "- If the tool fails or is unavailable, continue without it."
    )


def _is_intranet_scoped_request(message: str) -> bool:
    """Check if a user request is intranet-scoped.

    Args:
        message: The user message text.

    Returns:
        True if the request mentions intranet-related search markers.
    """
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
    """Check if a request implies workspace writing.

    Args:
        message: The user message text.

    Returns:
        True if the request contains write-oriented markers.
    """
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
    """Render a stable prompt section with trimmed content.

    Args:
        title: Section title.
        body: Section content body.

    Returns:
        A formatted section string.
    """
    clean = (body or "").strip() or "None."
    return f"{title}:\n{clean}"


def build_retrieval_planner_prompt(
    message: str,
    *,
    registry_dir: pathlib.Path | None = None,
    deterministic_context: graph_module.DeterministicRetrievalContext | None = None,
    task_contract: task_module.TaskContract | None = None,
    resolved_sources: tuple[anchors_module.ResolvedSourceReference, ...] = (),
) -> str:
    """Build the runtime prompt for the retrieval planner stage.

    The retrieval planner prepares a **retrieval handoff** for ``context_retrieval``. The CLI
    router already surfaces mode, pipeline shape, and retrieval intent, so this
    stage must not repeat that recap.

    Args:
        message: User text for this stage.
        registry_dir: Optional registry root; defaults to ``load_settings().registry_dir``.
        deterministic_context: Pre-computed retrieval context if available.
        task_contract: Derived task contract information.
        resolved_sources: Tuple of resolved source references from previous turn.

    Returns:
        The generated prompt string.
    """
    context = _resolve_deterministic_context(
        message,
        registry_dir=registry_dir,
        deterministic_context=deterministic_context,
    )
    source_constraints = constraints_module.infer_source_fit_constraints(message, registry_dir=registry_dir)
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
        blocks.append(_section("Task Contract", task_module.render_task_contract_summary(task_contract)))
    blocks.append(_section("Source Fit Constraints", constraints_module.render_source_fit_constraints(source_constraints)))
    if resolved_sources:
        blocks.append(_section("Resolved Session Sources", anchors_module.render_resolved_sources(resolved_sources)))
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
            "- If Resolved Session Sources are present, treat them as the preferred source identity from the prior turn. "
            "Use their source family, URL/path/content id, and title to retrieve the source again; do not assume a stale handle exists.\n"
            "- Do **not** retrieve or read source documents in this stage.\n"
            "- Provide only what helps search: 3–7 concrete angles (folders, doc "
            "types, product areas, keywords, standards IDs), ambiguities that change "
            "search strategy, and user constraints that materially affect retrieval.\n"
            "- Skip generic restatements of the user goal unless they add a retrieval "
            "signal the routing line did not cover.\n"
            "- When the user names explicit workspace-relative paths (for example "
            "``knowledge/patterns/foo.txt`` or ``tasks/<task>/artefacts/foo.md``), list them verbatim under **Paths to open** "
            "so the retrieval stage can call ``read_workspace_file`` immediately.\n"
            "- Respect active task isolation: use approved knowledge and active task artefacts only; do not search sibling ``tasks/`` sessions unless the user explicitly names those task paths.\n"
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
    registry_dir: pathlib.Path | None = None,
    deterministic_context: graph_module.DeterministicRetrievalContext | None = None,
    resolved_sources: tuple[anchors_module.ResolvedSourceReference, ...] = (),
) -> str:
    """Build the runtime prompt for single-mode retrieval-planner execution.

    In single mode, the retrieval planner agent is the terminal agent for retrieval-only asks, so
    it must perform retrieval now instead of only framing a downstream stage.

    Args:
        message: User text for this stage.
        registry_dir: Optional registry root; defaults to ``load_settings().registry_dir``.
        deterministic_context: Pre-computed retrieval context if available.
        resolved_sources: Tuple of resolved source references.

    Returns:
        The generated prompt string.
    """
    context = _resolve_deterministic_context(
        message,
        registry_dir=registry_dir,
        deterministic_context=deterministic_context,
    )
    source_constraints = constraints_module.infer_source_fit_constraints(message, registry_dir=registry_dir)
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
    blocks.append(_section("Source Fit Constraints", constraints_module.render_source_fit_constraints(source_constraints)))
    if resolved_sources:
        blocks.append(_section("Resolved Session Sources", anchors_module.render_resolved_sources(resolved_sources)))
    if expansion:
        blocks.append(expansion)
    blocks.extend(
        [
            "Task:\nPerform retrieval now and return concrete results for the user request.",
            "Execution rules:\n"
            "- Use available retrieval tools for OneDrive/SharePoint/workspace as needed.\n"
            "- If Resolved Session Sources are present, prefer those prior-turn source identities and re-search/refetch/read them with current tools.\n"
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
            prompt_contracts_module.SHAREPOINT_READ_HANDLE_CONTRACT,
            prompt_contracts_module.RETRIEVAL_EVIDENCE_POLICY_CONTRACT,
            prompt_contracts_module.LINK_FORMATTING_CONTRACT,
            prompt_contracts_module.EVIDENCE_BUNDLE_CONTRACT,
        ]
    )
    return "\n\n".join(blocks)


def build_context_retrieval_prompt(
    message: str,
    discovery_text: str,
    *,
    registry_dir: pathlib.Path | None = None,
    deterministic_context: graph_module.DeterministicRetrievalContext | None = None,
    task_contract: task_module.TaskContract | None = None,
    resolved_sources: tuple[anchors_module.ResolvedSourceReference, ...] = (),
) -> str:
    """Build the runtime prompt for the context retrieval stage.

    This stage performs source lookup only. It should return evidence and source
    references that the context stage can structure, without drafting the final
    design response.

    Args:
        message: User request text.
        discovery_text: Handoff text from the planner.
        registry_dir: Optional registry root path.
        deterministic_context: Pre-computed retrieval context if available.
        task_contract: Derived task contract details.
        resolved_sources: Tuple of resolved source references.

    Returns:
        The generated prompt string.
    """
    context = _resolve_deterministic_context(
        message,
        registry_dir=registry_dir,
        deterministic_context=deterministic_context,
    )
    spaces = spaces_module.load_workspace_spaces(registry_dir)
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
    source_constraints = constraints_module.infer_source_fit_constraints(message, registry_dir=registry_dir)
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
        blocks.append(_section("Task Contract", task_module.render_task_contract_summary(task_contract)))
    blocks.append(_section("Source Fit Constraints", constraints_module.render_source_fit_constraints(source_constraints)))
    if resolved_sources:
        blocks.append(_section("Resolved Session Sources", anchors_module.render_resolved_sources(resolved_sources)))
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
            "If Resolved Session Sources are present, use them as authoritative prior-turn source identity; re-search/refetch/read by title, URL/path, content id, and source family with current tools. "
            "Prefer context-specific retrieval tools such as build_context_index, search_context_chunks, and get_context_index_summary when available. "
            "If those tools are unavailable, list or search before reading files. "
            "When a **Deterministic retrieval expansion** block appears above, treat it as optional query hints from `registry/semantic_graph.yaml`; still validate fit to the user request. "
            "Workspace semantics:\n"
            "- ``search_workspace_text`` matches a **literal substring on one line**; long sentences often return nothing. "
            f"Use **short** queries (distinctive words or path fragments) or ``subdir`` scoped to ``{knowledge_root}`` / ``{knowledge_root}/patterns`` / the active task path, "
            "or call ``read_workspace_file`` / ``read_document`` when the user request or handoff names a concrete relative path.\n"
            f"- When in doubt, ``list_workspace_files('{knowledge_root}')`` (or a deeper subfolder) and the active task artefact folder, then open the best candidates.\n"
            "- Active task isolation: do not browse or search sibling ``tasks/`` sessions by fuzzy topic match. Use only the active task root, approved knowledge roots, or task paths explicitly named by the user.\n"
            + intranet_rules
            + "Return only grounded findings, source paths, relevant extracts, and any retrieval limitations. "
            "Do not create, update, or append workspace artefacts during retrieval; never call write-capable workspace tools from this stage. "
            "When source selection is needed, keep selection rationale short and make the read content prominent. "
            "Enforce Source Fit Constraints before reading: title phrases and user-scoped sources are hard filters, while deterministic expansion terms are optional hints. "
            "For SharePoint (not OneDrive-only) use `search_sharepoint_site_documents` or site-scoped search after `list_sites`. "
            "When the user asks for a summary of a document/deck/file, read the content first and mark the item `content_read`; if the read fails, mark it `read_failed` and include the raw error. "
            "For document/deck/file summary requests, always end with the required fenced `evidence_bundle_v1` JSON block; never rely on prose-only retrieval notes. "
            "Do not draft, recommend, or optimise the final design response.",
            prompt_contracts_module.SHAREPOINT_READ_HANDLE_CONTRACT,
            prompt_contracts_module.RETRIEVAL_EVIDENCE_POLICY_CONTRACT,
            prompt_contracts_module.LINK_FORMATTING_CONTRACT,
            prompt_contracts_module.EVIDENCE_BUNDLE_CONTRACT,
        ]
    )
    return "\n\n".join(blocks)


def build_context_retrieval_repair_prompt(
    message: str,
    retrieval_plan_text: str,
    invalid_output: str,
    validation_error: str,
) -> str:
    """Build a generic retry prompt for invalid retrieval evidence transport.

    Args:
        message: User request text.
        retrieval_plan_text: The retrieval handoff / plan text.
        invalid_output: The previous output that failed validation.
        validation_error: The validation error string.

    Returns:
        The generated prompt string.
    """
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
            prompt_contracts_module.SHAREPOINT_READ_HANDLE_CONTRACT,
            prompt_contracts_module.RETRIEVAL_EVIDENCE_POLICY_CONTRACT,
            prompt_contracts_module.EVIDENCE_BUNDLE_CONTRACT,
        ]
    )


def build_design_prompt(
    message: str,
    discovery_text: str,
    task_contract: task_module.TaskContract | None = None,
) -> str:
    """Build the runtime prompt for the design stage.

    Args:
        message: User request text.
        discovery_text: Context synthesised evidence brief.
        task_contract: Derived task contract details.

    Returns:
        The generated prompt string.
    """
    blocks = [_section("User request", message)]
    if task_contract is not None:
        blocks.append(_section("Task Contract", task_module.render_task_contract_summary(task_contract)))
    blocks.extend(
        [
            _section("Discovery findings", discovery_text),
            "Task:\nProduce the best possible architecture, design, or documentation response for the user's request.",
            prompt_contracts_module.DOCUMENT_EXTRACTION_CONTRACT,
        ]
    )
    return "\n\n".join(blocks)


def build_summary_prompt(
    message: str,
    discovery_text: str,
    task_contract: task_module.TaskContract,
) -> str:
    """Build the runtime prompt for the summary stage.

    Args:
        message: User request text.
        discovery_text: Grounded context and evidence.
        task_contract: Derived task contract details.

    Returns:
        The generated prompt string.
    """
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Task Contract", task_module.render_task_contract_summary(task_contract)),
            _section("Grounded context and evidence", discovery_text),
            "Task:\nProduce the requested summary as the main answer.",
            "Summary rules:\n"
            "- Use only content that was read or directly supplied in the grounded context.\n"
            "- Start with summary content, not candidate ranking or retrieval caveats.\n"
            "- If source resolution was required, add a short Source Note after the summary.\n"
            "- Mention gaps only when they block the requested summary.\n"
            "- Do not add architecture/design recommendations unless the user asked for them.",
            prompt_contracts_module.DOCUMENT_EXTRACTION_CONTRACT,
        ]
    )


def build_review_prompt(
    message: str,
    discovery_text: str,
    design_text: str,
    task_contract: task_module.TaskContract | None = None,
) -> str:
    """Build the runtime prompt for the review stage.

    Args:
        message: User request text.
        discovery_text: Discovery/retrieval findings.
        design_text: Draft design response text.
        task_contract: Derived task contract details.

    Returns:
        The generated prompt string.
    """
    blocks = [_section("User request", message)]
    if task_contract is not None:
        blocks.append(_section("Task Contract", task_module.render_task_contract_summary(task_contract)))
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
    task_contract: task_module.TaskContract | None = None,
) -> str:
    """Build the runtime prompt for the pipeline final stage.

    Args:
        message: User request text.
        discovery_text: Grounded context findings.
        design_text: Draft design response text.
        review_text: Review feedback text.
        task_contract: Derived task contract details.

    Returns:
        The generated prompt string.
    """
    blocks = [_section("User request", message)]
    if task_contract is not None:
        blocks.append(_section("Task Contract", task_module.render_task_contract_summary(task_contract)))
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
            + prompt_contracts_module.DOCUMENT_EXTRACTION_CONTRACT
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
    deterministic_context: graph_module.DeterministicRetrievalContext | None = None,
    deterministic_advisory_enabled: bool = False,
) -> str:
    """Build the runtime prompt for the author stage.

    This stage must remain isolated from later peer roles. The author receives
    the full user request, but must only produce the initial proposal or first
    draft. Later critique, refinement, judgement, and final packaging are
    handled by separate agents.

    Args:
        message: User request text.
        discovery_text: Discovery findings.
        run_contract_text: Run contract guidelines.
        deterministic_context: Canonical retrieval context.
        deterministic_advisory_enabled: Whether advisory lookup is enabled.

    Returns:
        The generated prompt string.
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
    deterministic_context: graph_module.DeterministicRetrievalContext | None = None,
    deterministic_advisory_enabled: bool = False,
) -> str:
    """Build the runtime prompt for the challenger stage.

    Args:
        message: User request text.
        discovery_text: Discovery findings.
        author_text: Author's initial draft.
        run_contract_text: Run contract guidelines.
        deterministic_context: Canonical retrieval context.
        deterministic_advisory_enabled: Whether advisory lookup is enabled.

    Returns:
        The generated prompt string.
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
    deterministic_context: graph_module.DeterministicRetrievalContext | None = None,
    deterministic_advisory_enabled: bool = False,
) -> str:
    """Build the runtime prompt for the refiner stage.

    Args:
        message: User request text.
        discovery_text: Discovery findings.
        author_text: Author's draft.
        challenger_text: Challenger's critique.
        run_contract_text: Run contract guidelines.
        deterministic_context: Canonical retrieval context.
        deterministic_advisory_enabled: Whether advisory lookup is enabled.

    Returns:
        The generated prompt string.
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
    deterministic_context: graph_module.DeterministicRetrievalContext | None = None,
    deterministic_advisory_enabled: bool = False,
) -> str:
    """Build the runtime prompt for the judge stage.

    Args:
        message: User request.
        discovery_text: Discovery findings.
        challenger_text: Challenger's critique.
        refiner_text: Refiner's improved draft.
        run_contract_text: Run contract guidelines.
        deterministic_context: Canonical retrieval context.
        deterministic_advisory_enabled: Whether advisory lookup is enabled.

    Returns:
        The generated prompt string.
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
    deterministic_context: graph_module.DeterministicRetrievalContext | None = None,
    deterministic_advisory_enabled: bool = False,
) -> str:
    """Build a strict acceptance-audit prompt for peer mode.

    This is a structural quality gate: when the initial judge decision is
    "accept", we run a second adjudication pass that specifically checks for
    silent information loss, weak evidence retention, and missing critical
    constraints.

    Args:
        message: User request text.
        discovery_text: Discovery findings.
        challenger_text: Challenger's critique.
        refiner_text: Refined draft.
        prior_judge_text: Original judge output.
        run_contract_text: Run contract guidelines.
        deterministic_context: Canonical retrieval context.
        deterministic_advisory_enabled: Whether advisory lookup is enabled.

    Returns:
        The generated prompt string.
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
    """Build the runtime prompt for the peer final stage.

    Args:
        message: User request text.
        discovery_text: Discovery findings.
        author_text: Author's initial draft.
        challenger_text: Challenger's critique.
        refiner_text: Refiner's improved draft.
        judge_text: Judge decision text.
        run_contract_text: Run contract guidelines.
        runtime_changed_files_text: Workspace-changed files.

    Returns:
        The generated prompt string.
    """
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
    task_contract: task_module.TaskContract | None = None,
) -> str:
    """Build a grounded prompt for the context synthesizer agent.

    The context_synthesizer stage is intentionally separate from both the retrieval
    planner and design: context_retrieval fetches sources from the planner handoff,
    while context_synthesizer converts that material into an evidence-led brief that
    a downstream design agent can use.

    Args:
        message: User request text.
        discovery_text: Context retrieval findings.
        task_contract: Derived task contract details.

    Returns:
        The generated prompt string.
    """
    return f"""You are the Context Synthesizer agent in the crisAI workflow.

Your job is to transform retrieved source material into a concise, grounded context brief for a downstream solution design agent.

## Original user request

```text
{message}
```

## Task Contract

```text
{task_module.render_task_contract_summary(task_contract) if task_contract is not None else "None."}
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

{prompt_contracts_module.RETRIEVAL_EVIDENCE_POLICY_CONTRACT}

{prompt_contracts_module.DOCUMENT_EXTRACTION_CONTRACT}

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
