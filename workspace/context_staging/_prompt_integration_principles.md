## Objective
Build **draft** architecture-context artefacts for **integration principles only** from UCL IT Architecture **intranet Site Pages** (see `registry/intranet.yaml`). Stage files only under **`workspace/context_staging/principles/`** (`type: principle`), using the layout you intend after promotion to `workspace/context/principles/`.

Use **peer mode** for this run so author → challenger → refiner → judge → final orchestrator all execute.

## Hard constraints
- Sources must be intranet MCP tools only (`intranet_search`, `intranet_list_all_pages`, `intranet_list_page_links`, `intranet_fetch`).
- Do not use SharePoint document libraries (`search_sharepoint_site_documents`) or generic web sources for facts.
- Every factual statement must be grounded in a successful `intranet_fetch` for the same page, and each authored file must expose those sources in **`## Source`**.
- If evidence is missing, omit the claim or record it in retrieval gaps; do not guess.
- Keep output in **British English** and markdown with concise `##` sections.
- Do not transfer content across pages with similar titles. Each file must reflect only the **exact** fetched page(s) used for that file.
- Claims such as “not stated”, “brief summary”, or “no details available” are allowed only when supported by explicit fetched evidence.
- **Do not anchor retrieval on one hard-coded page title alone.** Discover the correct **integration principles** (and related) Site Pages using tool results **and** the **Deterministic retrieval expansion** block injected into your prompt (from `registry/retrieval_association_graph.yaml`, vertex `integration_principles_corpus`). Use those suggested tokens in `intranet_search` / `intranet_list_all_pages` queries; still verify every page you cite with `intranet_fetch`.

## Deterministic graph hints (synonym-style expansion)
Your runtime prompt may include **“Deterministic retrieval expansion (registry graph)”** with suggested query/tool tokens. Those come from the **association graph** (not from this markdown file). Treat them as **search and discovery hints**—especially for phrases such as **integration principles**, **integration strategy**, **producer/consumer flows**, and related wording—then **confirm** candidates via `intranet_fetch`. Extend `registry/retrieval_association_graph.yaml` → vertex `integration_principles_corpus` when new intranet titles or slugs should expand future runs.

## Key evidence — Integration principles pages (discovered, not assumed)
- **Integration principles** content may live on a **dedicated Site Page** whose title or slug varies by site (for example pages whose title or URL contains “integration principles”, “integration strategy”, or similar). **Discover** it using graph-expanded tokens, `intranet_search`, `intranet_list_all_pages`, and **`intranet_list_page_links`** from relevant hubs—then **`intranet_fetch`** each page you rely on.
- Use one or more fetched **integration principles** pages as **primary evidence** for headline integration-principle artefacts where the user request applies.
- If no suitable integration-principles page exists after honest attempts, record that in **retrieval gaps** with queries tried; do not fabricate.

## Key evidence — Producer and consumer flows (mandatory when in scope)
Where principles address **producer flows**, **consumer flows**, or how they **relate**, you **must** also ground them in the IT Architecture page that describes those flows.

- **Canonical path (resolve ids via intranet tools; do not guess Graph ids):**  
  - Path ends with: **`/SitePages/producer-and-consumer-flows.aspx`** on the **IT Architecture** site configured in `registry/intranet.yaml` (example `web_url`: `https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/producer-and-consumer-flows.aspx` — only use hosts/sites that your successful tool responses confirm).
- **Mandatory in-scope fetch:** obtain a successful **`intranet_fetch`** of this page whenever the principle file covers producer/consumer themes. Treat its body as **primary evidence** for those themes (hand-offs, direction of data or control, responsibilities, constraints).
- **Distillation rule:** the page may describe **flows** rather than labelled “principles”. You may **distil** durable statements in `## Statement` / `## Implications` only when each bullet ties to **specific** wording, headings, or diagrams in the fetched text (verbatim excerpts in the evidence card). Otherwise **omit** or use **retrieval gaps**.
- **Naming hint:** for producer/consumer-heavy files, a slug such as `integration-principle-producer-and-consumer-flows.md` is acceptable if it matches dedup rules.

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

3. **Retrieval gaps file (if needed):** name with `*retrieval-gaps*.md` (recommended: `integration-principles-retrieval-gaps.md`). Place under `principles/`; it matches the relaxed **retrieval_gaps** profile when the filename contains `retrieval-gaps`.

4. **Final orchestrator close-out:** the last assistant message must list **every** `workspace/.../*.md` file created or updated by full repo-relative path (peer verifier).

Optional pre-check: `crisai validate-artefacts -p workspace/context_staging/principles/<file>.md`

## Task 0 — Baseline reading
Read:

- `workspace/context/README.md` (folder intent and metadata field reference)
- `prompts/_shared/context-staging.md` (catalogue vs leaf behaviour)
- `registry/workspace_artifact_profiles.yaml` (required headings for `type: principle`)

Do **not** recycle approved corpus text from `workspace/context/` as **source facts** for new claims (reading templates or README for shape is fine).

## Task 1 — Discover intranet pages (graph hints + principles + flows)
1. **Use the injected graph hints** (`integration_principles_corpus` and neighbours) plus the user request to build **query tokens** for `intranet_search` and `intranet_list_all_pages` (include synonyms such as **integration principles**, **integration strategy**, **producer/consumer** phrasing as hints—not as proof until fetched).
2. **Discover** the live **integration principles** (and related) Site Pages from results: inspect titles, slugs, and `web_url`; open hubs with **`intranet_list_page_links`**; shortlist candidates before fetching.
3. **`intranet_fetch`** every page you will cite in an artefact (including each **integration principles** page used).
4. **Producer and consumer flows:** locate `producer-and-consumer-flows.aspx` via the same discovery tools if not already in your candidate set; **`intranet_fetch`** it **whenever** producer/consumer themes appear in the principles you author. Record ids in the evidence card.

Reject treating **navigation-only** snippets as full sources: if a page is only a link farm with no substantive body, fetch the linked leaves or record a gap.

## Task 2 — Evidence-bind (principles only)
For each principle file you plan to write:

- capture an **evidence card** before writing:
  - working title for the principle artefact
  - `web_url`, `graph_site_id`, `graph_page_id` for **each** page that supports claims in that file (must include each **integration principles** page used, and **producer-and-consumer-flows** when the file covers producer/consumer themes)
  - 2–4 short **verbatim** excerpts per page that justify `## Scope`, `## Statement`, and `## Implications`.

If an **integration principles** page or the **producer/consumer flows** page cannot be fetched after reasonable attempts, record the exact tool errors and attempts in **retrieval gaps** and do not fabricate content for that scope.

## Task 3 — Author files, naming, and dedup
Write only with `write_workspace_file` under **`workspace/context_staging/principles/`**.

- One main topic per file where possible.  
- Filename convention: `integration-principle-<short-topic-slug>.md` (lowercase, hyphenated).  
- `type: principle`  
- Stable ids: `PRIN-INT-001`, increment without reuse across this run.

**Dedup invariant**  
- At most **one** staging file per **primary slug** (`integration-principle-*`). If a file already exists for the same topic, **update** it instead of creating a parallel name.

**Optional index**  
- You may add a short index under `principles/` (for example `integration-principles-index.md`) with `type: principle` and honest Scope/Statement/Implications if it adds navigation value; otherwise omit it.

## Task 4 — Retrieval gaps honesty block
If anything cannot be resolved from intranet pages after reasonable attempts:

```markdown
## Retrieval gaps
- <Topic or page name>: <attempts: list_page_links / search / fetch> -> <outcome>
```

## Task 5 — Close-out validation
Before final response:

- list files created/updated (all `workspace/...` paths);
- map each file to the `web_url`(s) used (**must** cite every **integration principles** page relied on, and **producer-and-consumer-flows** when producer/consumer principles are included);
- verify required `##` headings for `type: principle` and **`## Source`** on every artefact;
- verify stable `id` uniqueness across all new files in this run;
- show evidence card linkage per file (title + graph ids);
- ensure the **final orchestrator** lists every changed markdown path.

Done when close-out matches files on disk.
