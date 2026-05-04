# Context staging (draft corpus)

Rules for **curated architecture context** drafts staged before publication to `workspace/context/`.

This includes (non-exhaustive): templates, solution notes, design notes, patterns, standards, guidelines, references, principles, landscape maps, decisions, and intake artefacts.

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

## Intranet catalogues and detail pages

Many intranet **architecture knowledge areas** (patterns, standards, guidelines, templates, references, etc.) use a **catalogue page** (inventory/list) and **separate detail pages** for each entry’s rationale, constraints, implementation detail, examples, ownership, or lifecycle status.

When building **`context_staging/`** from intranet sources:

1. Treat the first **`intranet_fetch`** on a catalogue page as **inventory only** unless that page already contains complete detail for every listed item.
2. **Drill down before writing:** run **`intranet_list_page_links`** on the catalogue page (`graph_site_id` / `graph_page_id`), then **`intranet_fetch`** on linked detail pages that map to listed items. If links are sparse (for example, Quick Links/web-part limits), use **`intranet_search`** with item-specific tokens (name, id, slug, distinctive phrase), then fetch the best matching leaf pages.
3. **Deliverable shape:** choose one file per item (under the relevant staged folder such as `patterns/`, `standards/`, `guidelines/`, `templates/`, `reference/`) or one grouped file with clear per-item `##` sections. Every substantive section must be grounded in the corresponding leaf fetch, not only in catalogue names.
4. Do **not** claim a complete corpus when output only restates inventory labels from the catalogue. If details are missing, create an explicit gaps/limitations block with what was tried and outcome.

## Exceptions

- If the user says **publish to context**, **save directly under context/**, or names an **existing** `context/...` path to update, follow that instruction.
