# CRISAI-ADR-004: Task Contracts Preserve The User's Main Ask

Status: accepted  
Date: 2026-05-11

## Context

Pipeline traces showed agents spending tokens debating source candidates when
the user had asked for a summary or deliverable. Retrieval was sometimes treated
as the task, rather than support for the task.

## Decision

Use task contracts to preserve the user's primary ask across routing,
retrieval, synthesis, summary, design, review, and final orchestration.

Summary requests should route to summary-specific behaviour after retrieval,
including a fast path when validated evidence is already available.

## Consequences

- Retrieval is a support step, not the final answer.
- The pipeline must distinguish summary, design, and source-finding asks.
- Downstream stages should receive the contract and preserve the requested
  deliverable.
- Summary requests should avoid unnecessary design/review debate unless the
  contract requires it.

## Related

- `src/crisai/orchestration/task_contract.py`
- `src/crisai/cli/pipelines.py`
- `registry/semantic_graph.yaml`
