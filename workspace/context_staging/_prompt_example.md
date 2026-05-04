## Objective
Build draft architecture-context artefacts from UCL IT Architecture intranet Site Pages only (see `registry/intranet.yaml`), and stage them only under `workspace/context_staging/` (normally `workspace/context_staging/patterns/`).

## Hard constraints
- Sources must be intranet MCP tools only (`intranet_search`, `intranet_list_all_pages`, `intranet_list_page_links`, `intranet_fetch`).
- Do not use SharePoint document libraries (`search_sharepoint_site_documents`) or generic web sources for facts.
- Every factual statement must be grounded in a successful `intranet_fetch` for the same page, and each file must expose those sources in `## Source`.
- If evidence is missing, omit the claim or record it in retrieval gaps; do not guess.
- Keep output in British English and markdown with concise `##` sections.

## Task 0 — Baseline format and metadata
Read:
- `workspace/context/README.md`
- `workspace/context/_templates/artefact-template.txt`

Apply these front matter rules to every generated pattern file:
- `status: draft`
- `type: pattern`
- `owner: Architecture` (fixed default for this exercise)
- stable `id` values (for example `PATT-INT-001`, incremented without reusing ids)
- `related:` includes only existing paths under `workspace/context/` (otherwise `related: []`)

Required body sections for detail files:
- `## Source`
- `## Design overview`
- `## When to use`
- `## Implementation`
- `## Anti-patterns or when not to use` (only when supported)
- `## References`

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

## Task 3 — Author files with canonical naming and dedup
Write only with `write_workspace_file` under `workspace/context_staging/patterns/`.

Mandatory files:
- one index file: `integration-patterns-index.md`
- detail files for patterns with leaf evidence
- one gaps file if any unresolved items: `integration-patterns-retrieval-gaps.md`

Canonical filename policy for detail files:
- use one canonical file per pattern only
- format: `<group>-pattern-<number>-<short-topic-slug>.md`
- examples:
  - `consumer-pattern-1-enterprise-channel-to-system-synchronous.md`
  - `producer-pattern-2-system-to-enterprise-channel-batch-synchronous.md`
- do not create alias/duplicate variants (for example both short and long versions for the same pattern number)

Dedup invariant:
- at most one file per `(group, pattern number)` tuple
- if an existing file for the tuple is found, update it instead of creating another

## Task 4 — Retrieval gaps honesty block
Use this exact section shape in the gaps file or index file:

```markdown
## Retrieval gaps
- <Pattern name>: <attempts: list_page_links/search/fetch> -> <outcome>
```

No silent misses are allowed: every catalogue pattern must be represented in either detail coverage or retrieval gaps.

## Task 5 — Close-out validation
Before final response:
- list files created/updated
- map each file to source URLs used
- verify front matter fields are complete and `owner` remains `Architecture`
- verify no duplicate files for same `(group, pattern number)`

Done when close-out exactly matches files on disk.