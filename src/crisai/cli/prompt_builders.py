from __future__ import annotations


def build_discovery_prompt(message: str) -> str:
    return f"""
User request:
{message}

Task:
Inspect the available sources and retrieve the most relevant material for this request.

Rules:
- For workspace sources, all paths must be relative to the workspace root.
- Never guess file paths, site names, drive IDs, item IDs, or document IDs.
- Always list or search before reading.
- Only read a path or item returned by a listing/search tool in this run.
- For supported document formats such as .docx, .pdf, .pptx, .xlsx, use the document-reading tools.
- For plain text files, use workspace text reads where appropriate.
- Use SharePoint tools when the relevant information may be in SharePoint.
- When using SharePoint, first check auth status and authenticate if needed before searching.
- Never assume SharePoint auth is already warm.
- Use get_document_metadata or get_sharepoint_document_metadata only if needed, and only with a valid item returned in this run.
- If a tool fails, report the exact tool name and exact error.
- Do not claim you inspected or read a source unless a tool call succeeded.

Return:
1. relevant sources with exact paths or identifiers
2. extracted facts
3. assumptions
4. constraints
5. decisions already present
6. missing information
7. exact tool errors, if any
"""


def build_design_prompt(message: str, discovery_text: str) -> str:
    return f"""
User request:
{message}

Discovery findings:
{discovery_text}

Task:
Produce the best possible architecture, design, or documentation response for the user's request.

Rules:
- Treat the discovery findings as the authoritative retrieval result for this run.
- Do not invent or reopen file paths unless discovery explicitly identified them.
- If discovery found no reliable sources, say so and work only from the verified findings provided.
- Where a diagram would help, generate Mermaid.
"""


def build_review_prompt(message: str, discovery_text: str, design_text: str) -> str:
    return f"""
User request:
{message}

Discovery findings:
{discovery_text}

Draft design response:
{design_text}

Task:
Critically review the draft.

Rules:
- Treat discovery findings as the factual basis for this review.
- Do not invent additional files, SharePoint items, or file contents.
- If discovery reported tool failures or missing retrieval, take that into account.

Highlight:
- governance gaps
- ownership gaps
- NFR or assurance gaps
- delivery risks
- suggested improvements
"""


def build_pipeline_final_prompt(message: str, discovery_text: str, design_text: str, review_text: str) -> str:
    return f"""
User request:
{message}

Discovery findings:
{discovery_text}

Draft design response:
{design_text}

Review feedback:
{review_text}

Task:
Produce the final answer to the user.
Use the design output as the main body, but improve it using the review feedback where relevant.
Do not mention internal pipeline stages unless the user explicitly asked for them.
"""


def build_author_prompt(message: str, discovery_text: str) -> str:
    return f"""
User request:
{message}

Discovery findings:
{discovery_text}

Task:
Produce the best possible first draft for the user's request.

Rules:
- Treat discovery findings as the authoritative retrieval result for this run.
- Do not invent file paths or source content.
- Where a diagram would help, generate Mermaid.
"""


def build_challenger_prompt(message: str, discovery_text: str, author_text: str) -> str:
    return f"""
User request:
{message}

Discovery findings:
{discovery_text}

Draft:
{author_text}

Task:
Critique the draft rigorously.

Rules:
- Work only from the user request, discovery findings, and the draft.
- Do not invent evidence or file contents.
- Do not rewrite the draft directly.

Check for:
- missing assumptions
- governance gaps
- ownership ambiguity
- unsupported claims
- NFR or assurance gaps
- delivery risks
- missing options or trade-offs
- poor structure or unclear recommendation

Output:
- strengths
- weaknesses
- required corrections
- optional improvements
- final verdict: revise / acceptable
"""


def build_refiner_prompt(message: str, discovery_text: str, author_text: str, challenger_text: str) -> str:
    return f"""
User request:
{message}

Discovery findings:
{discovery_text}

Original draft:
{author_text}

Challenge:
{challenger_text}

Task:
Refine the draft using the critique.

Rules:
- Keep the useful parts of the original draft.
- Correct the weaknesses identified by the challenger.
- Do not invent evidence or file contents.
- Keep the answer practical and clear.
"""


def build_judge_prompt(message: str, discovery_text: str, challenger_text: str, refiner_text: str) -> str:
    return f"""
User request:
{message}

Discovery findings:
{discovery_text}

Challenge:
{challenger_text}

Refined draft:
{refiner_text}

Task:
Decide whether the refined answer is good enough.

Rules:
- Work only from the user request, discovery findings, critique, and refined answer.
- Do not invent new evidence.
- Be decisive.

Check:
- relevance to the request
- fidelity to the evidence
- whether major critique points were addressed
- whether the answer is clear, useful, and internally consistent

Output:
- decision: accept / revise
- reason
- remaining issues, if any
"""


def build_peer_final_prompt(
    message: str,
    discovery_text: str,
    author_text: str,
    challenger_text: str,
    refiner_text: str,
    judge_text: str,
) -> str:
    return f"""
User request:
{message}

Discovery findings:
{discovery_text}

Original draft:
{author_text}

Challenge:
{challenger_text}

Refined draft:
{refiner_text}

Judge decision:
{judge_text}

Task:
Produce the final answer to the user.

Rules:
- Use the refined draft as the main body.
- Incorporate only improvements justified by the critique and judge decision.
- Do not mention internal peer stages unless the user explicitly asked for them.
"""
