# Gem hcom Context Folder

This is an hcom context folder, not the Gem source root.

The launcher starts Gem agents from the repository root so Codex workspace-write
covers the files they own. Use this folder only for Gem context. The actual
source remains in the normal repository locations.

Primary ownership:

- `ui/apps/gem/`
- `ui/packages/contracts/` only when assigned by the orchestrator
- Gem-relevant tests under `tests/`

Role files:

- Codex: `reference/development/roles/gem_codex.md`
- Claude: `reference/development/roles/gem_claude.md`

Before work, read:

- `AGENTS.md`
- `reference/development/operating_model.md`
- `reference/development/agent_roster.yaml`
- `reference/development/session_assignments.local.yaml` when present

Use the Claude memory MCP server for task history and hcom for concise
coordination.
