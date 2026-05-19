# Gem hcom Context Folder

This is an hcom context folder, not the Gem source root.

The launcher starts Gem agents from the target repository root so Codex
workspace-write covers the files they own. Use this folder only for Gem context.
The actual source remains in the normal repository locations.

Primary ownership:

- target repo `ui/apps/gem/`
- target repo `ui/packages/contracts/` only when assigned by the orchestrator
- Gem-relevant tests under target repo `tests/`

Role files in the development-team repo:

- Codex: `../../reference/development/roles/gem_codex.md`
- Claude reviewer, launched on demand:
  `../../reference/development/roles/gem_claude.md`

Before work, read from the target repo:

- `AGENTS.md`
- `reference/TODO.md`

Also read from the development-team repo:

- `reference/development/operating_model.md`
- `reference/development/agent_roster.yaml`
- the local session assignment file printed by the launch script

Use the Claude memory MCP server for task history and hcom for concise
coordination.
