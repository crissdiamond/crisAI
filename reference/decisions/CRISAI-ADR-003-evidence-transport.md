# CRISAI-ADR-003: Evidence Transport Is Separate From Agent Prose

Status: accepted  
Date: 2026-05-11

## Context

Retrieval agents were exposing raw JSON in CLI output and sometimes downstream
agents treated prose summaries as equivalent to validated source evidence. This
created noisy UX and weak grounding.

## Decision

Machine evidence travels as structured transport. User-facing stage output and
final answers remain human-readable prose. Raw evidence is retained in trace
metadata and validated before downstream use.

## Consequences

- Retrieval stages can emit `evidence_bundle_v1`, but normal CLI/web rendering
  strips machine JSON from panels.
- Summary and design stages receive validated evidence summaries instead of
  copied raw JSON.
- Content-read requests require `content_read` evidence and fail fast when a
  valid bundle is missing.
- Debugging uses `logs/agent_trace.jsonl` metadata rather than exposing machine
  contracts in normal UX.

## Related

- `schemas/evidence_bundle_v1.schema.json`
- `src/crisai/orchestration/evidence_contract.py`
- `src/crisai/cli/pipelines.py`
- `src/crisai/cli/display.py`
