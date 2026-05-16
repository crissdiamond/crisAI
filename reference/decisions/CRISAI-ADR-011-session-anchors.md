# CRISAI-ADR-011: Preserve User-Visible Session Anchors

## Status

Accepted

## Context

Multi-step architecture tasks often create intermediate labels that users rely
on later: option numbers, section numbers, risk ids, decisions, and
recommendation labels. If a later turn says "create HLDs for option 2 and 3",
the system must preserve the labels already shown to the user. Reinterpreting
those references from prompt semantics can generate the wrong artefact while
still sounding plausible.

## Decision

crisAI stores deterministic session anchors in
`workspace/tasks/<task>/.crisai/anchors.json`.

Anchors are extracted from prior assistant Markdown tables and headings using
generic vocabulary from `registry/semantic_catalog.yaml`. Later requests are
resolved against this registry before agent execution. Resolved references are
included in runtime context and `request_contract_v1.referenced_anchors`.

Publisher remains a packaging specialist. It is instructed to preserve resolved
labels and titles, but the actual reference resolution and publication
conformance are deterministic runtime responsibilities.

## Consequences

- Follow-up turns can refer to prior visible labels without relying on full
  transcript replay.
- Prompt files do not need use-case-specific patches for option numbering.
- Generated task artefacts can be validated against resolved anchors before
  they are registered as successful outputs.
- Anchor vocabulary remains registry-owned and can be extended without changing
  Python semantics.

## References

- `registry/semantic_catalog.yaml`
- `src/crisai/orchestration/session_anchors.py`
- `src/crisai/orchestration/request_contract.py`
- `src/crisai/cli/chat_context.py`
- `src/crisai/cli/artefact_lifecycle.py`
