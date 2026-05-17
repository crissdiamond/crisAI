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

Role files in the development-team repo:

- Codex: `../../reference/development/roles/runtime_codex.md`
- Claude: `../../reference/development/roles/runtime_claude.md`

Before work, read from the target repo:

- `AGENTS.md`
- `reference/TODO.md`

Also read from the development-team repo:

- `reference/development/operating_model.md`
- `reference/development/agent_roster.yaml`
- the local session assignment file printed by the launch script

Use the Claude memory MCP server for task history and hcom for concise
coordination.
