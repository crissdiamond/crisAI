# crisAI TODO

This backlog tracks future product and engineering improvements for crisAI.

Use this file for maintainable work items, not detailed design decisions. When an
item becomes architecture-shaping, add or update an ADR in
`reference/decisions/` and link it from the item.

The product direction and guiding principles are recorded in
[`VISION.md`](VISION.md).

## How To Maintain

- `Status`: todo, planned, in-progress, blocked, done, or dropped.
- `Priority`: P0 highest, then P1, P2, P3.
- Keep one ownerless backlog here until the team adopts issue tracking.
- Move completed items to `Done` with the commit or PR reference.
- Split any item that cannot be completed and verified in one focused change.
- Keep semantics in registry files unless the item is explicitly infrastructure.
- Treat IDs as stable references, not strict priority order after new items are
  inserted. Use the `Priority` column and `Recommended Sequencing` section for
  execution order.

## Current Codebase Review

The current implementation is a solid local enterprise architecture workstation
foundation:

- agents are role-scoped and registry-configured;
- runtime semantics are mostly outside Python in registry files;
- evidence transport is separated from user prose and validated before summary
  or design stages;
- SharePoint/OneDrive document retrieval can read Office formats, including
  PowerPoint;
- intranet retrieval is provider-neutral, with SharePoint pages implemented;
- workspace, document, diagram, vision, export, SharePoint, and intranet MCP
  servers cover the main local and Microsoft 365 source types;
- task memory, workspace spaces, artefact profiles, ADRs, and tests are now in
  place.

The main product gaps are:

- pipeline runs now include a retrieval checkpoint and expose the initial
  routing/task-contract decision before agent execution;
- stage output now streams through the shared v1 event contract into React web
  and Ink Gem, with the streaming card viewport pass complete;
- retrieval does not persist validated evidence across iterative runs;
- the prototype name `crisAI` is not yet aligned with a professional product,
  repository, package, and CLI identity for team adoption;
- source coverage is still Microsoft-heavy and does not cover generic OAuth web
  apps, Confluence, or enterprise data catalogues;
- architecture artefact production is not yet guided by a full template library
  for HLD, options papers, data architecture, lineage, and NFRs;
- knowledge promotion is documented as a space but not yet a governed workflow;
- token/cost telemetry is not surfaced per stage, agent, and model;
- document export fidelity is limited: tables and non-linear template sections
  are not yet mapped correctly beyond basic paragraph and Mermaid rendering;
- a mid-peer-workflow stage failure terminates the run with no partial
  save or graceful degradation to the last completed stage;
- session memory is configurable globally, but not yet by task type, mode, or
  architecture workload profile, which can cause aggressive context collapse on
  extended architecture sessions;
- the React web app can browse, edit, and upload workspace files, but still
  needs production-quality artefact editing and richer run observability;
- the web file editor is Markdown/text-oriented, which is too technical for
  users who want structured editing of architecture artefacts without Markdown
  knowledge;
- web UX follows CLI concepts and now consumes streamed stage output, but still
  needs deeper checkpoint, error-state, and peer transcript parity.
- shared UI schemas, v1 runtime events, React web, and Ink Gem now own the
  active UI surface; remaining work should focus on parity depth, polish,
  accessibility, and operational resilience.
- local security controls need hardening before team/shared-machine use:
  agents should not be able to read auth caches or secret folders, Microsoft
  token caches need restrictive permissions, trace/log redaction needs to be
  enforced, and remote/custom MCP configuration needs stronger validation.
- crisAI does not yet have a structured architecture roles and people directory,
  so agents cannot reliably identify who owns, reviews, assures, or signs off
  architecture artefacts.
- crisAI does not yet support a governed asynchronous human assurance and
  sign-off process for generated architecture artefacts.

## Backlog

| ID | Priority | Status | Item | Rationale | Definition of Done |
|---|---:|---|---|---|---|
| TODO-003 | P0 | todo | Persistent retrieval cache | Repeated source reads during iterative tasks waste time and tokens. Evidence bundles can be reused when the query and source revision are unchanged. | Evidence bundles are cached by query fingerprint, source identity, and source revision/hash. Cache hits are visible in trace metadata. Stale entries are invalidated using provider revision metadata where available, such as ETag, source version, Graph `lastModifiedDateTime`, content hash, or configurable TTL expiry. |
| TODO-026 | P0 | todo | Product and repository rename | `crisAI` was the prototype name. Before broader team adoption, the project should use a professional product, repository, package, CLI, docs, log, and MCP identity such as `Architecture Assistant`, `architecture-assistant`, `architecture_assistant`, and `arch-assistant`. Doing this early avoids team-facing churn later. | Rename the GitHub repository, Python package, CLI entry point, docs, UI labels, MCP server names, log labels, and setup instructions. Decide explicitly whether to keep a temporary `crisai` compatibility alias or remove it for a clean first team clone. Full test suite, doctor, packaging, and install-from-clone flow pass under the new name. |
| TODO-042 | P1 | todo | Rate limiting on execution endpoints | `/api/run` and `/api/v1/runs` trigger LLM calls with no request-rate guard. A misconfigured client or accidental loop could exhaust the model provider budget before the user notices. VISION Principle 8 requires token spend to be rate-guarded. | Execution endpoints enforce a configurable per-key or per-IP rate limit (e.g. N requests per minute). Limit breach returns 429 with a `Retry-After` header. Limits are configured via registry or env var. Tests cover limit enforcement and bypass attempts. |
| TODO-004 | P1 | todo | Authenticated website retrieval MCP | Enterprise architecture work often depends on protected vendor portals, internal web apps, design standards sites, and architecture repositories that are not SharePoint pages. crisAI needs a read-only OAuth/OIDC website source connector with strict scope controls. | Add an `authenticated_web` MCP server with login/auth-status, allow-listed hosts, OAuth/OIDC auth-code or device flow, URL fetch, optional rendered-page fetch for JS-heavy pages, link extraction, content normalization, source references, and tests with mocked OAuth and HTTP responses. |
| TODO-030 | P1 | todo | Trace and log secret redaction and retention controls | Traces and logs intentionally contain agent stage content and source excerpts. They are ignored by git, but the configured `redact_secrets` policy is not yet enforced as a general write-time redaction layer. | All trace/log writers pass through a shared redaction function for API keys, bearer tokens, Microsoft auth payloads, client secrets, and configured secret patterns. Redaction is tested. Optional retention controls can cap age/size of local trace and MCP log files. Documentation states that traces may still contain sensitive business content. |
| TODO-031 | P1 | todo | Harden remote and custom MCP registry validation | Remote MCP servers and custom intranet providers are a trusted-code boundary. Before broader use, enabled remote/custom connectors should be explicit, least-privilege, and visibly risky in doctor output. | Doctor fails or warns on enabled remote MCPs with empty tool allowlists, literal `Authorization` headers, non-HTTPS URLs outside localhost, missing `auth` metadata, or high-risk custom provider paths. Documentation marks registry/custom providers as trusted admin configuration. Tests cover the validation cases. |
| TODO-006 | P1 | todo | Architecture artefact template library | The tool is intended to support daily enterprise, solution, and data architecture work. It needs reusable structures beyond one-off generated Markdown. | Add governed templates for HLD, options paper, architecture decision record, data flow, data mapping, data lineage, NFR assessment, integration design, migration plan, and architecture review. Semantic graph has vertices for each template type so agents can discover them by topic during retrieval. Artefact validation has tests. |
| TODO-007 | P1 | todo | Knowledge promotion tooling | Curated knowledge needs a deliberate promotion path from task artefacts into `workspace/knowledge/`. | Add `/promote` workflow or command, provenance fields, staged/approved status, and validation of required YAML front matter. |
| TODO-008 | P1 | todo | Task lifecycle commands | Sessions and task workspaces need first-class lifecycle controls to reduce clutter and accidental context reuse. | Add `/tasks list`, `/tasks close <id>`, and `/tasks archive <id>` with tests and docs. Commands operate on `workspace/tasks/` without deleting user artefacts unexpectedly. |
| TODO-009 | P1 | todo | Unified synonym and graph expansion | Search expansion should be consistent across intranet search, workspace search, routing, and prompt scaffolding. | `search_synonyms.yaml` is merged into or cross-referenced from the semantic graph. Expansion behaviour has regression tests and a single documented source of truth. |
| TODO-010 | P1 | todo | Mermaid image embedding in exports | DOCX/PPTX exports should contain rendered diagrams, not raw Mermaid blocks, for business-ready architecture documents. | Export server renders Mermaid to SVG or PNG and embeds images in DOCX/PPTX. Source Markdown/Mermaid remains the canonical source. Broader export fidelity (tables, non-linear template section mapping) is tracked separately in TODO-021. |
| TODO-011 | P1 | todo | Second intranet adapter: Confluence | The intranet provider interface is ready; Confluence support would validate provider neutrality and broaden adoption in enterprise architecture teams. | Add a Confluence provider implementing search, fetch, link listing, auth/status where applicable, config docs, and tests with mocked API responses. |
| TODO-012 | P1 | todo | Enterprise data catalogue MCP | Data architecture work needs direct access to glossary terms, data products, schemas, lineage, owners, classifications, and quality metadata. SharePoint documents are not enough. | Add a provider-shaped MCP for at least one catalogue family, preferably Microsoft Purview first, with search/fetch tools, lineage/owner metadata, registry config, evidence source references, and mocked tests. Keep Collibra/Atlan as future adapters. |
| TODO-017 | P1 | todo | Source connector capability contract | More MCP sources are coming. Agents and router need to know source capabilities without prompt patches or hardcoded assumptions. This is a prerequisite for TODO-004 and TODO-012 to avoid retrofitting the contract after those adapters are built. | Add registry metadata for source capabilities such as search, fetch, list, auth, source type, evidence level, binary support, pagination, and freshness. Retrieval prompts and tests consume this metadata. |
| TODO-021 | P1 | todo | Document export fidelity | `render_docx_from_markdown` does line-by-line paragraph output. Markdown tables are not rendered as DOCX tables, and non-linear template section mapping (where DOCX heading order differs from Markdown heading order) is not supported. Business-ready documents require both. | Export server maps Markdown tables to native DOCX table objects. Template manifests can declare a section-to-content mapping so source sections fill named template headings in non-document order. Tests cover table round-trip and non-linear mapping. Diagram embedding is tracked separately in TODO-010. |
| TODO-025 | P1 | todo | Structured web artefact editor | The current web editor exposes raw Markdown, which is efficient for developers but not friendly for architects who want to review and refine HLDs, options papers, decisions, and data architecture artefacts without learning Markdown syntax. | Add a structured editor for supported artefact profiles with section navigation, form-like fields for metadata/front matter, rich text controls for paragraphs and lists, table editing, Mermaid preview/edit affordances, validation feedback, and Markdown round-trip persistence. Raw Markdown remains available as an advanced/source mode. |
| TODO-033 | P1 | todo | Architecture roles and people directory design | Agents need a reliable, governed source of truth for architecture stakeholders before they can route review, assurance, or sign-off tasks. This should describe roles, functions, scope, architecture area, and contact channels without hardcoding people in prompts. | Design a `reference/`-based people/roles structure with fields for role, function, scope, domain/area, authority level, contact details, preferred channel, escalation path, and ownership boundaries. Include privacy/security guidance, sample entries, validation expectations, and how agents may use the directory. |
| TODO-034 | P1 | todo | Human assurance and sign-off operating model design | Architecture artefacts such as HLDs, option papers, ADRs, and technical designs need accountable human review and sign-off. The workflow must be designed before adding agents or tools, because it affects governance, document state, auditability, and exception handling. | Produce an ADR/design note defining review states, responsibilities, review gates, artefact types, sign-off criteria, exception paths, audit trail requirements, ownership handoffs, and the difference between AI critique, human assurance, and formal approval. |
| TODO-035 | P1 | todo | Assurance agents and asynchronous review tooling design | A new agent or set of agents may support review-pack preparation, reviewer routing, submission tracking, reminders, and approval-state updates, but those roles must be narrowly scoped and tied to human accountability. | Design the agent roles, allowed tools, MCP/server needs, state model, document submission flow, shared-location strategy, and failure handling for asynchronous review. Cover SharePoint/Teams first, with provider-neutral extension points for other document stores or workflow systems. No implementation until TODO-033 and TODO-034 are complete. |
| TODO-037 | P1 | todo | First-run and team onboarding experience | TODO-026 covers the rename, but there is no item for the practical onboarding path a new team member follows after cloning. Without a clear setup guide and first-run validation, team adoption remains friction-heavy regardless of the product name. | Add a team onboarding guide (README section or separate doc) covering environment prerequisites, `.env` setup, API key configuration, first-run `doctor` output, model provider smoke tests, and a short example run. `doctor` validates all required env variables at startup and emits actionable messages for common setup errors. Tests cover `.env.example` completeness and doctor env-var checks. |
| TODO-039 | P1 | todo | Configurable Gem themes and templates | Gem should use UCL-aligned defaults, but teams and organisations may need alternate terminal palettes, layout density, and component templates without editing Python code. | Add registry/config-backed Gem theme and layout templates with defaults for UCL dark, UCL light, and high-contrast. `crisai gem` loads the selected template from config, validates required tokens, falls back safely, and documents how teams can customise colours/backgrounds while preserving accessibility. Tests cover template loading, fallback, and token validation. |
| TODO-040 | P1 | in-progress | React web and Ink Gem on shared UI contract | The shared `ui_event_v1` and `/api/v1/runs` contract now backs the active React web and Ink Gem clients. The remaining gap is product-quality depth across stage rendering, checkpoint UX, final output, error states, install docs, accessibility, and CI checks. Current follow-ups include aligning toggle markup with the UCL switch pattern, adding alert live-region semantics, deciding whether Gem should expose the same per-run retrieval checkpoint toggle as React web, and documenting upload limits in the UI. | React web and Ink Gem consume `/api/v1/runs`, `/api/v1/runs/{id}`, `/api/v1/runs/{id}/events`, `/api/v1/runs/{id}/checkpoint`, and `/api/v1/ui/theme` with production-quality stage rendering, checkpoint UX, final output, error states, install docs, and CI type checks. |
| TODO-040A | P1 | todo | Web stage rail follows active run stage | React web shows the latest live stage in the streaming card, but the stage rail is not a selected or focused-stage control and does not auto-scroll to the current running stage. With many stages, the active stage can be outside the visible rail viewport even while live output is correct. | During an active run, the stage rail visibly tracks the currently running stage without disrupting keyboard navigation or user-selected detail views. Long stage lists keep the active stage reachable and visible across mobile and desktop viewports. Tests or manual viewport evidence cover many-stage runs, overflow handling, and reduced-motion behaviour. |
| TODO-040B | P1 | todo | Visible checkpoint indicator while streaming | When checkpoint state and live stage streaming coexist, React web exposes the decision through status text and an aria-live region, and controls remain reachable by scroll and keyboard. Sighted users may still miss that a decision is waiting because the checkpoint panel can start below the streaming card. | Add an above-the-fold checkpoint indicator, such as a sticky banner or status strip, that appears while a checkpoint is waiting during live streaming. The indicator must not cover input or transcript content, must preserve keyboard access to checkpoint controls, and must be verified at mobile and desktop viewports. |
| TODO-022 | P1 | todo | Peer workflow partial recovery | If a challenger, refiner, or judge stage times out or fails mid-run, the whole peer workflow terminates hard with no output saved. Given the cost of peer runs, partial save and graceful degradation to the last completed stage are important. VISION Principle 3 (user control at costly decisions) applies directly: peer runs are the highest-cost execution path. | When a non-retrieval peer stage fails, the workflow saves the last successfully completed stage output, traces the failure with stage identity, and surfaces a recoverable error to the user rather than discarding all upstream work. Behaviour is test-covered. |
| TODO-013 | P2 | todo | Dynamic model selection | Routing and task criticality should influence model tier instead of using only static agent assignments. | Model policy remains in registry/config. Router/task contract can select a model tier for supported agents. Decisions are traced and test-covered. |
| TODO-014 | P2 | todo | Incremental workspace semantic index | `document_server` has a local context index, but it is rebuilt manually/on demand and is not a persistent, incremental workspace knowledge service. | Add an incremental index updated on writes or explicit rebuild. Retrieval uses the index when fresh and falls back safely when stale/missing. Include freshness metadata and tests. |
| TODO-015 | P2 | todo | Cross-task memory summary | Useful decisions and artefacts can span tasks, but full history replay is too expensive. | Maintain a compact workspace-level summary of decisions, artefacts, and open questions. Include it only when relevant and trace when used. |
| TODO-016 | P2 | todo | Routing feedback capture | User mode overrides are valuable correction signals for improving routing behaviour. | Record explicit overrides as structured events. Provide an analytics view or export that can inform catalog/graph tuning without silently changing behaviour. |
| TODO-018 | P2 | todo | Architecture quality gates | Review and judge agents exist, but artefact quality expectations for enterprise and data architecture are not yet enforced systematically. | Add profile-driven checks for assumptions, NFRs, data ownership, lineage, security/privacy, integration pattern fit, risks, decisions, and open questions. Gates are configurable and test-covered. |
| TODO-023 | P2 | todo | Session memory tuning | The default global 2-turn / 3000-char compact memory can be aggressive for extended architecture sessions with retrieved source material, causing effective context collapse on long iterative runs. The current configuration is global plus env overrides, not workload-aware. | Session memory limits are configurable per task type, mode, or workload profile in `registry/session_memory.yaml`. Defaults are reviewed and set to reasonable values for the main architecture use cases. Configuration is documented and test-covered. |
| TODO-027 | P2 | todo | Testing coverage hardening | TESTING.md should describe the current suite, while future test ideas belong in this backlog. A few useful coverage extensions remain for configuration, model display, SharePoint auth, and provider smoke confidence. | Add tests for loading `registry/models.yaml` through the full CLI runtime path, `/list agents` model labels, mocked SharePoint auth status with MSAL, `.env.example` coverage/completeness, and optional provider-selection smoke tests for configured OpenAI, Gemini, Anthropic, and DeepSeek providers. |
| TODO-032 | P2 | todo | Clarify or enforce MCP approval policy | `registry/servers.yaml` and `registry/policies.yaml` describe approval requirements, but effective protection currently comes mainly from server-side path/write restrictions. The configuration should not imply a stronger central approval gate than exists. | Either implement a central approval gate for tools marked under `approval.required_for`, or rename/document approval metadata as advisory/local policy. Tests prove write tools cannot bypass the intended control path. README/DOCUMENTATION explain the actual trust model. |
| TODO-038 | P2 | todo | Agent model API resilience | Each agent is wired to a single `model_ref` with no fallback. A provider API failure causes the entire run to fail with no user guidance on which agent failed or whether retrying is appropriate. VISION Principle 7 (observable cost and quality) requires that failures are visible and understandable. | Registry supports an optional `fallback_model_ref` per agent. If the primary model call fails with a retriable error (rate limit, timeout), the agent retries once with the fallback before surfacing a structured error. Failures are traced with provider, model, stage, and error type. Behaviour is test-covered. |
| TODO-019 | P3 | todo | Web UI rebuild | The web UI should become a first-class execution surface matching CLI semantics. | Web shows routing, per-stage streaming, retrieval checkpoint, workspace browser, and peer transcript with role-labelled cards. Behaviour remains aligned with CLI. |
| TODO-020 | P3 | todo | Multi-workspace support | Users may need clean isolation across projects, clients, or architecture domains. | Add `/workspace switch <path>` and related status/doctor support. Registry and task state isolation are explicit and tested. |

## Recommended Sequencing

1. Implement `TODO-026` before broader team onboarding, because renaming after
   users clone and configure the tool will create avoidable churn.
2. Implement `TODO-037` alongside or immediately after `TODO-026`. A renamed
   product needs a clear setup path or team adoption remains friction-heavy
   regardless of the product name.
3. Implement `TODO-030` and `TODO-031` before adding more protected source
   connectors or enabling remote/custom MCPs for other users.
4. Implement `TODO-042` (rate limiting) alongside `TODO-030` and `TODO-031`.
   Once auth is in place, rate-guarding the execution endpoints prevents token
   exhaustion from misconfigured clients or loops.
5. Implement `TODO-003` after checkpoint and streaming semantics are stable, so
   cached evidence can participate in the same confirmation flow.
6. Implement `TODO-017` (source connector capability contract) before `TODO-004`
    and `TODO-012`. Both new source adapters should be built against the contract
    from the start rather than retrofitted later.
7. Implement `TODO-004` after the capability contract is in place. It creates
    the secure generic pattern for OAuth-protected web sources before site-specific
    adapters proliferate.
8. Implement `TODO-025` with the web UX track, ideally before the full web
    rebuild, because structured editing is a contained high-value feature for
    non-technical architecture users.
    **Note:** design `TODO-025` with the future web architecture
    (`TODO-019`) in mind. If the scope cannot be carried forward with minimal rework
    when the rebuild happens, consider advancing `TODO-019` to a design phase first
    to avoid duplicating effort.
9. Implement `TODO-006`, `TODO-012`, and `TODO-018` as the core data and
    enterprise architecture quality track.
10. Implement `TODO-033`, `TODO-034`, and `TODO-035` before building formal
    assurance automation. The roles directory and assurance operating model
    define who can review, who can approve, which artefacts require sign-off,
    and how asynchronous document movement should be audited.
11. Implement `TODO-013` and `TODO-038` as the model routing and resilience track.
    Dynamic model selection and API fallback should be built together so model
    choices and failure behaviour are governed by the same registry policy.
12. Implement `TODO-040` before any deeper web/Gem UX work. The active surfaces
    should consume the shared event contract instead of carrying removed UI
    implementations.
13. Treat `TODO-019` as the final alignment step for CLI workflow changes that
    affect user-visible execution semantics.

## Done

Completed items should move here with the merge commit or PR reference.

| ID | Item | Reference |
|---|---|---|
| TODO-001 | Human checkpoint after retrieval | `b1959b9 feat(pipeline): add retrieval checkpoint` |
| TODO-002 | Streaming stage output | `461461e feat(ui): stream stage output in clients` |
| TODO-002A | Browser viewport pass for streaming card | `fix(web): bound streaming viewport layout` |
| TODO-043 | CI security scanning | `ci: add security scanning gates` |
| TODO-005 | Token and cost tracking per stage | `feat(runtime): track stage cost telemetry` |
| TODO-041 | API authentication and authorisation guard (Phase 1 — static bearer token) | `2ea5457 feat(security): add Bearer token auth guard`, `800e2d7 fix(security): harden api bearer comparison` |
| TODO-024 | Web document upload | `a2b3f5c docs(todo): mark TODO-041 done and update sequencing` |
| TODO-036 | Routing decision transparency | `feat(ui): expose request contract before execution` |
| TODO-028 | Block agent access to local auth and secret folders | `fix(runtime): block sensitive workspace paths` |
| TODO-029 | Restrictive permissions for token caches | `fix(security): restrict microsoft token cache permissions` |
