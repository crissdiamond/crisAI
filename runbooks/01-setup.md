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

## Team member onboarding checklist

Use this path for a new teammate joining an existing crisAI checkout or team
branch:

1. Confirm prerequisites:
   - `uv --version`
   - `python --version`
   - `node --version` and `npm --version` if they will use Gem or web
2. Run `scripts/bootstrap.sh` from the repository root.
3. Open `.env` and choose one model-provider setup:
   - Default registry: set `OPENAI_API_KEY`, `GEMINI_API_KEY`, and
     `DEEPSEEK_API_KEY`.
   - One provider: copy one of `registry/examples/agents.*.yaml` over
     `registry/agents.yaml`, then set that provider key.
4. For local API clients, leave `CRISAI_API_KEY` empty only when the API stays
   bound to `127.0.0.1`. Set a long random value before team or network use.
5. Run `uv run crisai doctor`. Resolve errors first, then warnings that apply to
   your setup. Missing Microsoft token-cache permission warnings only matter if
   you use Microsoft Graph retrieval.
6. After changing model refs or providers, run `uv run crisai doctor --models`.
   This dry-builds configured agents without calling provider APIs.
7. Run the cheapest functional check for your intended surface:
   - Runtime only: `uv run crisai list-agents`
   - API: `./start api`
   - Gem: start the API, then `./start gem`
   - Web: start the API, then `./start web`
8. Optional provider smoke tests are disabled by default because they can spend
   tokens. Enable them only when provider keys are exported in the current
   shell and a live-provider check is intentional. If your keys are only in
   `.env`, source them for that shell first with `set -a; . ./.env; set +a`.
   Tests for providers without a key skip automatically:

   ```bash
   CRISAI_RUN_SMOKE_TESTS=1 uv run pytest tests/smoke -q
   ```

9. Try a short example run after `doctor` is clean enough for your setup:

   ```bash
   uv run crisai ask --message "Summarise what crisAI is for in three bullets."
   ```

If `doctor` reports that `.env` is missing keys from `.env.example`, copy only
the missing key names into `.env`. Do not overwrite existing local secrets.

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
first, then `./start hcom` when ready. `./start hcom` resumes saved hcom
sessions when local assignments exist, otherwise it starts a fresh team. See
`reference/development/operating_model.md`.

The hcom development team uses a dedicated `tmux` session by default. Attach to
the running team with:

```bash
scripts/hcom_attach.sh
```

Or attach directly with:

```bash
./start hcom-attach
```

or:

```bash
tmux attach -t crisai-hcom
```

Inside tmux, use `Ctrl-\` then a window number to switch agents:
`0` orchestrator, `1` Gem Codex, `2` Gem Claude, `3` web Codex, `4` web Claude,
`5` runtime Codex, and `6` runtime Claude. Use `Ctrl-\` then `n` or `p` for
next/previous, `Ctrl-\` then `w` for the window list, and `Ctrl-\` then `d` to
detach without stopping the team. `Ctrl-b` remains a secondary prefix if needed.
The tmux status bar uses cyan labels for Codex windows, purple labels for
Claude windows, and green for the orchestrator/other windows.
