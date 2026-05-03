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

## Intranet catalogues vs pattern detail pages

Many intranet **pattern**, **standard**, or **guidance** areas use a **catalogue page** (a table or list of names) and **separate Site Pages** for each item’s **rationale**, **when to use**, and **constraints**.

When building **`context_staging/`** from intranet sources:

1. Treat the first **`intranet_fetch`** on a catalogue page as **inventory only** unless that single page already contains full detail for every item.
2. **Drill down before writing:** run **`intranet_list_page_links`** on the catalogue page’s `graph_site_id` / `graph_page_id`, then **`intranet_fetch`** on each linked **Site Page** that corresponds to a listed pattern (or obvious child topic). If **`intranet_list_page_links`** returns too few links (Quick Links / other web parts), use **`intranet_search`** with distinctive tokens from each list row (pattern id, slug, or key phrase) and **`intranet_fetch`** the best matching **leaf** pages.
3. **Deliverable shape:** either **one file per pattern** under `context_staging/patterns/` (preferred when each leaf page is long), or **one file with a `##` section per pattern** where each section’s body is **summarised only from that pattern’s `intranet_fetch`** (not from the catalogue list alone). Include **## Source** per section with that page’s `web_url`.
4. Do **not** ship a “complete” pattern corpus that only restates **names** from the catalogue unless the user explicitly asked for an **index-only** artefact.

## Exceptions

- If the user says **publish to context**, **save directly under context/**, or names an **existing** `context/...` path to update, follow that instruction.
