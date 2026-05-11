# crisAI TODO

This backlog tracks future product and engineering improvements for crisAI.

Use this file for maintainable work items, not detailed design decisions. When an
item becomes architecture-shaping, add or update an ADR in
`reference/decisions/` and link it from the item.

## How To Maintain

- `Status`: todo, planned, in-progress, blocked, done, or dropped.
- `Priority`: P0 highest, then P1, P2, P3.
- Keep one ownerless backlog here until the team adopts issue tracking.
- Move completed items to `Done` with the commit or PR reference.
- Split any item that cannot be completed and verified in one focused change.

## Backlog

| ID | Priority | Status | Item | Rationale | Definition of Done |
|---|---:|---|---|---|---|
| TODO-001 | P0 | todo | Human checkpoint after retrieval | The most expensive failure mode is continuing into design with the wrong sources or an incomplete evidence set. A checkpoint lets the user confirm, redirect, or stop before downstream agents spend tokens. | CLI pipeline can pause after retrieval, render the evidence brief, accept confirm/redirect/stop, and trace the decision. Web has equivalent behaviour or a tracked follow-up. |
| TODO-002 | P0 | todo | Streaming stage output | Streaming is the largest interactive UX improvement that does not require changing pipeline semantics. Users can see progress and abort earlier. | CLI streams per-stage output without exposing machine evidence JSON. Trace output remains complete. Web streaming is either implemented or tracked separately. |
| TODO-003 | P0 | todo | Persistent retrieval cache | Repeated source reads during iterative tasks waste time and tokens. Evidence bundles can be reused when the query and source revision are unchanged. | Evidence bundles are cached by query fingerprint, source identity, and source revision/hash. Cache hits are visible in trace metadata. Stale entries are invalidated safely. |
| TODO-004 | P1 | todo | Token and cost tracking per stage | Cost needs to be visible for model pairing, pipeline tuning, and user trust. | Trace events include provider/model/token/cost metadata when available. CLI or doctor can summarise spend by run, stage, and agent. Missing provider usage data degrades gracefully. |
| TODO-005 | P1 | todo | Knowledge promotion tooling | Curated knowledge needs a deliberate promotion path from task artefacts into `workspace/knowledge/`. | Add `/promote` workflow or command, provenance fields, staged/approved status, and validation of required YAML front matter. |
| TODO-006 | P1 | todo | Task lifecycle commands | Sessions and task workspaces need first-class lifecycle controls to reduce clutter and accidental context reuse. | Add `/tasks list`, `/tasks close <id>`, and `/tasks archive <id>` with tests and docs. Commands operate on `workspace/tasks/` without deleting user artefacts unexpectedly. |
| TODO-007 | P1 | todo | Mermaid image embedding in exports | DOCX/PPTX exports should contain rendered diagrams, not raw Mermaid blocks, for business-ready documents. | Export server renders Mermaid to SVG or PNG and embeds images in DOCX/PPTX. Source Markdown/Mermaid remains the canonical source. |
| TODO-008 | P1 | todo | Unified synonym and graph expansion | Search expansion should be consistent across intranet search, workspace search, routing, and prompt scaffolding. | `search_synonyms.yaml` is merged into or cross-referenced from the semantic graph. Expansion behaviour has regression tests and a single documented source of truth. |
| TODO-009 | P1 | todo | Second intranet adapter: Confluence | The intranet provider interface is ready; Confluence support would validate provider neutrality and broaden adoption. | Add a Confluence provider implementing search, fetch, link listing, auth/status where applicable, config docs, and tests with mocked API responses. |
| TODO-010 | P2 | todo | Dynamic model selection | Routing and task criticality should influence model tier instead of using only static agent assignments. | Model policy remains in registry/config. Router/task contract can select a model tier for supported agents. Decisions are traced and test-covered. |
| TODO-011 | P2 | todo | Persistent workspace semantic index | Retrieval over `workspace/knowledge/` should not rebuild expensive indexes on every run. | Add an incremental index updated on writes or explicit rebuild. Retrieval uses the index when fresh and falls back safely when stale/missing. |
| TODO-012 | P2 | todo | Cross-task memory summary | Useful decisions and artefacts can span tasks, but full history replay is too expensive. | Maintain a compact workspace-level summary of decisions, artefacts, and open questions. Include it only when relevant and trace when used. |
| TODO-013 | P2 | todo | Routing feedback capture | User mode overrides are valuable correction signals for improving routing behaviour. | Record explicit overrides as structured events. Provide an analytics view or export that can inform catalog/graph tuning without silently changing behaviour. |
| TODO-014 | P3 | todo | Web UI rebuild | The web UI should become a first-class execution surface matching CLI semantics. | Web shows routing, per-stage streaming, workspace browser, and peer transcript with role-labelled cards. Behaviour remains aligned with CLI. |
| TODO-015 | P3 | todo | Multi-workspace support | Users may need clean isolation across projects or clients. | Add `/workspace switch <path>` and related status/doctor support. Registry and task state isolation are explicit and tested. |

## Recommended Sequencing

1. Implement `TODO-001` first because it prevents the highest-cost wrong-source
   pipeline runs.
2. Implement `TODO-002` next because it improves perceived performance and gives
   users earlier visibility into long-running stages.
3. Implement `TODO-003` after checkpoint semantics are stable, so cached evidence
   can participate in the same confirmation flow.
4. Implement `TODO-004` before major model-routing changes, so model choices can
   be assessed with actual cost and usage data.
5. Treat `TODO-014` as the final alignment step for any CLI workflow changes
   that affect user-visible execution semantics.

## Done

Completed items should move here with the merge commit or PR reference.
