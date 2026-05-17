# Web hcom Launch Folder

This is an hcom launch folder, not the web source root.

Run web-area hcom agents from here so their terminal context is clearly scoped
to React web client work. The actual source remains in the normal repository
locations.

Primary ownership:

- `../ui/apps/web/`
- `../ui/packages/contracts/` only when assigned by the orchestrator
- web-relevant tests under `../tests/`

Role files:

- Codex: `../reference/development/roles/web_codex.md`
- Claude: `../reference/development/roles/web_claude.md`

Before work, read:

- `../AGENTS.md`
- `../reference/development/operating_model.md`
- `../reference/development/agent_roster.yaml`
- `../reference/development/session_assignments.local.yaml` when present

Use the Claude memory MCP server for task history and hcom for concise
coordination.
