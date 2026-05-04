## Objective
Build crisAI **architecture-context** artefacts from the UCL IT Architecture **intranet Site Pages only** (see `registry/intranet.yaml`). Deliver **draft** files under **`workspace/context_staging/`** only, mirroring the layout you intend under `workspace/context/` (e.g. `context_staging/patterns/`).

## Hard constraints
- **Sources:** Intranet MCP only (`intranet_search`, `intranet_list_page_links`, `intranet_fetch`, etc. as exposed). **Do not** use SharePoint **document libraries** (`search_sharepoint_site_documents`). **Do not** use generic web search for source facts.
- **No recycling approved corpus:** Do **not** copy source text from `workspace/context/` except to read **`workspace/context/README.md`** and **`workspace/context/_templates/artefact-template.txt`** for format rules.
- **Grounding:** Every factual bullet must come from a successful **`intranet_fetch`** of the page cited in **`## Source`** for that bullet. If the fetch does not support a claim, **omit** it (do not guess). You may add a clearly labelled **`## Inferences (not from source)`** section only if strictly necessary; prefer omit.
- **Language:** British English.
- **Files:** UTF-8 **`.md`** or **`.txt`**; **`##` headings** and short bullets.

## Task 0 — Baseline format (read-only)
**Do:** Read `workspace/context/README.md` (metadata block) and `workspace/context/_templates/artefact-template.txt`.  
**Done when:** You know required front matter fields: `id`, `title`, `type`, `status`, plus sensible `owner`, `last_reviewed` (today’s date), `applies_to`, `tags`, `related`.

**Front matter rules:**
- `status: draft` for all new files.
- `type: pattern` for integration patterns.
- Stable `id` values (e.g. `PATT-INT-001`, increment per file).
- **`related:`** lists **only** repo paths that **exist** under `workspace/context/`; if none, use `related: []`. (Cross-links to other staging files go in the **body**, not `related`, unless you adopt a project convention that allows it.)

**Body sections (each file):**
- `## Source` — page **title** and **`web_url` / `open_url`** from the fetch used for that file’s grounded content (no secrets).
- `## Design overview` — structured metadata from the fetched page: pattern name, one-line description, version/status/date (if stated), classification (source, target, delivery mode), NFRs (observability, reliability, reconciliation, operational limits), and any security constraints. Include only fields the fetched text explicitly supports; omit the rest.
- `## When to use`
- `## Implementation` structured metadata from the fetched page: low level implementation, list of components and flow.
- `## Anti-patterns or when not to use` — only if the **fetched** text supports them.
- `## References` — intranet links only (from fetches or link lists).

---

## Task 1 — Find the catalogue page
**Do:** Search for the page whose URL slug is **`integration-patterns.aspx`** (all lowercase, no number suffix). Use `intranet_search` with query `integration-patterns` then check the `web_url` of every result. If the slug is not in the search results, call `intranet_list_all_pages(query="integration pattern")` and filter for an entry whose `web_url` ends with `/SitePages/integration-patterns.aspx`. Fetch that page with `intranet_fetch`.

**Catalogue imposters to reject** — if you land on any of these pages, discard them and keep searching:
- `allPatterns.aspx` — generic pattern library (not integration-specific)
- `Integration-Patterns(1).aspx` — integration architecture overview, not the leaf catalogue
- `Architecture-Patterns.aspx` — thematic browse page

**Done when:** You have an `intranet_fetch` of **`integration-patterns.aspx`** (lowercase) whose body enumerates all three groups with numbered leaf patterns: Consumer (0–4), Producer (1–3), Ingestion (1–3). A page that lists fewer than 10 numbered patterns is not the catalogue.

---

## Task 2 — Discover leaf pages (mandatory for “which pattern” guidance)
**For each named pattern** on the catalogue (Consumer, Producer, Ingestion, etc.):

**Do (in order):**
1. Run **`intranet_list_page_links`** on the **catalogue** page (and, if needed, on the nearest hub page). Collect candidate `/SitePages/...` links.
2. **`intranet_fetch`** any candidate whose title or slug plausibly matches that pattern.
3. If still unresolved, **`intranet_search`** using the **exact pattern name** plus a disambiguator (e.g. `SitePages`, `integration`, `pattern`).

**Classify each fetch:**
- **Leaf detail page:** contains guidance specific to that pattern (description, rationale, constraints, diagrams-as-text, steps — not only the name in a list).
- **Non-leaf:** index, duplicate hub, or generic overview.

**Done when:** For **every** catalogue pattern name, you have either:
- **(A)** at least one **leaf** `intranet_fetch` you will use for that pattern’s write-up, or  
- **(B)** a **documented miss** (see Task 4 `## Retrieval gaps`).

Do **not** treat a second generic overview page (e.g. another “Integration Patterns” explainer) as a substitute for **(A)** unless that fetch actually contains the **pattern-specific** detail.

---

## Task 3 — Author files (splitting rule)
**Do:** Write with `write_workspace_file` under `workspace/context_staging/patterns/` only.

**Splitting:**
- **Index file (required):** Lists all pattern **names**, grouped as on the catalogue, with **provenance** pointing at the **catalogue** `intranet_fetch`. Keep catalogue-only claims in this file only.
- **Detail coverage (required):** For **each** pattern with a **leaf** fetch, either:
  - **Preferred:** one file per pattern (`kebab-case` name), **or**
  - **Acceptable:** one **compound** file with a `## <Pattern name>` section per pattern, **each section’s bullets grounded only in that pattern’s leaf fetch**.

If there are **more than ~15** distinct patterns, **prefer one file per pattern** for maintainability.

**Done when:** A reader can choose a pattern and find **rationale/detail** without opening SharePoint, **or** see an explicit gap entry for that pattern.

---

## Task 4 — Retrieval gaps (required honesty block)
In the **index** file (or a separate `...-retrieval-gaps.md` in the same folder), include:

```markdown
## Retrieval gaps
- <Pattern name>: <what you tried: list_page_links / search queries> → <outcome: no leaf URL / fetch empty / only duplicate hub>

**Done when: No silent “name-only” entries: every catalogue name appears either in a leaf-grounded section/file or in Retrieval gaps.

---

Task 5 — Close-out
Do: End your run with a short bullet list: files created and which intranet URLs each file relied on (catalogue vs leaf).

**Done when: The close-out matches the files on disk.