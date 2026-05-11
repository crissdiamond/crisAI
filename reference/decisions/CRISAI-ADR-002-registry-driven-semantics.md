# CRISAI-ADR-002: Runtime Semantics Live In Registry And Config

Status: accepted  
Date: 2026-05-11

## Context

Earlier pipeline work showed that putting semantic rules directly in Python made
behaviour harder to inspect, tune, and govern. Examples include intent terms,
retrieval expansion, workspace roots, and workflow policy markers.

## Decision

Keep reusable runtime semantics in declarative registry/config files wherever
practical. Python should load and enforce those contracts, not become the main
place where business or architecture vocabulary is encoded.

## Consequences

- Semantic graph, semantic catalog, workflow policy, workspace spaces, agent
  assignments, and model assignments should remain externally configurable.
- Python changes are still appropriate for parsing, validation, orchestration,
  and safety gates.
- When a new semantic category is needed, check the registry first before adding
  code-level keyword lists.

## Related

- `registry/semantic_graph.yaml`
- `registry/semantic_catalog.yaml`
- `registry/workflow_policy.yaml`
- `registry/workspace_spaces.yaml`
- `src/crisai/workspace/spaces.py`
