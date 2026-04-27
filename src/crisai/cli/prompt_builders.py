from __future__ import annotations


def _section(title: str, body: str) -> str:
    """Render a stable prompt section with trimmed content."""
    clean = (body or "").strip() or "None."
    return f"{title}:\n{clean}"


def build_discovery_prompt(message: str) -> str:
    """Build the runtime prompt for the discovery stage.

    Discovery should classify and frame the request. Retrieval is handled by the
    dedicated context_retrieval stage so that source lookup remains observable
    and independently tunable.
    """
    return "\n\n".join(
        [
            _section("User request", message),
            "Task:\nFrame the request for the downstream workflow. Identify the user goal, likely output type, and what knowledge areas may need retrieval. Do not retrieve or read source documents in this stage.",
        ]
    )


def build_single_discovery_prompt(message: str) -> str:
    """Build the runtime prompt for single-mode discovery execution.

    In single mode, discovery is the terminal agent for retrieval-only asks, so
    it must perform retrieval now instead of only framing a downstream stage.
    """
    return "\n\n".join(
        [
            _section("User request", message),
            "Task:\nPerform retrieval now and return concrete results for the user request.",
            "Execution rules:\n"
            "- Use available retrieval tools for OneDrive/SharePoint/workspace as needed.\n"
            "- Authenticate when required (for example interactive Microsoft Entra login when cached tokens are missing or expired).\n"
            "- List or search first, then inspect only matching results.\n"
            "- Do not return a planning brief, workflow framing, or clarifying questionnaire unless the request is truly ambiguous.\n"
            "- Return grounded results with file names/paths and concise relevance notes.\n"
            "- For each file, output exactly `[file_name](url)` so only the **file name** is visible and the **URL is only in the href** "
            "(do not paste the raw URL as visible text). "
            "Graph: basename from tool row + `open_url`/`webUrl`. Workspace: basename + `file_uri` from `search_workspace_text` or `workspace_file_link`.",
        ]
    )


def build_context_retrieval_prompt(message: str, discovery_text: str) -> str:
    """Build the runtime prompt for the context retrieval stage.

    This stage performs source lookup only. It should return evidence and source
    references that the context stage can structure, without drafting the final
    design response.
    """
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery framing", discovery_text),
            "Task:\nRetrieve the most relevant material for this request from available context sources. "
            "Prefer context-specific retrieval tools such as build_context_index, search_context_chunks, and get_context_index_summary when available. "
            "If those tools are unavailable, list or search before reading files. "
            "Return only grounded findings, source paths, relevant extracts, and any retrieval limitations. "
            "For each source row, include **Link:** `[file_name](url)` only — visible text is the **file name**, URL **only** inside parentheses; do not duplicate the URL as plain text. "
            "Graph: use `open_url`/`webUrl`; workspace: use `file_uri` from `search_workspace_text` or `workspace_file_link`. "
            "Do not draft, recommend, or optimise the final design response.",
        ]
    )


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


def build_author_prompt(message: str, discovery_text: str) -> str:
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
            "Task:\nProduce the best possible first draft for the user's request.",
            "Stage boundary:\n"
            "- You are only the author stage in a peer workflow.\n"
            "- Do not simulate the challenger, refiner, judge, or orchestrator.\n"
            "- Do not output a peer transcript or role-labelled conversation.\n"
            "- Do not include sections such as 'Challenger', 'Refiner', 'Judge', 'Peer conversation', or 'Final recommendation'.\n"
            "- Output only the initial draft or proposal that later peer stages will inspect.",
        ]
    )


def build_challenger_prompt(message: str, discovery_text: str, author_text: str) -> str:
    """Build the runtime prompt for the challenger stage."""
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Draft", author_text),
            "Task:\nCritique the draft rigorously.",
            "Stage boundary:\n"
            "- You are only the challenger stage in a peer workflow.\n"
            "- Do not rewrite the draft directly.\n"
            "- Do not simulate the refiner, judge, or orchestrator.\n"
            "- Do not output a peer transcript or final recommendation.\n"
            "- Output only critique for later stages to use.",
        ]
    )


def build_refiner_prompt(message: str, discovery_text: str, author_text: str, challenger_text: str) -> str:
    """Build the runtime prompt for the refiner stage."""
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Original draft", author_text),
            _section("Challenge", challenger_text),
            "Task:\nRefine the draft using the critique.",
            "Stage boundary:\n"
            "- You are only the refiner stage in a peer workflow.\n"
            "- Do not simulate the judge or orchestrator.\n"
            "- Do not output a peer transcript or final recommendation.\n"
            "- Output only the improved draft that should be judged next.",
        ]
    )


def build_judge_prompt(message: str, discovery_text: str, challenger_text: str, refiner_text: str) -> str:
    """Build the runtime prompt for the judge stage."""
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
            _section("Challenge", challenger_text),
            _section("Refined draft", refiner_text),
            "Task:\nDecide whether the refined answer is good enough.",
            "Stage boundary:\n"
            "- You are only the judge stage in a peer workflow.\n"
            "- Do not rewrite the answer.\n"
            "- Do not simulate the orchestrator.\n"
            "- Do not output a peer transcript or final recommendation.\n"
            "- Output only the judgement, reasons, and any remaining issues.",
        ]
    )


def build_peer_final_prompt(
    message: str,
    discovery_text: str,
    author_text: str,
    challenger_text: str,
    refiner_text: str,
    judge_text: str,
) -> str:
    """Build the runtime prompt for the peer final stage."""
    return "\n\n".join(
        [
            _section("User request", message),
            _section("Discovery findings", discovery_text),
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
            "- Do not mention internal peer stages unless the user explicitly asked to see them.",
        ]
    )
