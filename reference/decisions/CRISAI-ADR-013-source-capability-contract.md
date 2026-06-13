# CRISAI-ADR-013: Source Connector Capability Contract

Status: accepted  
Date: 2026-06-13

## Context

crisAI reaches enterprise content through MCP source adapters (workspace,
documents, SharePoint/OneDrive, intranet, and future authenticated-web and data
catalogue adapters). Today, knowledge about what each source can do — which tool
searches, which lists, which fetches content, which family of sources it serves,
how strong the evidence it can return is, how a result is re-addressed across the
retrieval→read handover, and how a contributor authenticates — is **not in the
registry**. It is hardcoded in `src/crisai/orchestration/prompt_generation.py`
(scope markers and "use intranet tools / prefer SharePoint search" rules) and in
prompt markdown (`prompts/context_retrieval_agent.md`). Only source *scope*
(intranet / sharepoint / personal_onedrive / workspace) is registry-driven, via
`registry/semantic_catalog.yaml` `source_scope_markers`.

This conflicts with the registry-driven-semantics principle (CRISAI-ADR-002): a
new adapter or a change in source guidance should be a registry edit, not a
Python/prompt change. It also blocks clean addition of new adapters (TODO-004
authenticated web, TODO-012 data catalogue), which would otherwise each need new
hardcoded routing.

## Decision

Introduce a declarative **source capability contract** as a `capabilities:`
block on each retrieval-source server in `registry/servers.yaml`, plus a `kind:`
field distinguishing retrieval `source` servers from `tool` (utility) servers
(diagrams, vision, document export, session memory).

The v1 contract is the high-value, enforced subset:

```yaml
kind: source            # or: tool
capabilities:
  source_families: [intranet]          # which scopes this server serves; aligns with
                                        # semantic_catalog source_scope_markers keys
  source_types: [page]                 # file | document | slide | page | record
  operations:                           # operation -> tools that perform it (subset of tools.allow)
    search: [...]
    list:   [...]
    fetch:  [...]                        # read content
    read_binary: [...]                   # tools returning office/pdf/binary content
  evidence_levels: [search_hit_only, metadata_read, content_read]   # the ceiling this source reaches
  reference: { handle: content_id, stability: stable }   # how a result is re-addressed; stable | session
  auth: { interactive_login_tool: intranet_login, status_tool: intranet_auth_status }
  pagination: none                       # none | offset | cursor   — declared, advisory in v1
  freshness: graph_last_modified         # none | mtime | etag | graph_last_modified — advisory in v1
```

Enforced enums (validated by doctor):

- `source_families` ⊆ the source scopes the router already knows
  (`personal_onedrive`, `sharepoint`, `intranet`, `workspace`).
- `source_types` ⊆ `{file, document, slide, page, record}`.
- `operations` keys ⊆ `{search, list, fetch, read_binary}`; every listed tool is
  in that server's `tools.allow`.
- `evidence_levels` ⊆ the evidence-contract levels
  (`search_hit_only`, `metadata_read`, `content_read`).
- `reference.handle` ⊆ `{workspace_path, read_handle, content_id, open_url}`;
  `reference.stability` ∈ `{stable, session}`.
- `auth` login/status tools, when declared, are in `tools.allow`.

`pagination` and `freshness` are declared but advisory in v1; they exist so the
contract is forward-compatible with the retrieval cache (TODO-003) and paginating
adapters (TODO-004) without another schema change.

This ADR covers **Phase 0–1**: the contract, its loader, and doctor validation
(additive, no behaviour change). A later phase migrates the hardcoded retrieval
source guidance in `prompt_generation.py` to be generated from this contract, and
lets the router map an inferred source scope to the serving server(s) — at which
point the duplicated, hardcoded guidance is removed.

## Consequences

- Source capability becomes a registry edit, not a Python/prompt change, honoring
  CRISAI-ADR-002.
- New adapters (TODO-004, TODO-012) declare a `capabilities` block and are
  discoverable without retrofitting routing logic.
- Doctor surfaces source servers with missing or inconsistent capability metadata
  (operation tools not exposed, invalid evidence levels, unknown families).
- The `source_families` values intentionally reuse the `semantic_catalog`
  scope-marker keys; keeping the two in step is a follow-up doctor check.
- Until the Phase-2 migration lands, prompt guidance remains hardcoded; the
  contract is declared and validated but not yet the source of that guidance.
