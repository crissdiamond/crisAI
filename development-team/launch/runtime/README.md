# Runtime hcom Context Folder

This is an hcom context folder, not the runtime source root.

The launcher starts runtime agents from the target repository root so Codex
workspace-write covers the files they own. Use this folder only for runtime
context. The actual source remains in the normal repository locations.

Primary ownership:

- target repo `src/crisai/`
- target repo `registry/`
- target repo `prompts/`
- runtime-relevant tests under target repo `tests/`

Role files in the development-team repo:

- Codex: `../../reference/development/roles/runtime_codex.md`
- Claude reviewer, launched on demand:
  `../../reference/development/roles/runtime_claude.md`

Before work, read from the target repo:

- `AGENTS.md`
- `reference/TODO.md`

Also read from the development-team repo:

- `reference/development/operating_model.md`
- `reference/development/agent_roster.yaml`
- the local session assignment file printed by the launch script

Use the Claude memory MCP server for task history and hcom for concise
coordination.
