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

- pipeline runs still proceed without a user checkpoint after retrieval;
- long stages do not stream output, so users cannot judge progress early;
- retrieval does not persist validated evidence across iterative runs;
- source coverage is still Microsoft-heavy and does not cover generic OAuth web
  apps, Confluence, or enterprise data catalogues;
- architecture artefact production is not yet guided by a full template library
  for HLD, options papers, data architecture, lineage, and NFRs;
- knowledge promotion is documented as a space but not yet a governed workflow;
- token/cost telemetry is not surfaced per stage, agent, and model;
- web UX follows CLI concepts but does not yet provide full streaming,
  checkpoint, and peer transcript parity.

## Backlog

| ID | Priority | Status | Item | Rationale | Definition of Done |
|---|---:|---|---|---|---|
| TODO-001 | P0 | todo | Human checkpoint after retrieval | The most expensive failure mode is continuing into design with the wrong sources or an incomplete evidence set. A checkpoint lets the user confirm, redirect, or stop before downstream agents spend tokens. | CLI pipeline can pause after retrieval, render the evidence brief, accept confirm/redirect/stop, and trace the decision. Web has equivalent behaviour or a tracked follow-up. |
| TODO-002 | P0 | todo | Streaming stage output | Streaming is the largest interactive UX improvement that does not require changing pipeline semantics. Users can see progress and abort earlier. | CLI streams per-stage output without exposing machine evidence JSON. Trace output remains complete. Web streaming is either implemented or tracked separately. |
| TODO-003 | P0 | todo | Persistent retrieval cache | Repeated source reads during iterative tasks waste time and tokens. Evidence bundles can be reused when the query and source revision are unchanged. | Evidence bundles are cached by query fingerprint, source identity, and source revision/hash. Cache hits are visible in trace metadata. Stale entries are invalidated safely. |
| TODO-004 | P1 | todo | Authenticated website retrieval MCP | Enterprise architecture work often depends on protected vendor portals, internal web apps, design standards sites, and architecture repositories that are not SharePoint pages. crisAI needs a read-only OAuth/OIDC website source connector with strict scope controls. | Add an `authenticated_web` MCP server with login/auth-status, allow-listed hosts, OAuth/OIDC auth-code or device flow, URL fetch, optional rendered-page fetch for JS-heavy pages, link extraction, content normalization, source references, and tests with mocked OAuth and HTTP responses. |
| TODO-005 | P1 | todo | Token and cost tracking per stage | Cost needs to be visible for model pairing, pipeline tuning, and user trust. This should precede dynamic model selection so model decisions are based on measured usage. | Trace events include provider/model/token/cost metadata when available. CLI or doctor can summarise spend by run, stage, and agent. Missing provider usage data degrades gracefully. |
| TODO-006 | P1 | todo | Architecture artefact template library | The tool is intended to support daily enterprise, solution, and data architecture work. It needs reusable structures beyond one-off generated Markdown. | Add governed templates for HLD, options paper, architecture decision record, data flow, data mapping, data lineage, NFR assessment, integration design, migration plan, and architecture review. Router/semantic graph can select them. Artefact validation has tests. |
| TODO-007 | P1 | todo | Knowledge promotion tooling | Curated knowledge needs a deliberate promotion path from task artefacts into `workspace/knowledge/`. | Add `/promote` workflow or command, provenance fields, staged/approved status, and validation of required YAML front matter. |
| TODO-008 | P1 | todo | Task lifecycle commands | Sessions and task workspaces need first-class lifecycle controls to reduce clutter and accidental context reuse. | Add `/tasks list`, `/tasks close <id>`, and `/tasks archive <id>` with tests and docs. Commands operate on `workspace/tasks/` without deleting user artefacts unexpectedly. |
| TODO-009 | P1 | todo | Unified synonym and graph expansion | Search expansion should be consistent across intranet search, workspace search, routing, and prompt scaffolding. | `search_synonyms.yaml` is merged into or cross-referenced from the semantic graph. Expansion behaviour has regression tests and a single documented source of truth. |
| TODO-010 | P1 | todo | Mermaid image embedding in exports | DOCX/PPTX exports should contain rendered diagrams, not raw Mermaid blocks, for business-ready architecture documents. | Export server renders Mermaid to SVG or PNG and embeds images in DOCX/PPTX. Source Markdown/Mermaid remains the canonical source. |
| TODO-011 | P1 | todo | Second intranet adapter: Confluence | The intranet provider interface is ready; Confluence support would validate provider neutrality and broaden adoption in enterprise architecture teams. | Add a Confluence provider implementing search, fetch, link listing, auth/status where applicable, config docs, and tests with mocked API responses. |
| TODO-012 | P1 | todo | Enterprise data catalogue MCP | Data architecture work needs direct access to glossary terms, data products, schemas, lineage, owners, classifications, and quality metadata. SharePoint documents are not enough. | Add a provider-shaped MCP for at least one catalogue family, preferably Microsoft Purview first, with search/fetch tools, lineage/owner metadata, registry config, evidence source references, and mocked tests. Keep Collibra/Atlan as future adapters. |
| TODO-013 | P2 | todo | Dynamic model selection | Routing and task criticality should influence model tier instead of using only static agent assignments. | Model policy remains in registry/config. Router/task contract can select a model tier for supported agents. Decisions are traced and test-covered. |
| TODO-014 | P2 | todo | Incremental workspace semantic index | `document_server` has a local context index, but it is rebuilt manually/on demand and is not a persistent, incremental workspace knowledge service. | Add an incremental index updated on writes or explicit rebuild. Retrieval uses the index when fresh and falls back safely when stale/missing. Include freshness metadata and tests. |
| TODO-015 | P2 | todo | Cross-task memory summary | Useful decisions and artefacts can span tasks, but full history replay is too expensive. | Maintain a compact workspace-level summary of decisions, artefacts, and open questions. Include it only when relevant and trace when used. |
| TODO-016 | P2 | todo | Routing feedback capture | User mode overrides are valuable correction signals for improving routing behaviour. | Record explicit overrides as structured events. Provide an analytics view or export that can inform catalog/graph tuning without silently changing behaviour. |
| TODO-017 | P2 | todo | Source connector capability contract | More MCP sources are coming. Agents and router need to know source capabilities without prompt patches or hardcoded assumptions. | Add registry metadata for source capabilities such as search, fetch, list, auth, source type, evidence level, binary support, pagination, and freshness. Retrieval prompts and tests consume this metadata. |
| TODO-018 | P2 | todo | Architecture quality gates | Review and judge agents exist, but artefact quality expectations for enterprise and data architecture are not yet enforced systematically. | Add profile-driven checks for assumptions, NFRs, data ownership, lineage, security/privacy, integration pattern fit, risks, decisions, and open questions. Gates are configurable and test-covered. |
| TODO-019 | P3 | todo | Web UI rebuild | The web UI should become a first-class execution surface matching CLI semantics. | Web shows routing, per-stage streaming, retrieval checkpoint, workspace browser, and peer transcript with role-labelled cards. Behaviour remains aligned with CLI. |
| TODO-020 | P3 | todo | Multi-workspace support | Users may need clean isolation across projects, clients, or architecture domains. | Add `/workspace switch <path>` and related status/doctor support. Registry and task state isolation are explicit and tested. |

## Recommended Sequencing

1. Implement `TODO-001` first because it prevents the highest-cost wrong-source
   pipeline runs.
2. Implement `TODO-002` next because it improves perceived performance and gives
   users earlier visibility into long-running stages.
3. Implement `TODO-003` after checkpoint semantics are stable, so cached evidence
   can participate in the same confirmation flow.
4. Implement `TODO-004` before adding many site-specific web adapters. It creates
   the secure generic pattern for OAuth-protected web sources.
5. Implement `TODO-005` before major model-routing changes, so model choices can
   be assessed with actual cost and usage data.
6. Implement `TODO-006`, `TODO-012`, and `TODO-018` as the core data and
   enterprise architecture quality track.
7. Treat `TODO-019` as the final alignment step for CLI workflow changes that
   affect user-visible execution semantics.

## Done

Completed items should move here with the merge commit or PR reference.
