---
name: crisai-semantic-registry-reference
description: Deep domain reference for crisAI's semantic registry — registry/semantic_catalog.yaml and registry/semantic_graph.yaml. Load this before adding or removing routing terms, adding an intent vertex or deliverable type, tuning source-fit constraints, debugging why a prompt routed to the wrong agent/mode, editing peer-contract or verifier markers, or answering "which file owns this vocabulary?". Covers the catalog/graph ownership split, file schemas, the two different term-match semantics, emit/priority/BFS rules, validation gaps doctor does not catch, and the bare terms that must never be re-added.
---

# crisAI semantic registry reference

This is the domain-theory pack for the two registry files that own crisAI's routing and
workflow semantics. All line numbers and counts are as of 2026-07-02 (branch `main`).

Jargon used throughout, defined once:

- **Catalog** = `registry/semantic_catalog.yaml` (725 lines): the self-described "legacy"
  catalogue of router term families, peer-verifier regexes, peer-contract markers, peer-judge
  markers, shared lexicon, retrieval source-fit constraint vocabulary, interaction regexes,
  session-anchor/session-memory vocabulary.
- **Graph** = `registry/semantic_graph.yaml` (699 lines): task-intent vertices, deliverable
  vertices, source-resolution vertices, source-family suggestion vertices, and deterministic
  retrieval-expansion topic vertices connected by undirected edges.
- **Emit** = the `emits:` mapping on a graph vertex — facts (`primary_intent`,
  `deliverable_type`, `source_resolution`, `required_evidence_level`, `success_criteria`,
  `anti_goals`, `suggested_sources`) surfaced when user text activates that vertex.
- **Doctor** = `uv run crisai doctor` (`src/crisai/registry_validation.py::run_doctor`,
  CLI command at `src/crisai/cli/main.py:491`), the registry validation pass.

## 1. Ownership split — who owns which vocabulary

CLAUDE.md's hard rule: all semantic vocabulary lives in these two files, never hardcoded in
Python. The split (documented in both file headers and `DOCUMENTATION.md` §9.2):

| File | Owns |
|---|---|
| Catalog | Router term families (`discovery/design/review/operations/peer/publication/criticality` terms, `source_markers`, `architecture_location_markers`, explicit discovery/peer patterns), peer-verifier regexes and term lists, peer-contract substring markers, peer-judge decision markers, `lexicon` (function words, prompt-noise, title-relation, continuation template), `retrieval_constraints` (source-fit vocabulary), `interaction` regexes, `artifact_lifecycle`, `session_anchors`, `session_memory` markers |
| Graph | Task-intent vertices with emits, deliverable-type vertices, source-resolution vertices, source-family suggestion vertices, deterministic retrieval-expansion topic vertices and edges |

Direction of travel: the catalog self-describes as **legacy** (header line 1;
`src/crisai/orchestration/semantic_catalog.py` module docstring: router and peer subsystems
"have not moved to graph-emitted facts yet"). Both files are fully load-bearing today.

### Acknowledged leaks — vocabulary living outside the two sanctioned files

The two-file rule has two known, live exceptions. Do not "fix" them casually and do not cite
the rule as if it were airtight:

1. **`registry/workflow_policy.yaml` → `workflow_policy.capability_markers`** — term lists
   (`intranet_grounded`: intranet, site pages, sitepages, intranet_fetch_page;
   `produce_artifacts`: write_workspace_file, create file(s), deliver files,
   knowledge_staging/, tasks/, under workspace/) that activate hard runtime gates. Loaded by
   `src/crisai/cli/workflow_policy.py` (loader at :155, merged over structural defaults).
2. **`registry/search_synonyms.yaml`** — intranet page-search synonym groups, consumed by
   `src/crisai/intranet/providers/sharepoint_pages.py` (path configured via
   `intranet/config.py`, filename overridable as `search_synonyms_file`).

Also not registry-owned: the route-hint **thresholds** (≥2 operations, ≥2 discovery, ≥2
design, ≥2 review, ≥1 publication, ≥1 criticality — `request_contract.py:_route_hints`) and
the source-nudge family set `{intranet, sharepoint_docs, workspace}` (`router.py:108`) are
hardcoded in Python. Not every "tune routing" ask is registry-only — see §7.

Open hygiene item: `reference/TODO.md` TODO-049 records cross-bucket term
overlap (`judge` in both `peer_terms` and `review_terms`, etc.) and data-architecture
vocabulary having two homes (catalog `peer_verifier.data_architecture_terms` vs graph
`data_architecture_core`). Treat duplicated DA terms as a known drift, not a pattern to copy.

## 2. File schemas

### 2.1 Catalog schema (`registry/semantic_catalog.yaml`)

Loader: `semantic_catalog.py::load_semantic_catalog` — `@functools.lru_cache(maxsize=8)`
keyed on the registry-dir string. **Hard-fail**: missing file raises `FileNotFoundError`;
bad YAML or failed shape validation raises `SemanticCatalogError` with a field-level message.
A broken catalog kills every run.

Required top-level mappings (validated at `semantic_catalog.py:_validate_top_level`):
`router`, `peer_verifier`, `peer_contract`, `peer_judge`, `lexicon`, `retrieval_constraints`.
Optional: `interaction`, `artifact_lifecycle`, `session_anchors`, `session_memory`, plus
`version: 1` (not validated).

| Block | Shape and required fields |
|---|---|
| `router` | 11 flat lists → lowercased frozensets: `discovery_terms`, `design_terms`, `review_terms`, `operations_terms`, `peer_terms`, `publication_terms`, `explicit_discovery_patterns`, `explicit_peer_patterns`, `criticality_terms`, `source_markers`, `architecture_location_markers` |
| `peer_verifier` | `pattern_gap_line` + `leaf_file_pattern` (required non-empty regex strings); `leaf_file_terms` + `data_architecture_terms` (required non-empty lists); `intranet_evidence_positive_marker` (required string); `intranet_evidence_negative_markers`; `agent_output_signatures` (agent_id → regex, compiled IGNORECASE); `boilerplate_strip_patterns` (compiled IGNORECASE) |
| `peer_contract` | 5 **required non-empty** lists: `file_write_markers`, `code_change_markers`, `code_target_markers`, `grounding_markers`, `assessment_markers`; optional `document_export_native_markers`, `document_export_source_markers`. Lowercased but **trailing spaces preserved** — see §6.1 |
| `peer_judge` | 3 required non-empty lists: `accept_markers`, `revise_markers`, `rework_markers` |
| `lexicon` | `function_words` (categorised dict, ≥1 non-empty category required), `prompt_noise_terms` + `title_relation_terms` (required non-empty), `forward_title_relation_terms`, `continuation_intent_template` (string map) |
| `retrieval_constraints` | `object_type_terms` (required non-empty), `source_scope_markers` (scope → marker list, ≥1 scope required; scopes today: `personal_onedrive`, `sharepoint`, `intranet`, `workspace`), `title_position_terms`, `source_type_markers`, `source_candidate_metadata_deny_keys` |
| `interaction` | Real regex lists compiled with `re.IGNORECASE \| re.DOTALL`: `explicit_mode_patterns` (peer/pipeline/single), `continuation_patterns`, `generative_peer_patterns`, `retrieval_required_patterns`, `peer_retrieval_force_patterns` |
| `artifact_lifecycle` | `persisted_deliverable_filenames`: deliverable_type → filename (currently 4 entries: architecture_recommendation, architecture_design, options_paper, assessment) |
| `session_anchors` | `kinds` + order/title/summary/status column lists + `preferred_markers` (consumed by `session_anchors.py`) |
| `session_memory` | 7 marker lists for deterministic session-memory extraction |

`merge_semantic_catalog_dicts` (`semantic_catalog.py:302`) exists but is **only called from
tests** — there is no runtime overlay mechanism. The only override is whole-directory
replacement via `CRISAI_REGISTRY_DIR` (see the crisai-config-and-flags skill).

### 2.2 Graph schema (`registry/semantic_graph.yaml`)

Loader: `retrieval_association_graph.py::load_retrieval_association_graph` — **fail-open**:
missing file, unparseable YAML, or zero indexable vertices → returns `None` with a log
warning and the retrieval nudge silently disables (task contracts fall back to
`respond`/`general_answer`, `suggested_sources` becomes `{"generic_retrieval"}`). A broken
graph is easy to miss without running doctor. The loader is **not cached** — the file is
re-read and re-parsed on every call.

```yaml
version: 1
settings:
  max_hops: 2            # int, clamped to [0, 4]; default 2
vertices:
  - id: intent.example   # required, unique by convention (not enforced)
    priority: 80         # int, default 0; higher wins scalar-emit ties
    terms: [...]         # REQUIRED non-empty — a vertex with no terms is silently dropped
    emits: {...}         # optional mapping, copied verbatim (keys unvalidated)
edges:
  - [vertex_a, vertex_b] # 2-element list, or {from: a, to: b}; stored UNDIRECTED
```

Emit keys in use today and their consumers:

| Emit key | Values in use | Consumer |
|---|---|---|
| `primary_intent` | `recommend`, `design`, `assess`, `summarize_source`, `retrieve_source` (the wired set — §7) | Task contract → route hints, actions, router fast path |
| `deliverable_type` | architecture_recommendation, architecture_design, options_paper, assessment, source_inventory, decision, data_model, integration, migration_plan, mapping, deck_summary, document_summary, executive_summary | Task contract; artefact validation alignment |
| `source_resolution` | `as_needed`, `matching_source`, `latest_matching_source` | Task contract → `source_required` inference |
| `required_evidence_level` | `supporting_sources`, `content_read`, `metadata_read` | Task contract → quality gates, router fast path |
| `success_criteria` / `anti_goals` | lists of strings | Injected into stage prompts via the task contract |
| `suggested_sources` | `intranet`, `sharepoint_docs` (only `intranet`/`sharepoint_docs`/`workspace` trigger the router nudge) | DeterministicRetrievalContext → source nudge, prompt hints |

Vertex naming convention: `intent.*` (task intent), `deliverable.*`, `source_resolution.*`,
then bare-named topic vertices (`enterprise_architecture_core`, `intranet_site_pages`, …).

## 3. The two match semantics — memorise this table

Term authors must know both rules; they differ per file and the difference has caused real
misroutes.

| | Catalog router terms | Graph vertex terms |
|---|---|---|
| Code | `request_contract.py::_contains_any`/`_score_terms` (`phrase in text`), same in `router.py` | `retrieval_association_graph.py::_term_matches_message` (:49-61) |
| Rule | **Always plain substring**, on whitespace-collapsed lowercased text — regardless of term length | Term **≥ 5 chars → plain substring**; term **< 5 chars → word-boundary regex** `\bterm\b` (IGNORECASE) |
| Consequence | `read` (in `discovery_terms` and `source_markers`) matches inside "al**read**y" and "sp**read**"; `site` matches inside "web**site**" | `design` (6 chars, substring) matches inside "re**design**"; but `adr`, `hld`, `ppt`, `doc`, `file`, `page` (< 5 chars) only match as whole words |

Two traps that follow directly:

- Catalog `explicit_discovery_patterns` and `explicit_peer_patterns` are **named "patterns"
  but matched as plain substrings** (they pass through `_as_frozenset`, not `re.compile`).
  Only the catalog's `interaction:` block holds real regexes.
- Adding a short (< 5 char) term to the catalog gets substring matching anyway; adding it to
  the graph gets word-boundary matching. The same string behaves differently per file.

## 4. How a message becomes a route (the consumption pipeline)

`decide_route` (`router.py:483`) → normalise text → load catalog → compute deterministic
graph context → `infer_request_contract` (`request_contract.py:86`) → rule cascade
`_route_from_contract` (`router.py:111-353`) → explicit user overrides applied last.

1. **Task contract** (`task_contract.py:61`): `expand_retrieval_hints` finds **directly
   activated** vertices only; `collect_graph_emits(graph, activated_seeds)` merges their
   emits (§5). If no activated vertex emits a `primary_intent`, the contract falls back to
   `primary_intent=respond`, `deliverable_type=general_answer`.
2. **DeterministicRetrievalContext** (`retrieval_association_graph.py:246-270`): emits are
   merged over **all BFS-reachable vertices within `max_hops`** (unlike the task contract's
   seeds-only merge), but only `suggested_sources` is read from that merge; hint terms are
   the union of terms of all reachable vertices, injected into runtime prompts via
   `format_retrieval_expansion_block` (max 36 terms, wrapped by
   `prompt_generation.py:59`).
3. **Route hints** (`request_contract.py:_route_hints`, thresholds hardcoded in Python):
   `operations` at ≥2 matches; `retrieval_only` from any explicit_discovery_pattern;
   `publication` at ≥1 match or a workspace output path; `source_lookup` if discovery ≥2 OR
   any source_marker; `design` if design ≥2 OR `primary_intent ∈ {design, recommend}`;
   `review` if review ≥2 OR intent `assess`; `peer` if any explicit peer pattern OR (peer ≥2
   AND design/review ≥1); `criticality` at ≥1; `mixed_complexity` when ≥2 categories fire
   and combined score ≥3. An `architecture_location_markers` match **subtracts 1 from
   design_score** (so "sharepoint architecture site" does not read as a design ask).
4. **source_required** (`request_contract.py:113-124`): true when explicit source families
   are inferred (workspace excluded), a named-source filename matches the regex, the task
   contract's `source_resolution` ∉ {"", none, as_needed} (suppressed when publication is
   requested), or any `interaction.retrieval_required_patterns` regex fires.
5. **Deterministic source nudge** (`router.py:93-108`): if the graph's `suggested_sources`
   intersects `{intranet, sharepoint_docs, workspace}`, the router forces
   `source_required` plus the `source_required`/`source_lookup` hints even if step 4 said no.
6. **Router cascade** (`router.py:111-353`), first match wins:
   `retrieval_only` → `operations` → `native_document_export` → explicit
   pipeline/peer/single preference → **metadata-only source-inventory fast path** (requires
   `primary_intent=retrieve_source` + `deliverable_type=source_inventory` +
   `required_evidence_level=metadata_read` + `source_required` and NO output_path or
   publication hint) → publication+source (pipeline) → publication (single publisher) →
   summary+source (pipeline) → criticality+(design|review) (peer) → peer → source+design
   (pipeline) → design+review (pipeline) → review-only (single) → summary (single) →
   mixed_complexity (pipeline) → design (single) → source_required/source_lookup discovery
   (single retrieval_planner) → orchestrator fallback (confidence 0.50).

Other catalog consumers: `retrieval_constraints` + `lexicon` feed
`source_constraints.py::infer_source_fit_constraints` (its docstring: "term lists live in
registry/semantic_catalog.yaml; Python only performs deterministic extraction and matching
mechanics" — and the **output path's scope is excluded from inferred source scopes**: an
artefact's write destination must never become an input source requirement, PR #43) and
`session_anchors.py`; `peer_contract` / `peer_verifier` / `peer_judge` feed
`peer_contract.py`, `peer_verifier.py`, `peer_judge.py`.

## 5. Emit rules: direct activation vs BFS, priority, tiebreak

`collect_graph_emits` (`retrieval_association_graph.py:118-145`) merges emits over an ordered
vertex list, sort key **`(-priority, vertex_id)`**:

- **Scalars are first-wins**: the highest-priority vertex's value sticks;
  **ties break alphabetically by vertex id**. Never rely on id ordering — set an explicit
  `priority` whenever two vertices can co-activate and emit the same scalar key. (Current
  priorities: intent.summary and source_resolution.latest_matching_source 100,
  intent.source_discovery 95, intent.options_analysis and source_resolution.matching_source
  90, intent.decision_record 85, intent.recommendation 80, intent.data_model /
  intent.integration_design / intent.migration_plan 78, intent.data_mapping 76,
  intent.assessment 75, intent.design_response 70, deliverable.executive_summary 65,
  deliverable.deck_summary / deliverable.document_summary 60, topic vertices 0.)
- **Lists are concatenated with de-duplication** (success_criteria, anti_goals,
  suggested_sources).

**Direct activation vs BFS-reachable — the single most important rule when wiring edges:**

- The **task contract** merges emits from **directly activated vertices only**
  (`task_contract.py:107-111` passes the seed set). Connecting a new vertex by edge to an
  intent vertex surfaces its **terms as prompt hints** (BFS within `max_hops`) and its
  `suggested_sources` (BFS merge in `build_deterministic_retrieval_context`), but it will
  **never contribute `primary_intent` or `deliverable_type`** unless the user's text
  activates that vertex directly.
- Bare-noun deliverable vertices (`deliverable.document_summary`,
  `source_resolution.matching_source` — terms like `document`, `file`, `page`) activate on
  almost any document-referencing prompt by design; they only win emit merges via their
  priority, and their short terms get word-boundary matching.

## 6. Hazards and invariants

### 6.1 Trailing-space peer markers must stay quoted

`peer_contract.code_target_markers` includes `"function "`, `"def "`, `"class "` — the
trailing space is load-bearing (it distinguishes `def ` the keyword from `default`,
`definition`, …). The loader (`semantic_catalog.py::_peer_marker_phrases`, :180-199)
lowercases but **deliberately preserves trailing whitespace** for peer_contract fields only
(everything else goes through `_as_frozenset`, which strips). If a YAML reformat strips the
quotes, matching silently broadens. Keep them quoted; check with:
`grep -n '"function "\|"def "\|"class "' registry/semantic_catalog.yaml`.

### 6.2 What doctor does NOT catch

Doctor validates: the 7 required registry files parse as YAML mappings
(`registry_validation.py:460-468`), full catalog load after `cache_clear()` (:486-493),
graph missing-vs-invalid distinguished with vertex count reported (:495-509), and the
**function-word leak check** (:510-522) — any graph vertex term equal to a standalone word
in `catalog.lexicon.all_function_words` is a doctor **error** naming the vertex and term.
That leak check is the only cross-file semantic check. Silently tolerated:

- **Typo'd edge endpoints are dropped without warning**
  (`retrieval_association_graph.py:213`: `if a in vertex_terms and b in vertex_terms`).
  A misspelt vertex id in `edges:` simply disconnects the association.
- **A vertex whose `terms:` list is empty or missing is dropped entirely** (:194) — its
  emits, priority, and edges all vanish. Every vertex needs at least one term to exist.
- **Unknown emit keys pass silently** — `emits` is copied verbatim; consumers only read the
  known keys, so a typo like `primary_intents:` produces a vertex that emits nothing useful.
- **`primary_intent` values are not validated against the wired set** (§7) — an unwired verb
  loads fine and silently degrades routing.
- **Duplicate vertex ids are not rejected** — the later dict entry wins.

### 6.3 Asymmetric failure and caching

| | Catalog | Graph |
|---|---|---|
| Load failure | Hard-fail (FileNotFoundError / SemanticCatalogError kills the run) | Fail-open (None + log warning; routing silently degrades to `respond`/`general_answer` and `generic_retrieval`) |
| Caching | `lru_cache(maxsize=8)` per process — **long-running processes (`./start api`, `./start web`) need a restart after edits** (the file header says "Restart CLI / processes after edits") | **No cache** — re-read and re-parsed from disk on every routing/contract computation, so edits take effect live even in running servers (and cost per-turn I/O) |

Each `crisai ask` CLI invocation is a fresh process, so restart-after-catalog-edit in
practice means: restart the API/web services.

### 6.4 `graph_version` in traces

`deterministic_context_from_registry` (`retrieval_association_graph.py:313-351`) reports
`graph_version` as the first 12 hex chars of a **sha1 of the file bytes**, not the YAML
`version:` field. Use it to confirm which graph revision a trace ran against.

### 6.5 Function-words rule

Standalone function words (`the`, `a`, `an`, `of`, `for`, `in`, `on`, `to`, `and`, `that`,
`this`, `would`, …) belong in `lexicon.function_words` in the catalog, **never** as
standalone graph vertex terms — doctor errors on the leak. Multiword phrases containing
function words are fine when the whole phrase carries meaning
(e.g. `principles of integration`).

## 7. The wired `primary_intent` enum lives in Python — say it plainly

The values the runtime actually branches on are:
**`recommend`, `design`, `assess`, `summarize_source`, `retrieve_source`**
(plus the fallback `respond`). Consumption points:

- `task_contract.py:42` — `is_summary` ⇔ `primary_intent == "summarize_source"`
- `request_contract.py:_route_hints` — `{design, recommend}` fire the design hint; `assess`
  fires the review hint; same sets drive `_actions` (draft/assess)
- `router.py:189` — metadata-only fast path requires `retrieve_source`

**A registry edit is NOT sufficient for a brand-new intent verb.** CLAUDE.md says "adding a
new intent type … should be a registry edit, not a code change" — that holds only when you
**reuse a wired verb with a new `deliverable_type`** (the pattern used by
`intent.decision_record`, `intent.data_model`, `intent.integration_design`,
`intent.migration_plan`, `intent.data_mapping` — see the comment block at graph lines
192-199 and `DOCUMENTATION.md` §9.2). Emitting a genuinely new verb (say
`primary_intent: translate`) loads without error, but no route hint, no action, and no router
branch tests it: the request degrades to term-score routing or the orchestrator fallback.
Extending the verb set requires code changes in `request_contract.py`/`router.py` plus golden
cases — route that through change control as a code change, not a registry edit.

## 8. Deliberately removed bare terms — never re-add them

Each of these was removed because it caused a documented misroute (the in-file comments,
`DOCUMENTATION.md` §9.2, CRISAI-ADR-014's context section, and regression tests all record
the stories). Re-adding any "obvious" term below reintroduces the bug:

| Never re-add | Where it was | Misroute it caused | Where it lives / is guarded now |
|---|---|---|---|
| Bare object nouns `document`, `file`, `page` | `router.discovery_terms` | Inflated discovery_score and the mixed-complexity heuristic on any doc-referencing prompt | `router.source_markers` (still fires `source_lookup` for source-context prompts) — comment at catalog :9-15 |
| Bare trouble words `issue`, `error`, `fix`, `broken`, `auth`, `token`, `login`, `timeout` | `router.operations_terms` | Two collisions ("fix the auth design") hit the ≥2 threshold and sent an architecture request to the crisAI-runtime troubleshooting agent | Tool-failure-scoped phrases only (`sharepoint auth`, `token cache`, `timed out`, …) — comment at catalog :64-73; guarded by `test_architecture_prompts_do_not_route_to_operations` |
| Bare file extensions (e.g. `.pptx`) | `router.publication_terms` | A *referenced* source filename ending `.pptx` was read as a publish instruction; the workspace-write gate then failed an otherwise-complete run (the incident that motivated CRISAI-ADR-014) | Type tokens only count inside produce contexts: `into a .pptx`, `as a powerpoint`, `export as`, … — comment at catalog :137-140 |
| Bare `workspace` | `retrieval_constraints.source_scope_markers.workspace` | "save it in the workspace" (a *write* phrasing) was read as a workspace *source-scope* filter | Only read/fetch phrasings count: `from the workspace`, `search workspace`, `workspace file`, … — comment at catalog :474-479 |

Guarding tests exist for the operations story; the others are guarded by the router golden
set staying green (§10).

## 9. Step-by-step checklists

### 9.1 Add a routing term (catalog)

1. Pick the correct family — and check §8 first: is this a bare noun / trouble word / file
   extension / write-phrasing that was deliberately removed?
2. Remember **always-substring** matching (§3): a short or embeddable term (`read`, `site`,
   `path`) matches inside longer words. Prefer multi-word phrases.
3. Check the term is not already in another family (TODO-049 overlap debt) and is not a
   function word.
4. Mind the thresholds (§4 step 3): a single new `operations`/`design`/`review` term only
   matters in combination (≥2), but one `publication` or `criticality` term fires alone.
5. Edit `registry/semantic_catalog.yaml`; keep trailing-space markers quoted (§6.1).
6. Verify (§10). Restart long-running services (catalog is lru_cached).

### 9.2 Add an intent vertex (graph)

1. Add a vertex `intent.<name>` with: explicit `priority` (compare against the table in §5 —
   who else could co-activate?), specific **multi-word** terms (so a bare noun cannot
   trigger it — the ADR-014 discipline), and `emits` containing:
   - a **wired** `primary_intent` (`recommend`/`design`/`assess`/`summarize_source`/
     `retrieve_source` — anything else silently degrades, §7);
   - a `deliverable_type`, ideally matching a validation profile in
     `registry/workspace_artifact_profiles.yaml` so the ask, the task contract, and the
     artefact validator line up;
   - `required_evidence_level`, `success_criteria`, `anti_goals`.
2. Optionally add `edges` to topic vertices for hint expansion — remembering edges give
   **hints and suggested_sources only, never primary_intent** (§5), and typo'd endpoints are
   silently dropped (§6.2). Spell-check both ids against existing vertex ids.
3. The vertex must have ≥1 term or it is silently dropped (§6.2). Terms < 5 chars get
   word-boundary matching; ≥ 5 chars get substring (§3).
4. No standalone function words as terms (doctor errors).
5. Run doctor; add a golden case (§10). Graph edits are live (no restart needed for the
   graph itself), but restart anyway if you also touched the catalog.

### 9.3 Add a deliverable type

1. Emit the new `deliverable_type` from an intent vertex (§9.2) — deliverable types are just
   strings flowing through the task contract; nothing validates the value.
2. If artefacts of this type are written under `workspace/knowledge*/` or
   `workspace/tasks/`, add a matching profile to `registry/workspace_artifact_profiles.yaml`
   (profiles are first-match top-to-bottom; `type_aliases` maps front-matter spellings).
3. If the deliverable should persist under a canonical filename, add a mapping to
   `artifact_lifecycle.persisted_deliverable_filenames` in the catalog.
4. Check whether any downstream logic keys on the type (e.g. the router fast path requires
   `source_inventory`; `grep -rn "deliverable_type" src/crisai` before assuming inertness).

### 9.4 Tune source-fit constraints

1. Vocabulary lives in catalog `retrieval_constraints`: `object_type_terms` (what counts as
   a retrievable object), `source_scope_markers` (per-scope phrasings — keep the
   read-vs-write phrasing discipline from §8 for the `workspace` scope),
   `title_position_terms`, `source_type_markers`.
2. Consumer is `source_constraints.py::infer_source_fit_constraints` (fail-open on catalog
   errors). Note the invariant: the request's output path scope is **excluded** from
   inferred source scopes (output destination ≠ input source, PR #43).
3. `source_scope_markers` also drives Request Contract `source_families` inference
   (`request_contract.py::_source_families`), which feeds `source_required` — a new scope
   marker can flip prompts from single-agent to retrieval pipeline. Run the golden set.

## 10. How to verify a semantic registry change

Run these after any edit, in order:

1. **Doctor** — `uv run crisai doctor` (add `--models` only when model wiring changed;
   it needs `OPENAI_API_KEY`). Confirms both files load, reports graph vertex count, and
   catches function-word leaks. It does NOT catch §6.2's gaps — eyeball edges and emit keys.
2. **Router golden set** —
   `uv run pytest tests/unit/test_router_regression.py -q`
   (28 golden (query, intent, mode) cases plus ADR-014 operations guards). **Always put the
   test path FIRST, flags after**: MCP server modules treat `sys.argv[1]` as a workspace
   root at import time (`servers/sharepoint_server.py:29-34`), so `pytest -q <path>` litters
   the repo root with a `-q/.auth/` directory. Note the golden set suppresses the
   deterministic source **nudge** and passes `registry_dir=None`, but task contracts still
   load the real graph via settings fallback — so it exercises catalog terms AND graph
   intent emits (its own header comment slightly understates this).
3. **Unit suites for the touched layer** — `tests/unit/test_semantic_catalog.py`,
   `test_retrieval_association_graph.py`, `test_router.py`, `test_router_publisher.py`,
   `test_registry_validation.py` (all exist as of 2026-07-02).
4. **Add a case for new behaviour**: a new routing path gets a `GOLDEN_CASES` tuple; a new
   vertex gets a term-activation assertion. See the crisai-validation-and-qa skill for test
   mechanics and the crisai-proof-and-analysis-toolkit skill for the full
   prove-a-routing-change recipe.
5. **Restart semantics**: catalog edits require restarting long-running services
   (`./stop`, then `./start api` / `./start web`); graph edits are picked up live (§6.3).
   Confirm the running graph via `graph_version` in traces (§6.4).

## When NOT to use this skill

- **Classifying and gating the change itself** (is this a registry edit vs code change,
  branch/PR/commit discipline, CI blockers) → **crisai-change-control**.
- **Router/orchestration code architecture and ADR-level rationale** (why contracts are
  schema-backed, module map, enforced invariants with file:line) →
  **crisai-architecture-contract**.
- **Test mechanics** (exact pytest commands, markers, coverage gate, conftest traps, the
  full golden/certified inventory) → **crisai-validation-and-qa**.
- **Env vars and flags** (`CRISAI_REGISTRY_DIR`, `CRISAI_MATERIALISE_SOURCES`, …) →
  **crisai-config-and-flags**.
- **A run misbehaving at runtime** (wrong route observed live, gate failures, trace
  triage) → **crisai-debugging-playbook**; measuring behaviour →
  **crisai-diagnostics-and-tooling**.

## Provenance and maintenance

All claims verified against the repo on 2026-07-02 (branch `main`). Re-verification
one-liners for facts most likely to drift:

- Ownership split docs: `sed -n '761,796p' DOCUMENTATION.md`
- Catalog required keys / hard-fail loader: `grep -n "_validate_top_level\|lru_cache\|FileNotFoundError" src/crisai/orchestration/semantic_catalog.py`
- Trailing-space preservation: `grep -n "_peer_marker_phrases" src/crisai/orchestration/semantic_catalog.py` and `grep -n '"def "' registry/semantic_catalog.yaml`
- Graph match rule (≥5 substring / <5 word-boundary): `sed -n '49,61p' src/crisai/orchestration/retrieval_association_graph.py`
- Catalog always-substring: `grep -n "_contains_any\|_score_terms" src/crisai/orchestration/request_contract.py`
- Emit merge order `(-priority, vid)`: `grep -n "vertex_priorities.get" src/crisai/orchestration/retrieval_association_graph.py`
- Seeds-only task-contract merge: `grep -n "collect_graph_emits" src/crisai/orchestration/task_contract.py src/crisai/orchestration/retrieval_association_graph.py`
- Silently dropped edges: `sed -n '203,215p' src/crisai/orchestration/retrieval_association_graph.py`
- Wired primary_intent set: `grep -rn '"design", "recommend"\|summarize_source\|retrieve_source' src/crisai/orchestration/request_contract.py src/crisai/orchestration/task_contract.py src/crisai/orchestration/router.py`
- Route-hint thresholds: `grep -n ">= 2\|>= 1\|>= 3" src/crisai/orchestration/request_contract.py`
- Source-nudge family set: `grep -n "sharepoint_docs" src/crisai/orchestration/router.py`
- Doctor checks (required files, function-word leak): `sed -n '456,523p' src/crisai/registry_validation.py`
- Ownership leaks: `grep -n "capability_markers" registry/workflow_policy.yaml` and `head -20 registry/search_synonyms.yaml`
- Removed-bare-term comments: `grep -n "CRISAI-ADR-014" registry/semantic_catalog.yaml`
- Golden set: `sed -n '1,25p' tests/unit/test_router_regression.py`
- Graph fail-open + no cache: `grep -n "return None\|lru_cache" src/crisai/orchestration/retrieval_association_graph.py`
