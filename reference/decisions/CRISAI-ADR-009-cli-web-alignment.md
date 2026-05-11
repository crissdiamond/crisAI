# CRISAI-ADR-009: Web UX Aligns With CLI Routing And Stage Semantics

Status: accepted  
Date: 2026-05-11

## Context

The CLI became the strongest reference implementation for routing decisions,
verbose controls, stage rendering, session memory, and evidence hiding. The web
interface needs to behave consistently rather than becoming a separate product
surface with different semantics.

## Decision

Align the web interface to CLI semantics:

- show routing decisions and stage progression;
- keep normal stage output human-readable;
- keep raw machine evidence out of normal panels;
- use the same task/session model;
- expose workspace browsing for knowledge, tasks, and staging.

## Consequences

- UI implementation should reuse CLI display sanitisation where practical.
- Web task/session APIs should share the same storage model as CLI sessions.
- The web browser/editor is for text-based review and edits, not a full document
  management system.
- Future UX changes should preserve parity unless there is an explicit decision
  to diverge.

## Related

- `src/crisai/apps/web.py`
- `src/crisai/apps/ui/`
- `src/crisai/cli/display.py`
