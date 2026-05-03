# Context staging (draft corpus)

Rules for **curated architecture context** files (principles, patterns, standards, landscape, decisions, intake)—not general design deliverables under `outputs/`.

## Write location

- Put **new** or **refreshed** context-style artefacts under **`workspace/context_staging/`** only.
- **Mirror** the intended final path: e.g. `context_staging/patterns/integration-patterns-from-intranet.txt` so reviewers know where it should land in `context/` after approval.
- Do **not** use `write_workspace_file` / `append_workspace_file` targets under **`workspace/context/`** for agent-generated drafts unless the user **explicitly** asks to publish or overwrite the canonical tree.

## Metadata

- Use **`status: draft`** in YAML front matter unless the user explicitly approved publication.
- Prefer **`source_url:`** (or a short **provenance** line in the body) when content comes from intranet pages or other external sources.

## Reads and retrieval

- **Approved** corpus for grounding remains **`workspace/context/`**. Continue to **read**, **cite**, and **search** there during normal retrieval.
- Do not assume `context_staging/` is indexed for production retrieval unless the user scoped the task to drafts.

## Exceptions

- If the user says **publish to context**, **save directly under context/**, or names an **existing** `context/...` path to update, follow that instruction.
