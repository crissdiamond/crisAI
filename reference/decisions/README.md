# crisAI Design Decisions

This folder records product and engineering decisions about crisAI itself.

Use it for durable decisions that future development should respect: architecture,
runtime behaviour, agent boundaries, workspace structure, retrieval contracts,
configuration policy, and user experience conventions.

Do not use this folder for customer/domain architecture knowledge. That belongs
in `workspace/knowledge/`. Do not use it for generated task artefacts. Those
belong in `workspace/tasks/<task>/artefacts/`.

## Decision Format

Each decision file should be short and use this shape:

- `Status`: proposed, accepted, superseded, or retired.
- `Date`: decision date.
- `Context`: why the decision was needed.
- `Decision`: what we chose.
- `Consequences`: trade-offs and implementation implications.
- `Related`: links to code, docs, or other decisions.

## Current Decisions

| ID | Title | Status |
|---|---|---|
| [CRISAI-ADR-001](CRISAI-ADR-001-agent-workstation.md) | crisAI is a workstation of narrowly scoped agents | accepted |
| [CRISAI-ADR-002](CRISAI-ADR-002-registry-driven-semantics.md) | Runtime semantics live in registry/config, not scattered Python | accepted |
| [CRISAI-ADR-003](CRISAI-ADR-003-evidence-transport.md) | Evidence transport is separate from agent prose | accepted |
| [CRISAI-ADR-004](CRISAI-ADR-004-task-contracts.md) | Task contracts preserve the user’s main ask across stages | accepted |
| [CRISAI-ADR-005](CRISAI-ADR-005-session-memory.md) | Sessions use compact task memory instead of full transcript replay | accepted |
| [CRISAI-ADR-006](CRISAI-ADR-006-workspace-spaces.md) | Separate curated knowledge from task artefact workspaces | accepted |
| [CRISAI-ADR-007](CRISAI-ADR-007-markdown-source-artefacts.md) | Markdown/Mermaid is the source of truth for generated artefacts | accepted |
| [CRISAI-ADR-008](CRISAI-ADR-008-provider-neutral-intranet.md) | Intranet retrieval is provider-neutral | accepted |
| [CRISAI-ADR-009](CRISAI-ADR-009-cli-web-alignment.md) | Web UX should align with CLI routing and stage semantics | accepted |
| [CRISAI-ADR-010](CRISAI-ADR-010-document-formatting-agent.md) | Add a narrow document formatting agent | accepted |
| [CRISAI-ADR-011](CRISAI-ADR-011-session-anchors.md) | Preserve user-visible session anchors across follow-up turns | accepted |
