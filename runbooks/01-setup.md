# crisAI Setup

1. Install uv if needed: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
2. Install the package for the default multi-provider registry: `uv sync --extra litellm`.
3. For development and tests, install the dev group: `uv sync --extra litellm --group dev`.
4. Install UI dependencies for Ink Gem and React web: `npm --prefix ui install`.
5. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `DEEPSEEK_API_KEY`.
6. For a mono-provider setup, copy one of `registry/examples/agents.*.yaml` over `registry/agents.yaml`, then set only that provider's key.
7. Optional Microsoft Graph: set `MS_TENANT_ID` and `MS_CLIENT_ID`, then run SharePoint or intranet auth status/login tools from crisAI.
8. Validate local configuration: `uv run crisai doctor`.
9. Validate artefact profiles: `uv run crisai validate-artefacts`.
10. Start the FastAPI backend: `./start api`.
11. Start the Ink terminal client in another terminal: `./start gem`.
12. Or start the React web UI: `./start web`, then open `http://127.0.0.1:5173`.

Use `uv run pytest` for the network-free regression suite after installing the
dev group. The manual Graph login smoke test remains `uv run python
tests/orchestration/test_graph_login.py`.

For hcom-based multi-agent development, run `scripts/hcom_start.sh --dry-run`
first, then `scripts/hcom_start.sh` when ready. See
`reference/development/operating_model.md`.

The hcom development team uses a dedicated `tmux` session by default. Attach to
the running team with:

```bash
tmux attach -t crisai-hcom
```

Inside tmux, use `Ctrl-b` then a window number to switch agents:
`0` orchestrator, `1` Gem Codex, `2` Gem Claude, `3` web Codex, `4` web Claude,
`5` runtime Codex, and `6` runtime Claude. Use `Ctrl-b` then `d` to detach
without stopping the team.
