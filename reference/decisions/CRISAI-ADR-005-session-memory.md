# CRISAI-ADR-005: Sessions Use Compact Task Memory

Status: accepted  
Date: 2026-05-11

## Context

Long-running tasks need history, but replaying full transcripts wastes tokens
and can cause agents to repeat old reasoning. Users may also accidentally mix
tasks in one session, increasing cost and reducing answer quality.

## Decision

Use one session per task. Persist raw history, but build runtime prompts from
compact task memory plus a small relevant recent tail. Warn when the current
message appears to drift into a new task.

## Consequences

- Runtime prompts are bounded and cheaper.
- Session memory records task goal, current state, important decisions, known
  sources, open questions, recent outputs, and do-not-repeat guidance.
- Users should create a new session/task for materially different work.
- Agentic memory can be added later behind the same persisted contract.

## Related

- `registry/session_memory.yaml`
- `src/crisai/cli/chat_context.py`
- `src/crisai/cli/session_store.py`
