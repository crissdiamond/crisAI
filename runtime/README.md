# Runtime hcom Launch Folder

This is an hcom launch folder, not the runtime source root.

Run runtime-area hcom agents from here so their terminal context is clearly
scoped to runtime work. The actual source remains in the normal repository
locations.

Primary ownership:

- `src/crisai/`
- `registry/`
- `prompts/`
- runtime-relevant tests under `tests/`

Role files:

- Codex: `../reference/development/roles/runtime_codex.md`
- Claude: `../reference/development/roles/runtime_claude.md`

Before work, read:

- `../AGENTS.md`
- `../reference/development/operating_model.md`
- `../reference/development/agent_roster.yaml`
- `../reference/development/session_assignments.local.yaml` when present

Use the Claude memory MCP server for task history and hcom for concise
coordination.
