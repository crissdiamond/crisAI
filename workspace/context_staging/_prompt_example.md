## Objective
Build draft architecture-context artefacts from UCL IT Architecture intranet Site Pages only (see `registry/intranet.yaml`), and stage them only under `workspace/context_staging/` (normally `workspace/context_staging/patterns/`).

Use **peer mode** for this run so author → challenger → refiner → judge → final orchestrator all execute.

## Hard constraints
- Sources must be intranet MCP tools only (`intranet_search`, `intranet_list_all_pages`, `intranet_list_page_links`, `intranet_fetch`).
- Do not use SharePoint document libraries (`search_sharepoint_site_documents`) or generic web sources for facts.
- Every factual statement must be grounded in a successful `intranet_fetch` for the same page, and each file must expose those sources in `## Source`.
- If evidence is missing, omit the claim or record it in retrieval gaps; do not guess.
- Keep output in British English and markdown with concise `##` sections.
- Do not transfer content across pages with similar names (for example `Ingestion Pattern 3` vs `Producer Pattern 3`). File claims must be authored only from the exact fetched page used for that file.
- Claims such as “not stated”, “brief summary”, or “no details available” are allowed only when supported by explicit fetched evidence.

## Peer pipeline and artefact validator (must pass)
After the judge accepts, the run applies **filesystem + artefact profile checks** (`registry/workspace_artifact_profiles.yaml` via `src/crisai/orchestration/peer_verifier.py`). A failed check aborts the run.

Obey these **exact** rules so validation passes:

1. **Integration pattern leaf files** (`workspace/context_staging/patterns/*.md` with `type: pattern`, excluding index/gaps/readme):
   - Front matter must include: `id`, `title`, `type`, `status`, `owner` (use `Architecture` for this exercise).
   - Body must contain these level-2 headings **verbatim** (spelling and casing):
     - `## Design overview`
     - `## When to use`
     - `## Implementation`
     - `## NFRS`
     - `## Anti-patterns or when not to use`
     - `## Source`
     - `## References`
   - Do **not** omit `## NFRS`, `## Anti-patterns or when not to use`, or `## References` even when the source is thin: use minimal, evidence-backed bullets (for example “Not stated on the fetched page for this subsection.” only if the fetched text supports that negative claim).
   - `## Source` must list the `web_url`(s) used for claims (and `graph_site_id` / `graph_page_id` when available).

2. **Slug dedup (hard gate):** at most **one** detail file per `(group, pattern number)` where group is `consumer`, `producer`, or `ingestion`. Filename pattern: `<group>-pattern-<number>-<single-short-topic-slug>.md`. Do **not** create two files that share the same group and number (for example two different `ingestion-pattern-3-*.md` names).

3. **Index file:** `integration-patterns-index.md` must include `type: pattern` in front matter and these sections: `## Design overview`, `## When to use`, `## Implementation`, `## Source`.

4. **Retrieval gaps file:** if used, name it so it matches `*retrieval-gaps*.md` (recommended: `integration-patterns-retrieval-gaps.md`). Include `## Retrieval gaps` with honest outcomes.

5. **Final orchestrator close-out:** the last assistant message must mention **every** `workspace/.../*.md` file created or updated in this run by full repo-relative path. Omitted changed files cause peer verifier failure.

Optional local pre-check (from repo root): `crisai validate-artefacts -p workspace/context_staging/patterns/<file>.md`

## Task 0 — Baseline format and metadata
Read:
- `workspace/context/README.md`
- `workspace/context/_templates/integration-pattern-artefact-template.txt`

Apply these front matter rules to every generated **pattern** file (index and leaf):
- `status: draft`
- `type: pattern`
- `owner: Architecture` (fixed default for this exercise)
- stable `id` values (for example `PATT-INT-001`, incremented without reusing ids across files)
- `related:` includes only existing paths under `workspace/context/` (otherwise `related: []`)

**Leaf** detail files must satisfy the **Peer pipeline and artefact validator** heading list above (stricter than “omit section if empty” in the template — headings are always required for this run).

## Task 1 — Resolve the correct catalogue page
Locate and fetch the catalogue whose URL ends with `/SitePages/integration-patterns.aspx` (lowercase, no suffix).

Primary route:
1. `intranet_search("integration-patterns")`
2. verify candidate `web_url`
3. `intranet_fetch` the exact lowercase slug

Fallback route:
1. `intranet_list_all_pages(query="integration pattern")`
2. filter by `/SitePages/integration-patterns.aspx`
3. fetch the exact page

Reject these imposters if discovered:
- `allPatterns.aspx`
- `Integration-Patterns(1).aspx`
- `Architecture-Patterns.aspx`

Done when the fetched catalogue enumerates Consumer, Producer, and Ingestion pattern groups with numbered entries.

## Task 2 — Discover leaf detail pages
For each catalogue pattern:
1. inspect links from catalogue/hub via `intranet_list_page_links`
2. fetch plausible candidates via `intranet_fetch`
3. if unresolved, run `intranet_search` with exact pattern name + disambiguator terms

Classify pages explicitly:
- leaf detail page: pattern-specific guidance (not just an index mention)
- non-leaf page: index/hub/overview/duplicate

Done when each catalogue pattern is either:
- covered by at least one leaf fetch used for authoring, or
- listed in retrieval gaps with attempts and outcome.

For each pattern selected for authoring, capture an evidence card before writing:
- pattern name
- `web_url`
- `graph_site_id`
- `graph_page_id`
- 2–4 short verbatim excerpts from fetched body text that justify key sections (for example implementation, NFRs, security, physical implementation)

## Task 3 — Author files with canonical naming and dedup
Write only with `write_workspace_file` under `workspace/context_staging/patterns/`.

Mandatory files:
- one index file: `integration-patterns-index.md`
- detail files for patterns with leaf evidence
- one gaps file if any unresolved items: `integration-patterns-retrieval-gaps.md`

Canonical filename policy for detail files:
- use **one** canonical file per pattern only
- format: `<group>-pattern-<number>-<short-topic-slug>.md`
- examples:
  - `consumer-pattern-1-enterprise-channel-to-system-synchronous.md`
  - `producer-pattern-2-system-to-enterprise-channel-batch-synchronous.md`
- do not create alias/duplicate variants (for example both “system” and “dms” filenames for the same ingestion pattern number)

Dedup invariant:
- at most one file per `(group, pattern number)` tuple
- if an existing file for the tuple is found, **update that file** instead of creating another

Authoring fidelity rules (mandatory):
- If fetched content contains detailed sections (for example working steps, NFRs, security, physical implementation), include those details; do not collapse them into “brief summary”.
- Negative assertions (for example “not stated on the page”) must be section-specific and evidence-backed by fetched text.
- If attribution is uncertain for any section, move that section’s claim to retrieval gaps rather than guessing.
- If the fetched page body clearly belongs to a **different** pattern family than the URL title (for example URL says Ingestion but body is Producer), record that in `integration-patterns-retrieval-gaps.md` and do **not** fabricate ingestion content from the producer text.

## Task 4 — Retrieval gaps honesty block
Use this exact section shape in the gaps file or index file:

```markdown
## Retrieval gaps
- <Pattern name>: <attempts: list_page_links/search/fetch> -> <outcome>
```

No silent misses are allowed: every catalogue pattern must be represented in either detail coverage or retrieval gaps.

## Task 5 — Close-out validation
Before final response:
- list files created/updated (all paths under `workspace/...`)
- map each file to source URLs used
- verify front matter fields are complete and `owner` remains `Architecture`
- verify no duplicate files for same `(group, pattern number)` (validator enforces this)
- for each detail file, show which fetched evidence card was used (match by pattern name + page ids)
- verify no file claims “not stated/brief summary” where fetched excerpts show concrete details
- ensure the **final orchestrator** answer explicitly references every changed markdown path (peer verifier requirement)

Done when close-out exactly matches files on disk.
