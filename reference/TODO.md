# crisAI TODO

This backlog tracks future product and engineering improvements for crisAI.

Use this file for maintainable work items, not detailed design decisions. When an
item becomes architecture-shaping, add or update an ADR in
`reference/decisions/` and link it from the item.

The product direction and guiding principles are recorded in
[`VISION.md`](VISION.md).

## How To Maintain

- `Status`: todo, planned, in-progress, blocked, done, or dropped.
- `Priority`: P0 blocks the supported local team-adoption target; P1 is the next
  reliability, security, or core-product track; P2 is medium-term capability or
  maintainability work; P3 is optional polish or a conditional future surface.
- Keep one ownerless backlog here until the team adopts issue tracking.
- Move completed items to `Done` with the commit or PR reference.
- Split any item that cannot be completed and verified in one focused change.
- Keep semantics in registry files unless the item is explicitly infrastructure.
- Treat IDs as stable references, not strict priority order after new items are
  inserted. Use the `Priority` column and `Recommended Sequencing` section for
  execution order.

## Current Codebase Review

The current implementation is a strong local enterprise architecture workstation
foundation and is suitable for a controlled team pilot where each user runs an
independent local installation:

- agents are role-scoped and registry-configured;
- runtime semantics are mostly outside Python in registry files, with
  schema-backed request, task, evidence, peer, and UI contracts;
- evidence transport is separated from user prose and validated before summary
  or design stages;
- pipeline runs expose the routing/task-contract decision, stream stage output,
  and stop at a retrieval checkpoint before downstream drafting;
- token and estimated cost telemetry is recorded per stage and can be inspected
  with `crisai spend`;
- SharePoint/OneDrive document retrieval can read Office formats, including
  PowerPoint;
- intranet retrieval is provider-neutral, with SharePoint pages implemented;
- workspace, document, diagram, vision, export, SharePoint, and intranet MCP
  servers cover the main local and Microsoft 365 source types;
- task memory, durable source-anchor primitives, workspace evidence
  materialisation, workspace spaces, artefact profiles, ADRs, and broad automated
  tests are in place;
- API bearer authentication, execution rate limiting, sensitive-path blocking,
  restrictive token-cache creation, CI security scans, and registry validation
  provide a credible local security baseline.

The main gaps before broader local team adoption are:

- the source-grounding backbone is only partially integrated: durable anchors and
  the materialisation store exist, but checkpoint-time materialisation,
  anchor-first read-through, pin/retire controls, invalidation, and trace-visible
  cache reuse still need completion;
- no representative quality-evaluation baseline currently measures routing,
  retrieval/source fit, groundedness, artefact quality, human acceptance, cost,
  or latency against release thresholds;
- team ownership, contribution, security-reporting, release/versioning, support,
  and readiness expectations are not yet documented as a maintained operating
  model;
- trace/log write-time redaction, business-content handling guidance, and
  retention controls are incomplete;
- upgrade, rollback, backup/restore, and failure-recovery procedures are not yet
  defined and exercised;
- the prototype name `crisAI` is not yet aligned with a professional product,
  repository, package, and CLI identity for team adoption;
- a mid-peer-workflow stage failure terminates the run with no partial
  save or graceful degradation to the last completed stage;
- each agent has one configured model with no bounded provider/model failover;
- session memory is configurable globally, but not yet by task type, mode, or
  architecture workload profile, which can cause aggressive context collapse on
  extended architecture sessions;
- UI unit tests exist but are not run in CI; browser end-to-end, automated
  accessibility, concurrency, and recovery coverage are also missing;
- several core orchestration and API modules are large ownership hotspots that
  should be decomposed along existing contract and stage boundaries as the team
  grows;
- source coverage is still Microsoft-heavy, artefact templates and deterministic
  architecture quality gates are incomplete, and document export fidelity is
  not yet business-ready for all target artefacts;
- crisAI does not yet have a structured architecture roles and people directory,
  so agents cannot reliably identify who owns, reviews, assures, or signs off
  architecture artefacts.

A shared-machine or centrally hosted multi-user service is a separate maturity
target, not the current supported team topology. It additionally requires user
identity, role-based authorisation, per-user/workspace isolation, durable shared
run state, distributed quotas/rate limits, and production deployment controls.

## Backlog

| ID | Priority | Status | Item | Rationale | Definition of Done |
|---|---:|---|---|---|---|
| TODO-050 | P0 | todo | Team adoption governance and release baseline | The technical baseline is stronger than the repository operating model. Broader adoption needs explicit ownership, contribution, security-reporting, support, release, and readiness expectations to reduce bus-factor and review risk. | Add `CONTRIBUTING.md`, `SECURITY.md`, CODEOWNERS or an equivalent ownership map, supported local-team topology and data-handling policy, review/merge expectations, support and incident routes, versioning/release notes, dependency-update automation, and a release-readiness checklist. Reconcile maintained docs with the active agent/server inventory and define measurable pilot exit criteria. |
| TODO-051 | P0 | todo | Product quality evaluation and acceptance baseline | Passing deterministic tests does not establish that an LLM workflow retrieves the right sources, remains grounded, produces useful architecture artefacts, or does so within acceptable cost and latency. | Add a versioned representative evaluation set covering routing, named-source resolution, source fit, evidence grounding/citation, summary fidelity, architecture artefact quality, policy gates, cost, latency, and human acceptance. Define release thresholds, regression reporting, safe handling of evaluation sources, and a documented process for approving baseline changes. |
| TODO-030 | P0 | todo | Trace/log redaction, content handling, and retention controls | Traces and logs intentionally contain agent stage content and source excerpts. Git ignores do not protect local business content, and the configured `redact_secrets` policy is not yet a general write-time control. | All trace/log writers pass through shared redaction for API keys, bearer tokens, Microsoft auth payloads, client secrets, and configured patterns. Define business-content classification/handling guidance and configurable retention/size limits. Tests cover redaction and cleanup; documentation states what sensitive content may remain and who may access it. |
| TODO-048 | P0 | in-progress | Complete source-grounding backbone integration | ADR-015's anchor and materialisation primitives now exist, but the end-to-end find → confirm → reuse workflow is not complete. Until it is, a later turn can still fall back to mutable live retrieval instead of a confirmed source. | Complete per-turn intent isolation; anchor-first identity/alias/version/ordinal resolution; checkpoint-time materialisation; revision invalidation and stale status; downstream read-through from the cached copy; connector junk filtering; checkpoint pin/retire controls; and regression tests for the reproduced multi-turn failure. Machine state remains schema-backed and cache use is visible in traces. |
| TODO-003 | P0 | in-progress | Persistent retrieval cache lifecycle and reuse | The per-task source materialisation store is implemented, but live retrieval/checkpoint wiring, query/source revision reuse, bounded retention, and operator visibility are incomplete. | Validated evidence is reused by query fingerprint, stable source identity, and source revision/hash. Cache hits/misses and invalidation are visible in trace metadata. Stale entries use provider revision metadata or configured TTLs; cache size/age is bounded; task cleanup is documented. Coordinate with TODO-048, which owns anchor binding and workflow integration. |
| TODO-026 | P1 | todo | Product and repository rename | `crisAI` was the prototype name. Before broad rollout, the project should use a professional product, repository, package, CLI, docs, log, and MCP identity. This is adoption hygiene and should follow the P0 trust/governance baseline rather than displace it. | Rename the GitHub repository, Python package, CLI entry point, docs, UI labels, MCP server names, log labels, and setup instructions. Decide explicitly whether to keep a temporary `crisai` compatibility alias or remove it for a clean first team clone. Full test suite, doctor, packaging, and install-from-clone flow pass under the new name. |
| TODO-004 | P1 | todo | Authenticated website retrieval MCP | Enterprise architecture work often depends on protected vendor portals, internal web apps, design standards sites, and architecture repositories that are not SharePoint pages. crisAI needs a read-only OAuth/OIDC website source connector with strict scope controls. | Add an `authenticated_web` MCP server with login/auth-status, allow-listed hosts, OAuth/OIDC auth-code or device flow, URL fetch, optional rendered-page fetch for JS-heavy pages, link extraction, content normalization, source references, and tests with mocked OAuth and HTTP responses. Declares a `capabilities` block (CRISAI-ADR-013); the deferred capability-driven router family→server resolution and runtime evidence-ceiling checks can be built here against a concrete adapter. |
| TODO-031 | P1 | todo | Harden remote and custom MCP registry validation | Remote MCP servers and custom intranet providers are a trusted-code boundary. Before broader use, enabled remote/custom connectors should be explicit, least-privilege, and visibly risky in doctor output. | Doctor fails or warns on enabled remote MCPs with empty tool allowlists, literal `Authorization` headers, non-HTTPS URLs outside localhost, missing `auth` metadata, or high-risk custom provider paths. Documentation marks registry/custom providers as trusted admin configuration. Tests cover the validation cases. |
| TODO-053 | P1 | todo | Operational lifecycle, recovery, and upgrade runbooks | Clone-and-bootstrap setup is documented, but team operation also needs a safe path through upgrades, configuration changes, corrupted local state, provider outages, and restoration of task/knowledge artefacts. | Document and test supported upgrade and rollback paths, registry/schema migration expectations, backup/restore boundaries, log/cache cleanup, failed-run recovery, and provider outage procedures. Add at least one repeatable recovery drill and define which workspace state is authoritative versus rebuildable. |
| TODO-006 | P1 | todo | Architecture artefact template library | The tool is intended to support daily enterprise, solution, and data architecture work. It needs reusable structures beyond one-off generated Markdown. | Add governed templates for HLD, options paper, architecture decision record, data flow, data mapping, data lineage, NFR assessment, integration design, migration plan, and architecture review. Semantic graph has vertices for each template type so agents can discover them by topic during retrieval. Artefact validation has tests. |
| TODO-007 | P1 | todo | Knowledge promotion tooling | Curated knowledge needs a deliberate promotion path from task artefacts into `workspace/knowledge/`. | Add `/promote` workflow or command, provenance fields, staged/approved status, and validation of required YAML front matter. |
| TODO-008 | P1 | todo | Task lifecycle commands | Sessions and task workspaces need first-class lifecycle controls to reduce clutter and accidental context reuse. | Add `/tasks list`, `/tasks close <id>`, and `/tasks archive <id>` with tests and docs. Commands operate on `workspace/tasks/` without deleting user artefacts unexpectedly. |
| TODO-027 | P1 | todo | Test and resilience coverage hardening | Python coverage and CI are strong, and UI unit tests exist, but CI does not run those UI tests and the suite lacks browser end-to-end, automated accessibility, concurrency, recovery, and representative provider-path confidence. Deprecation warnings are also accumulating. | Run web and Gem tests in CI; add focused browser E2E tests for run, checkpoint, auth, error, and workspace flows; automate WCAG checks; add concurrency/rate-limit/run-state recovery coverage; fail or budget new deprecation warnings; and retain bounded optional provider smoke tests. Keep product-quality LLM evaluation in TODO-051. |
| TODO-010 | P1 | todo | Mermaid image embedding in exports | DOCX/PPTX exports should contain rendered diagrams, not raw Mermaid blocks, for business-ready architecture documents. | Export server renders Mermaid to SVG or PNG and embeds images in DOCX/PPTX. Source Markdown/Mermaid remains the canonical source. Broader export fidelity (tables, non-linear template section mapping) is tracked separately in TODO-021. |
| TODO-021 | P1 | todo | Document export fidelity | `render_docx_from_markdown` does line-by-line paragraph output. Markdown tables are not rendered as DOCX tables, and non-linear template section mapping (where DOCX heading order differs from Markdown heading order) is not supported. Business-ready documents require both. | Export server maps Markdown tables to native DOCX table objects. Template manifests can declare a section-to-content mapping so source sections fill named template headings in non-document order. Tests cover table round-trip and non-linear mapping. Diagram embedding is tracked separately in TODO-010. |
| TODO-018 | P1 | todo | Architecture quality gates | Review and judge agents exist, but artefact quality expectations for enterprise and data architecture are not yet enforced systematically. | Add profile-driven checks for assumptions, NFRs, data ownership, lineage, security/privacy, integration pattern fit, risks, decisions, and open questions. Gates are configurable and test-covered, and their outcomes feed the evaluation baseline in TODO-051. |
| TODO-032 | P1 | todo | Clarify or enforce MCP approval policy | `registry/servers.yaml` and `registry/policies.yaml` describe approval requirements, but effective protection currently comes mainly from server-side path/write restrictions. The configuration should not imply a stronger central approval gate than exists. | Either implement a central approval gate for tools marked under `approval.required_for`, or rename/document approval metadata as advisory/local policy. Tests prove write tools cannot bypass the intended control path. README/DOCUMENTATION explain the actual trust model. |
| TODO-038 | P1 | todo | Agent model API resilience | Each agent is wired to a single `model_ref` with no fallback. A provider API failure causes the entire run to fail with limited recovery guidance. | Registry supports an optional bounded `fallback_model_ref` per agent. Retriable rate-limit/timeout failures retry once using governed policy, with provider, model, stage, error type, and fallback decision traced. Non-retriable failures remain fail-closed and test-covered. |
| TODO-055 | P1 | todo | Source-fit title-phrase extraction precision | `infer_source_fit_constraints` can extract instruction words as spurious title phrases. Because title matching is OR-based, this can weaken inventory/content-read source-fit gates and admit an off-title source. | Stop title-phrase extraction at instruction/noise tokens; retain only genuine title phrases; prove the inventory and content-read gates reject off-title rows without rejecting legitimate inventories; and cover the reproduced noisy-instruction prompt. |
| TODO-057 | P1 | todo | Peer-mode framing-only planner tool scoping | The pipeline retrieval planner is framing-only and tool-less, but peer mode still executes its planner through a generic loop with source-search tools. That permits competing retrieval, unnecessary spend, and a least-privilege inconsistency. | Run the peer retrieval-planner stage without source-search servers, matching pipeline behaviour; keep single-agent retrieval fully tooled; and cover the stage-specific tool scope with tests. |
| TODO-040 | P1 | in-progress | React web and Ink Gem on shared UI contract | The shared `ui_event_v1` and `/api/v1/runs` contract now backs the active React web and Ink Gem clients. The remaining gap is product-quality depth across stage rendering, checkpoint UX, final output, error states, install docs, accessibility, and CI checks. Current follow-ups include aligning toggle markup with the UCL switch pattern, adding alert live-region semantics, deciding whether Gem should expose the same per-run retrieval checkpoint toggle as React web, and documenting upload limits in the UI. | React web and Ink Gem consume the shared v1 endpoints with production-quality stage rendering, checkpoint UX, final output, error states, install docs, keyboard/accessibility behaviour, and UI unit tests executed in CI. Browser E2E and broader resilience coverage remain under TODO-027. |
| TODO-022 | P1 | todo | Peer workflow partial recovery | If a challenger, refiner, or judge stage times out or fails mid-run, the whole peer workflow terminates hard with no output saved. Given the cost of peer runs, partial save and graceful degradation to the last completed stage are important. VISION Principle 3 (user control at costly decisions) applies directly: peer runs are the highest-cost execution path. | When a non-retrieval peer stage fails, the workflow saves the last successfully completed stage output, traces the failure with stage identity, and surfaces a recoverable error to the user rather than discarding all upstream work. Behaviour is test-covered. |
| TODO-023 | P1 | todo | Session memory tuning | The default global compact-memory limits can be aggressive for extended architecture sessions with retrieved source material, causing effective context collapse. | Make memory limits configurable per task type, mode, or workload profile in `registry/session_memory.yaml`; review defaults for primary use cases; preserve source anchors independently from prose compaction; document and test behaviour. |
| TODO-047 | P1 | todo | Portable knowledge artefact validation for the external knowledge repo CI | The curated knowledge base lives in its own repository, but its CI does not yet enforce the full crisAI artefact profiles. Team-authored knowledge can therefore pass a weaker gate than runtime-authored knowledge. | Provide a supported validator for an arbitrary knowledge tree and run it in the knowledge repository's CI, enforcing required sections, type aliases, provenance/front matter, and slug uniqueness. Document and test the integration. |
| TODO-013 | P2 | todo | Dynamic model selection | Routing and task criticality should influence model tier instead of using only static agent assignments. | Model policy remains in registry/config. Router/task contract can select a model tier for supported agents. Decisions are traced and test-covered. |
| TODO-014 | P2 | todo | Incremental workspace semantic index | `document_server` has a local context index, but it is rebuilt manually/on demand and is not a persistent, incremental workspace knowledge service. | Add an incremental index updated on writes or explicit rebuild. Retrieval uses the index when fresh and falls back safely when stale/missing. Include freshness metadata and tests. |
| TODO-015 | P2 | todo | Cross-task memory summary | Useful decisions and artefacts can span tasks, but full history replay is too expensive. | Maintain a compact workspace-level summary of decisions, artefacts, and open questions. Include it only when relevant and trace when used. |
| TODO-016 | P2 | todo | Routing feedback capture | User mode overrides are valuable correction signals for improving routing behaviour. | Record explicit overrides as structured events. Provide an analytics view or export that can inform catalog/graph tuning without silently changing behaviour. |
| TODO-009 | P2 | todo | Unified synonym and graph expansion | Search expansion should be consistent across intranet search, workspace search, routing, and prompt scaffolding. | `search_synonyms.yaml` is merged into or cross-referenced from the semantic graph. Expansion behaviour has regression tests and a single documented source of truth. |
| TODO-011 | P2 | todo | Second intranet adapter: Confluence | The intranet provider interface is ready; Confluence support would validate provider neutrality and broaden adoption after the local trust baseline is complete. | Add a Confluence provider implementing search, fetch, link listing, auth/status where applicable, config docs, and tests with mocked API responses. |
| TODO-012 | P2 | todo | Enterprise data catalogue MCP | Data architecture work needs direct access to glossary terms, data products, schemas, lineage, owners, classifications, and quality metadata. This is medium-term capability expansion rather than a local pilot blocker. | Add a provider-shaped MCP for at least one catalogue family, preferably Microsoft Purview first, with search/fetch tools, lineage/owner metadata, registry config, evidence source references, and mocked tests. Build on the source capability contract and keep other providers extensible. |
| TODO-045 | P2 | todo | Structured artefact editor enhancements | TODO-025 shipped the editor core. Remaining profile-aware forms, section navigation, Mermaid affordances, and validation feedback improve usability but do not block the controlled local pilot. | Add artefact-profile-aware fields, long-document section navigation, Mermaid preview/editing, and profile-driven validation feedback using the existing editor registry. |
| TODO-040A | P2 | todo | Web stage rail auto-scrolls active stage into view | The focused run view follows the active agent, but a long stage rail does not scroll the active item into view. | Scroll the live stage into view without disrupting keyboard navigation or a user-pinned selection; verify mobile, desktop, and reduced-motion behaviour. |
| TODO-046 | P2 | todo | Knowledge freshness (last_reviewed) report | Knowledge artefacts carry a `last_reviewed` date and `owner`, but nothing surfaces stale entries, so the curated corpus can silently drift out of date as institutional sources change. | A `crisai` command or report lists knowledge artefacts whose `last_reviewed` is older than a configurable window (optionally per type), with owner and path, so reviewers can act before grounding degrades. Behaviour is documented and test-covered. |
| TODO-033 | P2 | todo | Architecture roles and people directory design | Agents need a reliable, governed source of truth for architecture stakeholders before they can route review, assurance, or sign-off tasks. | Design a privacy-aware `reference/` structure for role, function, scope, domain, authority, contact channel, escalation path, and ownership boundaries. Include validation and agent-use guidance. |
| TODO-034 | P2 | todo | Human assurance and sign-off operating model design | Formal review automation must not precede a clear accountable human operating model. | Produce an ADR defining review states, responsibilities, gates, artefact types, sign-off criteria, exceptions, audit trail, and the boundary between AI critique, human assurance, and formal approval. |
| TODO-035 | P2 | todo | Assurance agents and asynchronous review tooling design | Review-pack preparation and tracking may be useful after roles and governance are defined, but it is not a prerequisite for the local workstation pilot. | After TODO-033 and TODO-034, design narrow agent roles, allowed tools, state contracts, submission flow, provider-neutral storage, and failure handling. Do not implement formal approval replacement. |
| TODO-054 | P2 | todo | Decompose core ownership hotspots | Core orchestration and API modules have accumulated multiple responsibilities, increasing review cost and conflict risk as contributor count grows. | Identify stable contract/stage boundaries in `cli/pipelines.py`, `apps/web.py`, prompt generation, and session context; split incrementally without behaviour changes; document module ownership; preserve or improve coverage; and avoid abstraction that merely relocates complexity. |
| TODO-052 | P2 | todo | Shared-service identity and isolation architecture | Static bearer auth, process-local rate limiting, in-memory jobs, and one workspace are appropriate for the current local workstation, not for a centrally hosted multi-user service. This work is conditional on choosing that deployment topology. | Before any shared deployment, write an ADR and implement OIDC-backed user identity, RBAC, per-user/project workspace and session isolation, audit attribution, durable run state, distributed quotas/rate limits, deployment secrets, and multi-user threat tests. Local-per-user installs remain the supported topology until this is complete. |
| TODO-049 | P2 | todo | Semantic catalog hygiene: cross-bucket overlap and DA vocab single-ownership | Two consistency findings from the semantic-layer review remain. (1) Several router terms sit in more than one bucket — `judge` in both `peer_terms` and `review_terms`, `refine`/`refiner` across `review_terms` and `peer_terms`, `draft` in `design_terms` and `interaction.generative_peer_patterns`, and `option(s)` under `design_terms` although options analysis is its own graph intent — so the additive router score is muddier than it needs to be even though graph priorities disambiguate the contract. (2) Data-architecture vocabulary has two homes: `peer_verifier.data_architecture_terms` in `registry/semantic_catalog.yaml` and `data_architecture_core` in `registry/semantic_graph.yaml`, which drifts from the CLAUDE.md ownership rule (the graph owns source-family/deliverable vocabulary). | Each overlapping router term has a documented primary bucket, or the overlap is recorded as intentional with a one-line rationale; the router golden set (`tests/unit/test_router_regression.py`) is unchanged and passing. Data-architecture vocabulary has a single owner: the catalog `peer_verifier.data_architecture_terms` and graph `data_architecture_core` are reconciled so no DA term is duplicated across the two files, consumers read from the owning file, and tests cover the reconciled behaviour. Both are registry/doc edits with no routing behaviour change (CRISAI-ADR-002, CRISAI-ADR-014). |
| TODO-056 | P2 | todo | Lean routing for pure source-inventory asks | A pure "find/list files" inventory ask (deliverable `source_inventory`, evidence `metadata_read`) over-routes to `mixed_complexity`/pipeline (design + review) rather than a lean discovery/single path — heavier latency and tokens, and before PR #29 it bypassed the single-path inventory source-fit gate (now mode-independent). Surfaced in the test003 assessment. | The router keeps a metadata-only source-inventory ask on discovery/single (or an equivalently lean path) unless the user also asks for synthesis; golden routing cases cover the test003 prompt; the inventory source-fit gate still applies on whichever path is chosen. |
| TODO-020 | P3 | todo | Multi-workspace support | Users may need clean isolation across projects, clients, or architecture domains. | Add `/workspace switch <path>` and related status/doctor support. Registry and task state isolation are explicit and tested. |
| TODO-039 | P3 | todo | Configurable Gem themes and templates | Gem should use accessible defaults, but organisations may eventually need alternate palettes, density, and component templates without code changes. | Add validated registry/config-backed Gem theme and layout templates with UCL dark, UCL light, and high-contrast defaults. Preserve accessibility and test fallback behaviour. |

## Recommended Sequencing

1. Complete `TODO-050`, `TODO-051`, and `TODO-030` as the local team-adoption
   gate: ownership/release discipline, measurable product quality, and safe
   handling of trace/log content.
2. Finish `TODO-048` and `TODO-003` together. The source anchor must resolve to
   reusable materialised evidence end to end; neither item is complete while a
   confirmed follow-up can regress to mutable live retrieval. Complete
   `TODO-055` and `TODO-057` in the same trust track so source-fit constraints
   and planner tool scope do not weaken that backbone.
3. Complete `TODO-027`, `TODO-053`, and `TODO-032` to establish test, recovery,
   and actual approval-policy confidence before widening the pilot.
4. Implement `TODO-026` before broad rollout to avoid repository, package, CLI,
   and documentation churn after many users have configured installations.
5. Complete `TODO-038`, `TODO-022`, and `TODO-023` as the execution-resilience
   track: provider failure, partial peer recovery, and long-session continuity.
6. Finish `TODO-040`, then address `TODO-040A` and `TODO-045` according to pilot
   feedback. The active clients already share the v1 contract; remaining work is
   parity depth, accessibility, and usability rather than another rebuild.
7. Build `TODO-006`, `TODO-018`, `TODO-021`, and `TODO-010` as the core
   business-ready artefact quality track.
8. Complete `TODO-047`, `TODO-007`, `TODO-008`, and `TODO-046` to govern the
   knowledge and task lifecycle used by a team.
9. Harden remote connector trust with `TODO-031` before enabling remote/custom
   MCPs for other users; then implement `TODO-004`, followed by medium-term
   provider expansion in `TODO-011` and `TODO-012`.
10. Design `TODO-033` and `TODO-034` before `TODO-035`. Formal assurance tooling
    must follow accountable human roles and sign-off rules.
11. Start conditional `TODO-052` only if the product chooses a shared-machine or
    centrally hosted topology. Static bearer auth and local process state must
    not be treated as multi-user controls.
12. Take `TODO-054` incrementally alongside feature work when a touched ownership
    hotspot has a clear contract boundary; do not pause delivery for a broad
    rewrite.

## Done

Completed items should move here with the merge commit or PR reference.

| ID | Item | Reference |
|---|---|---|
| TODO-001 | Human checkpoint after retrieval | `b1959b9 feat(pipeline): add retrieval checkpoint` |
| TODO-002 | Streaming stage output | `461461e feat(ui): stream stage output in clients` |
| TODO-002A | Browser viewport pass for streaming card | `fix(web): bound streaming viewport layout` |
| TODO-043 | CI security scanning | `ci: add security scanning gates` |
| TODO-005 | Token and cost tracking per stage | `6398d8e feat(runtime): track stage cost telemetry`, `7d7ba13 feat(cli): add spend command for cost telemetry`, `83d3287 fix(cli): harden spend parser against non-dict JSONL` |
| TODO-037 | First-run and team onboarding experience | `docs(runtime): improve first-run onboarding checks` |
| TODO-041 | API authentication and authorisation guard (Phase 1 — static bearer token) | `2ea5457 feat(security): add Bearer token auth guard`, `800e2d7 fix(security): harden api bearer comparison` |
| TODO-024 | Web document upload | `a2b3f5c docs(todo): mark TODO-041 done and update sequencing` |
| TODO-036 | Routing decision transparency | `feat(ui): expose request contract before execution` |
| TODO-028 | Block agent access to local auth and secret folders | `fix(runtime): block sensitive workspace paths` |
| TODO-029 | Restrictive permissions for token caches | `fix(security): restrict microsoft token cache permissions` |
| TODO-044 | Image-only / scanned PDF reading via vision | `feat(documents): read image-only PDFs via the vision model` |
| TODO-025 | Structured web artefact editor (core) | `1108d47 feat(web): content-type editor registry + CodeMirror engine`, `671fb13 feat(web): Markdown WYSIWYG editor (Toast UI)`, `cf4d830 feat(web): editor validation, states, a11y + lazy-load`. Remaining niceties tracked in TODO-045. |
| TODO-042 | Rate limiting on execution endpoints | `8badc2e feat(web): add per-minute rate limit on execution endpoints`, `47cdc97 fix(web): add /api/run/start to rate-limited paths` |
| TODO-040B | Visible checkpoint indicator while streaming | `f57ce9b feat(web): focused run view that follows the active agent` — the retrieval checkpoint is now an above-the-fold modal overlay (Continue/Redirect/Stop), so it cannot be missed below the streaming card. The modal supersedes the original sticky-banner idea and intentionally overlays run output while a decision is pending. |
| TODO-017 | Source connector capability contract | `CRISAI-ADR-013` + `feat(registry): source connector capability contract` (Phase 0–1: `kind` + `capabilities` block on every source server, `SourceCapability` loader, doctor validation) and `feat(retrieval): registry-derived source tool guidance` (Phase 2: `render_source_tool_guidance` generates the retrieval source-tool guidance from the contract; hardcoded intranet/SharePoint tool lists removed). Advisory `pagination`/`freshness` fields are declared for future consumers (TODO-003/004); deeper router scope→server mapping can build on the contract later. |
| TODO-019 | Legacy web UI rebuild | Superseded by the shared React web/Ink Gem contract work under TODO-040. The active web surface already provides routing, streamed stages, retrieval checkpoints, workspace browsing/editing, and peer transcript rendering; remaining parity and polish stay in TODO-040/040A/045. |
