## Objective
Build **draft** architecture-context artefacts for **integration principles**, **high-level design (HLD)**, and **low-level design (LLD)** from UCL IT Architecture **intranet Site Pages only** (see `registry/intranet.yaml`). Stage files only under **`workspace/context_staging/`**, using the layout you intend after promotion:

- **Principles** → `workspace/context_staging/principles/` (`type: principle`)
- **High-level integration design** → `workspace/context_staging/designs/` (`type: high_level_design` — you may write `type: HLD` in front matter; it is treated as `high_level_design` for validation)
- **Low-level integration design** → `workspace/context_staging/designs/` (`type: low_level_design` — you may write `type: LLD`)

Use **peer mode** for this run so author → challenger → refiner → judge → final orchestrator all execute.

## Hard constraints
- Sources must be intranet MCP tools only (`intranet_search`, `intranet_list_all_pages`, `intranet_list_page_links`, `intranet_fetch`).
- Do not use SharePoint document libraries (`search_sharepoint_site_documents`) or generic web sources for facts.
- Every factual statement must be grounded in a successful `intranet_fetch` for the same page, and each authored file must expose those sources in **`## Source`**.
- If evidence is missing, omit the claim or record it in retrieval gaps; do not guess.
- Keep output in **British English** and markdown with concise `##` sections.
- Do not transfer content across pages with similar titles (for example two different “Integration strategy” pages). Each file must reflect only the **exact** fetched page(s) used for that file.
- Claims such as “not stated”, “brief summary”, or “no details available” are allowed only when supported by explicit fetched evidence.

## Peer pipeline and artefact validator (must pass)
After the judge accepts, the run applies **filesystem + artefact profile checks** (`registry/workspace_artifact_profiles.yaml` via `src/crisai/orchestration/peer_verifier.py`). A failed check aborts the run.

Obey these rules so validation passes:

1. **Default front matter (every authored `.md` in this exercise)**  
   Include: `id`, `title`, `type`, `status` (`draft`), `owner` (`Architecture`), `related:` only paths that already exist under `workspace/context/` (otherwise `related: []`).

2. **`type: principle` files** under `workspace/context_staging/principles/*.md`  
   Required level-2 headings **verbatim**:
   - `## Scope`
   - `## Statement`
   - `## Implications`  
   Also include **`## Source`** (URLs and optional Graph ids). You may add further sections if grounded.

3. **`type: high_level_design` files** under `workspace/context_staging/designs/*.md`  
   Required level-2 headings **verbatim**:
   - `## Context`
   - `## Target architecture`
   - `## Key decisions`  
   Also include **`## Source`**.

4. **`type: low_level_design` files** under `workspace/context_staging/designs/*.md`  
   Required level-2 headings **verbatim**:
   - `## Design overview`
   - `## Components and interfaces`
   - `## Deployment and operations`  
   Also include **`## Source`**.

5. **Retrieval gaps file (if needed):** name with `*retrieval-gaps*.md` (recommended: `integration-principles-retrieval-gaps.md`). You may place it under `principles/` or `designs/`; it matches the relaxed **retrieval_gaps** profile when the filename contains `retrieval-gaps`.

6. **Final orchestrator close-out:** the last assistant message must list **every** `workspace/.../*.md` file created or updated by full repo-relative path (peer verifier).

Optional pre-check: `crisai validate-artefacts -p workspace/context_staging/principles/<file>.md` (and the same for `designs/`).

## Task 0 — Baseline reading
Read:

- `workspace/context/README.md` (folder intent and metadata field reference)
- `prompts/_shared/context-staging.md` (catalogue vs leaf behaviour)
- `registry/workspace_artifact_profiles.yaml` (required headings per `type`)

Do **not** recycle approved corpus text from `workspace/context/` as **source facts** for new claims (reading templates or README for shape is fine).

## Task 1 — Discover authoritative intranet pages
There is no single mandated catalogue URL for “integration principles / HLD / LLD” across tenants. Discover pages using **evidence-first** steps:

1. `intranet_search` with focused queries (for example `integration principles`, `integration strategy`, `target architecture`, `high level design`, `detailed design`, `integration standards`).
2. `intranet_list_all_pages(query="<short keywords>")` when you need breadth (title and slug token matching, no OData-only cap).
3. For each **hub or index** page you fetch, call **`intranet_list_page_links`** on its `graph_site_id` / `graph_page_id`, then **`intranet_fetch`** on linked detail pages that carry the actual principle or design content.

Reject treating **navigation-only** snippets as full sources: if a page is only a link farm with no substantive body, fetch the linked leaves or record a gap.

## Task 2 — Classify and evidence-bind
For each candidate page you might author from:

- classify as **principle-oriented**, **high-level design-oriented**, or **low-level design-oriented** (some pages may support more than one artefact—still **do not** duplicate claims across files without distinct fetches and clear scope);
- capture an **evidence card** before writing each file:
  - working title for the artefact
  - `web_url`, `graph_site_id`, `graph_page_id`
  - 2–4 short **verbatim** excerpts that justify the sections you will write.

If a page’s title says “principle” but the body is empty, duplicate, or clearly belongs to another topic, record that under retrieval gaps rather than inventing content.

## Task 3 — Author files, naming, and dedup
Write only with `write_workspace_file` under the staging paths above.

**Principles (`principles/`)**  
- One topic per file where possible.  
- Filename convention: `integration-principle-<short-topic-slug>.md` (lowercase, hyphenated).  
- `type: principle`  
- Stable ids: `PRIN-INT-001`, increment without reuse.

**High-level design (`designs/`)**  
- Filename convention: `integration-hld-<short-topic-slug>.md`  
- `type: high_level_design` (or `type: HLD`)  
- Stable ids: `HLD-INT-001`, increment without reuse.

**Low-level design (`designs/`)**  
- Filename convention: `integration-lld-<short-topic-slug>.md`  
- `type: low_level_design` (or `type: LLD`)  
- Stable ids: `LLD-INT-001`, increment without reuse.

**Dedup invariant**  
- At most **one** staging file per **primary slug** for each kind (`integration-principle-*`, `integration-hld-*`, `integration-lld-*`). If a file already exists for the same topic, **update** it instead of creating a parallel name.

**Optional index**  
- You may add one index file (for example `integration-architecture-context-index.md`) with `type: design` or `type: principle` depending on its role; if you use `type: design`, the validator expects `## Overview` among defaults—prefer a **short index** that only points to staged files and sources, or use `type: principle` with Scope/Statement/Implications filled honestly. If an index would be misleading, omit it.

## Task 4 — Retrieval gaps honesty block
If anything cannot be resolved from intranet pages after reasonable attempts:

```markdown
## Retrieval gaps
- <Topic or page name>: <attempts: list_page_links / search / fetch> -> <outcome>
```

## Task 5 — Close-out validation
Before final response:

- list files created/updated (all `workspace/...` paths);
- map each file to the `web_url`(s) used;
- verify required `##` headings per `type` and **`## Source`** on every artefact;
- verify stable `id` uniqueness across all new files in this run;
- show evidence card linkage per file (title + graph ids);
- ensure the **final orchestrator** lists every changed markdown path.

Done when close-out matches files on disk.
