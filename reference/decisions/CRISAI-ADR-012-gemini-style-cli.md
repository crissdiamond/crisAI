# CRISAI-ADR-012: Gemini-Style Persistent CLI Experience

- `Status`: accepted
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

`crisai chat` uses a Gemini-style display layer that captures routing, status,
stage, checkpoint, final, and error output into a live transcript with a
persistent footer during interactive execution. The existing Rich/classic
rendering remains available for non-interactive commands and as a fallback via
`CRISAI_CLI_EXPERIENCE=classic`.

The display layer is intentionally a UI boundary, not a workflow controller.
Routing, agents, retrieval, policy checks, and prompt semantics remain owned by
their existing modules.

## Consequences

- Interactive chat has a visible status/footer during long agent runs.
- `crisai ask`, `doctor`, list commands, and classic chat keep the existing Rich
  output path.
- Stage output and final output continue to use the same sanitisation rules that
  hide machine-readable JSON contracts from user-facing output.
- Future web alignment should consume the same event/sink pattern rather than
  scraping terminal output.

## Related

- `src/crisai/cli/display.py`
- `src/crisai/cli/gemini_chat.py`
- `src/crisai/cli/main.py`
- `CRISAI_CLI_EXPERIENCE`
