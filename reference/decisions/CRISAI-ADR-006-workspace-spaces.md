# CRISAI-ADR-006: Separate Curated Knowledge From Task Artefact Workspaces

Status: accepted  
Date: 2026-05-11

## Context

The previous `workspace/context` and `workspace/context_staging` model mixed
team-owned reference knowledge with generated task outputs. The desired model is
two first-class spaces: one maintained by the team for retrieval, and one where
agents create artefacts for a task.

## Decision

Use:

- `workspace/knowledge/` for curated, approved, team-owned machine-readable
  knowledge.
- `workspace/knowledge_staging/` for promotion candidates that need review or
  transformation.
- `workspace/tasks/<task>/` for one task/session's artefacts, inputs, scratch,
  exports, and `.crisai` metadata.

Workspace root semantics live in `registry/workspace_spaces.yaml`.

## Consequences

- Agents may write task artefacts directly.
- Agents may write knowledge promotion candidates to staging.
- Agents should not write directly into approved knowledge unless an explicit
  promotion workflow is requested and validation passes.
- Legacy `context` and `context_staging` read aliases remain for compatibility.

## Related

- `registry/workspace_spaces.yaml`
- `workspace/knowledge/README.md`
- `workspace/knowledge_staging/README.md`
- `workspace/tasks/README.md`
