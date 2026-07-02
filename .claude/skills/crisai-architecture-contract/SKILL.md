---
name: crisai-architecture-contract
description: The crisAI architecture contract — every load-bearing design decision (all 15 ADRs distilled with the WHY behind each), the runtime invariants that must hold with the exact enforcing code file:line, and the known-weak points stated plainly. Load this before planning any change to routing, pipelines, contracts, MCP servers, workspace safety, or the FastAPI boundary; when asked "why is it built this way", "where is X enforced", "can I move/relax Y", or "what is fragile here"; when reviewing a change for architectural regressions; or when an ADR, invariant, or design rationale needs to be cited.
---

# crisAI architecture contract

This skill is the binding architectural memory of the repo: what was decided, why,
where each decision is enforced in code, and where the design is honestly weak.
Line numbers were verified on branch `main` at commit `c39273b` (2026-07-02); the
Provenance section gives one-line commands to re-verify anything that may drift.

System shape in one paragraph: crisAI is a local AI workstation of ~15 narrowly
scoped runtime agents (`registry/agents.yaml` → `registry/models.yaml`, per-agent
model assignment) running in three modes — `single`, `pipeline`, `peer` — behind a
single FastAPI boundary (`src/crisai/apps/web.py`). Machine-critical state travels
as JSON schema contracts (12 `*.schema.json` files in `src/crisai/schemas/`, plus 5
`*.prompt.md` fragments). Source and tool access goes through MCP stdio servers
declared in `registry/servers.yaml` with an `allow` (agent-visible) vs `internal`
(deterministic-orchestration-only) tool split. Semantic vocabulary lives in
`registry/semantic_catalog.yaml` and `registry/semantic_graph.yaml`, never in
Python. The doctrine throughout is **structural enforcement over prompt
instruction**: after a model demonstrably ignored "do not retrieve" in its prompt
(commit `9c9ee2e`), no behavioural guarantee is trusted unless a tool filter,
gate, or schema makes violation impossible.

## When NOT to use this skill

| You need | Use instead |
|---|---|
| Catalog vs graph schema, matching semantics, how to add an intent or tune routing | `crisai-semantic-registry-reference` |
| React web / Ink Gem UI architecture, design tokens, WCAG obligations | `crisai-ui-surfaces` |
| Env var / flag catalogue with defaults and guards | `crisai-config-and-flags` |
| Symptom→triage for a live runtime failure | `crisai-debugging-playbook` |
| Full incident history behind these decisions | `crisai-failure-archaeology` |
| How a change gets classified, gated, committed, merged | `crisai-change-control` |
| Setup, `./start`/`./stop`, daily operation | `crisai-build-run-operate` |

## 1. Load-bearing decisions (all 15 ADRs, distilled)

ADRs live in `reference/decisions/CRISAI-ADR-001..015` with an index in
`reference/decisions/README.md`. Read the full ADR before touching its subject
area; the table below is the map, not the territory.

| ID | Decision | Why (the pressure or incident behind it) | Status |
|---|---|---|---|
| ADR-001 | Workstation of narrowly scoped agents; agent↔model association lives in registry, not code | One broad agent owning retrieval + synthesis + critique + publishing blurred responsibility; users must pick a model per role | accepted (2026-05-11) |
| ADR-002 | Runtime semantics live in registry/config YAML; Python loads and enforces, never encodes vocabulary | Semantic rules hardcoded in Python were impossible to inspect, tune, or govern | accepted (2026-05-11) |
| ADR-003 | Evidence transport is separate from agent prose (`evidence_bundle_v1`); UI strips machine JSON; content-read requests fail fast without a valid bundle | Retrieval agents leaked raw JSON into CLI output, and downstream agents treated prose summaries as if they were validated evidence — weak grounding | accepted (2026-05-11) |
| ADR-004 | Task contracts preserve the user's main ask across stages; a request contract wraps them (workflow preference, source obligations, output paths, gates); summary fast path when validated evidence exists | Traces showed agents burning tokens debating source candidates when the user just wanted a summary — retrieval was being treated as the task | accepted (2026-05-11) |
| ADR-005 | One session per task; persist raw history but build prompts from compact task memory + small recent tail; drift warnings | Full-transcript replay wasted tokens and made agents repeat old reasoning | accepted (2026-05-11) |
| ADR-006 | Workspace spaces: `knowledge/` (curated, agent read-only), `knowledge_staging/` (agent-writable promotion candidates), `tasks/<task>/`; semantics in `registry/workspace_spaces.yaml` | The old `context`/`context_staging` model mixed team-owned reference knowledge with generated task output | accepted (2026-05-11) |
| ADR-007 | Markdown + Mermaid is the source of truth for artefacts; native DOCX/PPTX/email/JSON are follow-on exports from reviewed Markdown | Producing native files directly made validation, review, and promotion much harder | accepted (2026-05-11) |
| ADR-008 | Intranet MCP is standalone and provider-neutral; SharePoint Site Pages is only the default provider behind a neutral page contract | Other organisations use wikis/custom intranets; the contract must not bake in SharePoint IDs | accepted (2026-05-11) |
| ADR-009 | Web UX aligns with CLI routing/stage/session/evidence-hiding semantics; parity across surfaces unless explicitly decided otherwise | The CLI became the reference implementation; a second surface with divergent semantics would fork the product | accepted (2026-05-11) |
| ADR-010 | Narrow `document_formatter` agent: reviewed Markdown + template manifest → DOCX/PPTX via `document_export` MCP; writes only to `exports/`/`outputs/`; owns no content | Mixing drafting, design judgement, and native formatting in one agent risks content changes during export | accepted (2026-05-11) |
| ADR-011 | Deterministic session anchors (option/section/risk labels) stored in `tasks/<task>/.crisai/anchors.json`, extracted with registry vocabulary, resolved into `request_contract_v1.referenced_anchors` before agent execution | "Create HLDs for option 2 and 3" must resolve against the labels already shown to the user; reinterpreting from prompt semantics produces the wrong artefact while sounding plausible | accepted (file records no date) |
| ADR-012 | Gemini-style prompt-toolkit/Rich persistent CLI | The footer died during pipeline runs; the experiment was **abandoned** in favour of `./start api` + Ink Gem + React web over the shared `/api/v1/runs` contract. Note: the index table in `reference/decisions/README.md` still says "accepted" — the ADR file itself is authoritative | **superseded** (2026-05-16) |
| ADR-013 | Source connector capability contract: declarative `kind: source\|tool` + `capabilities` block per server in `registry/servers.yaml`, doctor-validated | What each source could do was hardcoded in `prompt_generation.py` and prompt markdown, conflicting with ADR-002 and blocking new adapters. Note: the ADR text self-describes Phase 0–1, but TODO-017's Done row records Phase 2 shipped (guidance generated from the contract; hardcoded tool lists removed) — the ADR text is stale on that point | accepted (2026-06-13) |
| ADR-014 | Session state as living, pulled, status-bearing design memory: per-turn intent classified from the NEW message only; prior output typed by kind and pulled on relevance, never pushed into intent; stale state demoted by status, not deleted | A real misclassification: a "find/list/summarise" request routed as `publish_artifact` because the continuation step folded prior-turn text containing `.pptx` filenames into the classifier input | accepted (2026-06-13) |
| ADR-015 | Source-grounding backbone: durable source anchors keyed by stable provider identity (sourcedoc GUID / driveItem id — never title), resolved on reference before any live search; confirmed sources materialised at the retrieval checkpoint into `workspace/tasks/<id>/sources/<source-id>/<revision>/{raw,extracted}`; downstream reads the cached copy; revision change → `stale` | Reproduced `Test001` failure (2026-06-14): a follow-up "compare the 2 versions" dropped the v2 anchor (title-score below threshold), live-searched OneDrive, matched an unreadable `~$` Office lock stub, and the policy gate killed the run — even though the authoritative source with a working handle was still in session memory. The owner explicitly rejected score-tuning workarounds | accepted (2026-06-14); implementation = TODO-048, **in progress** |

Volatile status, as of 2026-07-02: ADR-015 materialisation is wired in both
pipeline and peer modes but gated **off by default** behind
`CRISAI_MATERIALISE_SOURCES` (`src/crisai/cli/pipelines.py:212-222`,
`.env.example:84` = `false`; this machine's local `.env` sets `true`, so local
behaviour is not shipped behaviour).

## 2. Invariants that must hold (with the enforcing code)

Each row is a guarantee the rest of the system relies on. Before weakening,
moving, or "simplifying" any of these, read the enforcing code and the ADR, and
assume the invariant exists because its absence already caused a real failure.

| # | Invariant | Enforced at | Failure mode it prevents |
|---|---|---|---|
| 1 | **Schema-backed handoffs.** Machine-critical inter-stage state travels as pinned JSON contracts, never prose. Evidence must be `evidence_bundle_v1` (`src/crisai/orchestration/evidence_contract.py:221`); after one repair retry, an invalid bundle hard-fails the run (`src/crisai/cli/pipelines.py:1295` pipeline, `:1757` peer). 12 schemas live in `src/crisai/schemas/`. | `evidence_contract.py:221`; `pipelines.py:1295,1757` | Downstream stages acting on a hallucinated or partial source list dressed up as prose |
| 2 | **`tools.allow` ∩ `tools.internal` = ∅.** `crisai doctor` errors on overlap (`src/crisai/registry_validation.py:373-378`). At runtime `tools.allow` becomes a static tool filter (`src/crisai/runtime.py:100`); `internal` tools are added only when `include_internal=True`, whose single caller is the deterministic materialisation path (`src/crisai/orchestration/source_fetch.py:64`). | `registry_validation.py:373-378`; `runtime.py:85-100` | An agent calling `download_source_bytes_by_handle` and pulling whole-file base64 into model context |
| 3 | **Evidence separated from prose (ADR-003).** `to_sanitized_dict` strips `read_handle` and sensitive metadata before anything durable/user-visible (`evidence_contract.py:95-98`); `sanitize_user_visible_text` strips machine JSON from user-facing rendering (`src/crisai/cli/display.py:267`). | `evidence_contract.py:95-98`; `display.py:267` | Graph handles persisted into session memory or shown to users; prose being parsed as evidence |
| 4 | **Single FastAPI network boundary.** `src/crisai/apps/web.py` is the only HTTP server in `src/crisai/` (grep for `FastAPI(` — one app); every configured MCP server in `registry/servers.yaml` is `transport: stdio` (remote SSE is supported by `runtime.py` but none is configured). Mandated by VISION.md Principle 8 (`reference/VISION.md:117-121`). | by construction; `registry/servers.yaml` | Unauthenticated side doors to LLM-spend or workspace-write operations |
| 5 | **Dot-file invisibility.** Any dot-prefixed workspace directory or file is pruned from the agent-visible surface during traversal (`src/crisai/workspace/safety.py:131-139`). Business content in dotfiles silently disappears from the corpus — by design. | `safety.py:110-145` | Agents reading local runtime/hidden state; users assuming dotfiles are retrievable |
| 6 | **`.crisai/` is agent-blocked.** `.crisai` is in `SENSITIVE_PATH_PARTS` (`safety.py:10-18`, alongside `.auth`, `.cache`, `.secrets`, `.tokens`, `chat_sessions`, `logs`); every workspace MCP tool resolves paths through `resolve_workspace_path` (`safety.py:54-71`, wired at `src/crisai/servers/workspace_server.py:46`), which also rejects root escapes (`safety.py:65-68`). Consequence: materialised sources are deliberately cached in the **visible** `workspace/tasks/<session>/sources/` tree, not `.crisai/` (`pipelines.py:255-260` — the comment states the reason), because agents must be able to read the cached copy. Beware: the docstring in `src/crisai/workspace/source_cache.py:4` still says `.crisai/sources/` — stale; the caller passes the task root. | `safety.py:10-18,54-71`; `workspace_server.py:46` | Agents reading session memory, token caches, or histories; agent-consumable data written somewhere agents cannot see |
| 7 | **Markdown as source, native documents as output (ADR-007).** Export tools take reviewed Markdown as input (`render_docx_from_markdown`, `render_pptx_from_markdown`) and may write only under `tasks/<task>/exports/` or `outputs/` (`src/crisai/servers/document_export_server.py:56-65`, `_enforce_output_path` raises otherwise). | `document_export_server.py:56-65` | Native binaries becoming the editable source of truth; exports landing in curated knowledge |
| 8 | **Structural, not prompt, enforcement.** The pipeline retrieval planner is made framing-only by *stripping* `sharepoint_docs`/`documents`/`intranet` from its server list (`pipelines.py:620-637`, applied at `:1207`) — the in-code comment records that the model searched OneDrive despite the prompt saying "do not retrieve" (commit `9c9ee2e`). Same doctrine: static tool filters (invariant 2), workspace write policy enforced server-side (`workspace_server.py:74-95`: authorised subdirs, extensions, max bytes via `CRISAI_WORKSPACE_WRITE_SUBDIRS`/`_EXTENSIONS`), and workflow gates (`src/crisai/cli/workflow_policy.py:282,294,313`). | `pipelines.py:620-637,1207`; `workspace_server.py:74-95` | Relying on an instruction a model can (and did) ignore |
| 9 | **Mode parity obligation.** A behavioural fix or gate landing in one mode must land in all applicable modes (`run_single:849`, `run_pipeline:1082`, `run_peer_pipeline:1543` in `pipelines.py`), and web/CLI surfaces must share semantics (ADR-009). There is no structural enforcement — this is a review obligation, and it is the repo's dominant regression pattern: parity fixes shipped as `a49593c` (#29, source-fit gate to pipeline), `0b63dbf` (#39, planner fallback to peer), `841769e` (#44, materialisation to peer). One parity gap is known-open — see weak point 1. | review discipline; no code gate | The same defect resurfacing in the mode the fix skipped |
| 10 | **Peer quality gate is hard.** A judge decision other than `accept` (after bounded refinement rounds and one escalation) raises `WorkflowValidationError` before finalisation — no best-effort output (`pipelines.py:2126-2129`). The peer verifier then checks written files against final-text claims with exactly one repair round (`src/crisai/orchestration/peer_verifier.py`, regexes from the semantic catalog). | `pipelines.py:2126-2129` | Unaccepted drafts silently shipping from the highest-cost path |

## 3. Known-weak points (stated plainly, as of 2026-07-02)

These are real, verified, and open. Do not design on the assumption any of them
is already fixed; do check the tracker reference before relying on this list.

1. **Peer planner still holds source-search tools (TODO-057).** Pipeline mode
   strips search servers from the planner (`pipelines.py:1207`); peer mode runs
   the planner with the raw spec — full `sharepoint_docs`/`documents`/`intranet`
   access (`pipelines.py:1677`). The Defect-B failure class (planner running a
   competing, wrong search) is structurally fixed in only one of the two
   retrieval-capable modes. Given weak invariant 9, this is the most predictable
   next live failure.
2. **The approvals policy is YAML with nothing behind it (TODO-032).**
   `registry/policies.yaml` declares `approvals: {enabled: true, default_mode:
   deny_for_unsafe_writes}` and `registry/servers.yaml` lists
   `approval.required_for` tools (`write_workspace_file`, `save_diagram`,
   `render_docx_from_markdown`) — but no Python file in `src/crisai/` references
   "approval" at all. There is no central approval gate. Real protection is the
   workspace server's path/write restrictions (invariants 6 and 8). Never
   describe an approval gate that does not exist.
3. **The Python↔TypeScript contract boundary is hand-synced.**
   `ui/packages/contracts/src/index.ts` (814 lines) manually mirrors the
   `ui_*` JSON schemas; no codegen, no CI drift check, and the UI unit tests that
   might catch drift are not run in CI (TODO-027). For a repo whose core rule is
   "machine-critical exchange must be schema-backed", the schemas' TS twin is
   unguarded.
4. **Catalog hard-fails, graph fails open.** A missing/invalid
   `semantic_catalog.yaml` raises (`src/crisai/orchestration/semantic_catalog.py:611`
   onwards) and the router calls it unguarded
   (`src/crisai/orchestration/router.py:394`) — the run dies. A missing/invalid
   `semantic_graph.yaml` returns `None` and the run continues in "fail-open mode"
   (`src/crisai/orchestration/retrieval_association_graph.py:148-163`; traced at
   `pipelines.py:927,1187,1661`). Two registry files, opposite failure semantics;
   a silently degraded graph is easy to miss.
5. **Catalog is cached, graph is re-read per message.** `load_semantic_catalog`
   is `@functools.lru_cache(maxsize=8)` (`semantic_catalog.py:591`);
   `deterministic_context_from_registry` re-reads and re-hashes
   `semantic_graph.yaml` on every call
   (`retrieval_association_graph.py:313-333`). Practical effect: catalog edits
   need a process restart to take effect; graph edits apply on the next message.
   A frequent source of "my registry edit did nothing" confusion.
6. **Evidence is parsed out of LLM prose.** The `evidence_bundle_v1` transport is
   recovered from model output text via a balanced-brace JSON scan
   (`evidence_contract.py:274-328`), with one repair retry before the hard fail
   (invariant 1). The gate is strict on schema, but the transport channel itself
   is still model text.
7. **Rate limiting is a single-process, in-memory, fixed-window counter — and off
   by default.** State is a module-level dict (`web.py:135`), window logic at
   `web.py:151-181`, default `0` = disabled (`web.py:133`,
   `CRISAI_RATE_LIMIT_RPM`); auth is a no-op unless `CRISAI_API_KEY` is set
   (`web.py:184-198`). Deliberate local single-user defaults, but nothing here is
   a multi-user or multi-process control (see TODO-052).
8. **A legacy API surface coexists with v1.** `/api/run`, `/api/run/start`,
   `/api/run/status/{job_id}`, `/api/run/checkpoint/{job_id}` (`web.py:1213-1355`)
   live alongside `/api/v1/*` (`web.py:1421` onwards); `ui/README` documents only
   v1. Any change to run semantics must cover both or consciously deprecate one;
   the rate-limited path set (`web.py:134`) already has to name both.

Related open fragilities owned by sibling skills: peer mode has zero partial
recovery on its highest-cost path (TODO-022) and trace/log write-time redaction
is incomplete (TODO-030) — see `crisai-failure-archaeology` and
`crisai-debugging-playbook` for the operational detail.

## Provenance and maintenance

Verified against `main` @ `c39273b` on 2026-07-02. Line numbers drift; re-verify
before citing:

- ADR list and statuses: `grep -n 'Status' reference/decisions/CRISAI-ADR-*.md`
- ADR-012 index staleness: `grep -n 'ADR-012' reference/decisions/README.md`
- Framing-only planner + peer gap: `grep -n '_framing_only_planner_spec\|specs\["retrieval_planner"\]' src/crisai/cli/pipelines.py`
- Evidence hard fail + judge gate: `grep -n 'raise WorkflowValidationError' src/crisai/cli/pipelines.py`
- Materialisation flag and cache location: `grep -n 'CRISAI_MATERIALISE_SOURCES\|task_dir(session_name)' src/crisai/cli/pipelines.py .env.example`
- allow/internal overlap check: `grep -n 'tools.internal' src/crisai/registry_validation.py`
- Internal-tool single caller: `grep -rn 'include_internal=True' src/crisai/`
- Sensitive paths / dot-file pruning: `grep -n 'SENSITIVE_PATH_PARTS\|startswith("\.")' src/crisai/workspace/safety.py`
- Export destination restriction: `grep -n '_enforce_output_path' src/crisai/servers/document_export_server.py`
- Auth / rate-limit defaults: `grep -n 'CRISAI_API_KEY\|CRISAI_RATE_LIMIT_RPM\|_RATE_LIMIT_STATE' src/crisai/apps/web.py`
- Legacy vs v1 endpoints: `grep -n '@app.post("/api/run\|@app.post("/api/v1' src/crisai/apps/web.py`
- Approval gate absence: `grep -rln 'approval' src/crisai --include='*.py'` (empty as of 2026-07-02)
- Catalog cache vs graph re-read: `grep -n 'lru_cache' src/crisai/orchestration/semantic_catalog.py src/crisai/orchestration/retrieval_association_graph.py`
- Evidence schema pin + brace scan: `grep -n "evidence_bundle_v1'\|_iter_bare_json_objects" src/crisai/orchestration/evidence_contract.py`
- TS contract twin: `wc -l ui/packages/contracts/src/index.ts && grep -c 'codegen\|generate' ui/packages/contracts/package.json`
- Open TODOs cited here: `grep -n 'TODO-057\|TODO-032\|TODO-027\|TODO-048\|TODO-022\|TODO-030' reference/TODO.md`
