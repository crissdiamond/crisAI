# Gem hcom Launch Folder

This is an hcom launch folder, not the Gem source root.

Run Gem-area hcom agents from here so their terminal context is clearly scoped
to Ink terminal client work. The actual source remains in the normal repository
locations.

Primary ownership:

- `../ui/apps/gem/`
- `../ui/packages/contracts/` only when assigned by the orchestrator
- Gem-relevant tests under `../tests/`

Role files in the development-team repo:

- Codex: `../../reference/development/roles/gem_codex.md`
- Claude: `../../reference/development/roles/gem_claude.md`

Before work, read from the target repo:

- `AGENTS.md`
- `reference/TODO.md`

Also read from the development-team repo:

- `reference/development/operating_model.md`
- `reference/development/agent_roster.yaml`
- the local session assignment file printed by the launch script

Use the Claude memory MCP server for task history and hcom for concise
coordination.
