# crisAI Setup

## First clone

1. Install uv if needed: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
2. Install Node.js/npm if you want to use Ink Gem or React web.
3. Clone the repository and enter it.
4. Run `scripts/bootstrap.sh`.
5. Edit `.env` and set the provider keys required by your selected agent registry.
6. Validate local configuration: `uv run crisai doctor`.
7. Validate artefact profiles: `uv run crisai validate-artefacts`.
8. Start the FastAPI backend: `./start api`.
9. Start the Ink terminal client in another terminal: `./start gem`.
10. Or start the React web UI: `./start web`, then open `http://127.0.0.1:5173`.

uv is the supported setup path. It creates and manages the project `.venv`; do
not create or activate a virtual environment manually. `scripts/bootstrap.sh`
runs the uv install, installs UI workspace dependencies when npm is available,
copies `.env.example` to `.env` when missing, and creates the standard workspace
and log folders.

## Troubleshooting setup manually

Use these commands only when you need to inspect or repair what bootstrap would
normally do:

```bash
uv sync --extra litellm
npm --prefix ui install
cp .env.example .env
```

For development and tests, install the dev group:

```bash
uv sync --extra litellm --group dev
```

For a mono-provider setup, copy one of `registry/examples/agents.*.yaml` over
`registry/agents.yaml`, then set only that provider's key. Optional Microsoft
Graph retrieval also needs `MS_TENANT_ID` and `MS_CLIENT_ID`, followed by the
SharePoint or intranet auth status/login tools from crisAI.

If `uv run crisai doctor` reports that `.env` is missing placeholders present in
`.env.example`, add those placeholder keys without overwriting real local
secrets.

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
