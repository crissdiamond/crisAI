# CRISAI-ADR-012: Gemini-Style Persistent CLI Experience

- `Status`: superseded
- `Date`: 2026-05-16

## Context

The interactive CLI had adopted some Gemini-style elements, including a compact
prompt footer, terminal title updates, hierarchical settings, and structured
stage panels. The footer was still tied to `PromptSession.prompt()`, so it
disappeared while the pipeline was running and reappeared only after the agents
finished. That made long retrieval, synthesis, and peer runs feel stuck because
the user could not see the current mode, session, agent, or stage while work was
in progress.

## Decision

The earlier prompt-toolkit/Rich Gemini-style experiment has been superseded by
the shared UI runtime contract and the Ink Gem terminal client. The supported
local interactive path is now:

- `./start api` for the FastAPI runtime
- `./start gem` for the Ink terminal client
- `./start web` for the React web client

The removed classic and Textual paths should not receive new UX behaviour.

The display layer is intentionally a UI boundary, not a workflow controller.
Routing, agents, retrieval, policy checks, and prompt semantics remain owned by
their existing modules.

## Consequences

- Interactive UX work moves to the shared `/api/v1/runs` event contract and the
  React/Ink clients.
- `crisai ask`, `doctor`, and list commands can continue to use the existing
  Rich output path for non-interactive command output.
- Stage output and final output continue to use the same sanitisation rules that
  hide machine-readable JSON contracts from user-facing output.
- Future UI alignment should extend the shared event contract rather than
  scraping terminal output or reviving removed UI surfaces.

## Related

- `src/crisai/cli/display.py`
- `src/crisai/cli/main.py`
- `ui/apps/gem`
- `ui/apps/web`
