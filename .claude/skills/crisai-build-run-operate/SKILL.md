---
name: crisai-build-run-operate
description: Setup and operations runbook for crisAI. Load when recreating the environment from scratch (fresh clone, uv sync, .env, API keys, bootstrap), when `crisai doctor` fails, when starting or stopping services (./start api/web/gem/knowledge/hcom, ./stop, ports 8000/5173), when a fresh clone is missing CLAUDE.md or workspace/knowledge, or when asking where files land (workspace/tasks layout, sources cache, outputs, logs).
---

# crisAI: build, run, operate

Runbook for getting a working crisAI environment from a bare clone and operating
it day to day. Everything below is verified against the repo as of 2026-07-02.

## Fresh clone to first run (the golden path)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv is missing
git clone https://github.com/crissdiamond/crisAI
cd crisAI
scripts/bootstrap.sh          # uv sync --extra litellm; npm --prefix ui install (if npm);
                              # .env from .env.example (if missing); mkdir workspace dirs
# edit .env — set provider keys (see "API keys" below)
uv run crisai doctor          # THE gate: fix errors before anything else
uv run crisai validate-artefacts
./start api                   # FastAPI backend on http://127.0.0.1:8000
./start gem                   # Ink terminal client (separate terminal), or:
./start web                   # React/Vite web client at http://127.0.0.1:5173
```

Rules of the road:

- **uv is the only supported install path.** uv creates and manages `.venv`; never
  create or activate a virtualenv manually. Always invoke tools as `uv run ...`.
  A `uv.lock` is committed; CI installs with `uv sync --locked`.
- **Wheel / `uv tool install` is NOT a supported deployment** — the repo itself
  supplies the registry, prompts, runbooks, UI workspace, and starter workspace.
- **Dev work needs the dev group too**: `uv sync --extra litellm --group dev`
  (the `litellm` extra is required by the default multi-provider registry, the
  dev group carries pytest/ruff/mypy/bandit/pip-audit).
- Onboarding checklist of record: `runbooks/01-setup.md`. Quick start: `README.md`.
  Full operator manual: `DOCUMENTATION.md`.

### Python versions

- `pyproject.toml` declares `requires-python = ">=3.10"`; CI tests the full
  matrix 3.10–3.14.
- `.python-version` pins **3.13** for local development. The known OpenAI
  streaming incompatibility applies only to Python ≥ 3.14 with openai SDK
  ≤ 1.109.1 (`_openai_streaming_construct_type_incompatible`,
  `src/crisai/cli/pipeline_display.py:178-187`); the lock has been on the
  openai 2.x line (2.44.0) since `a010c8f` (2026-07-01), so the fallback
  detector should not fire on a correct bootstrap. Whether 3.14 + openai 2.x
  streams correctly live is unverified; `README.md:27` still carries the
  pre-2.x wording (stale). Details → `crisai-debugging-playbook` §H.

### API keys — which, and when

Do not catalogue env vars here (that is crisai-config-and-flags territory); the
setup-critical key facts are:

| Key | Needed when |
|---|---|
| `OPENAI_API_KEY` | **At agent BUILD time**, not just call time. Shipped OpenAI models set `base_url`, which forces eager client construction — so `uv run crisai doctor --models` fails without it even though it makes no API call. Plain `doctor` only warns. |
| `GEMINI_API_KEY`, `DEEPSEEK_API_KEY` | Required by the default `registry/agents.yaml` (it mixes OpenAI + Gemini + DeepSeek). |
| `ANTHROPIC_API_KEY` | Only if your registry assigns Anthropic model refs. |
| None (`local` provider) | Local OpenAI-compatible endpoints (Ollama/vLLM/LM Studio) need no key unless the server enforces one (`api_key_env` on the model). |

Mono-provider shortcut: `cp registry/examples/agents.openai.yaml registry/agents.yaml`
(also `.gemini`, `.anthropic`, `.deepseek`, `.local` variants), then set only that
provider's key.

### Doctor as the gate

- `uv run crisai doctor` — config/registry/env validation. CI runs it as a hard
  step before pytest, so a dirty doctor is a broken build. Resolve errors first,
  then the warnings relevant to your setup (Microsoft token-cache warnings only
  matter if you use Graph retrieval).
- `uv run crisai doctor --models` — dry-builds every configured agent without
  calling providers. Run after any model/provider change. Caveats: needs
  `OPENAI_API_KEY` (see above); a malformed Gemini/Anthropic `base_url` **passes**
  `doctor --models` but breaks live calls — verify endpoint changes with a real
  request.
- `uv run crisai validate-artefacts` — artefact-profile validation.
- `uv run crisai list-agents` — cheapest runtime-only functional check.

## `./start` anatomy

`./start` first: `cd`s to the repo root, verifies uv exists, exports
`PYTHONPATH=./src`, and sources `.env` with `set -a` (so everything in `.env`
becomes process environment). Default subcommand is `gem`. Subcommands as of
2026-07-02 (the full set — nothing else exists in the script):

| Subcommand | What it runs | Notes |
|---|---|---|
| `api` | `uv run crisai-web` → `crisai.apps.web:main` → uvicorn | **Start this first.** Binds hardcoded `127.0.0.1:8000`. |
| `web` | `uv run python -m crisai.cli.main web-react` → `npm --prefix ui run dev:web` → Vite | Requires api. Binds hardcoded `127.0.0.1:5173`. Launcher auto-maps `CRISAI_API_KEY`/`CRISAI_API_TOKEN` and `CRISAI_RUNTIME_URL` to the `VITE_*` vars if unset. |
| `gem` (alias `cli`) | `uv run python -m crisai.cli.main gem-ink` → `npm run dev:gem` | Ink terminal client. Requires api. |
| `hcom [all-up] [agy [claude\|gemini]] [claude-dev] [-- args]` | `scripts/hcom_start.sh` (with `--resume` when `reference/development/session_assignments.local.yaml` has matching role assignments) | Dev-team tmux orchestration, NOT product runtime. `all-up` = persistent reviewers; `agy` = Antigravity review provider (with `claude`/`gemini` model profile); `claude-dev` (aliases `claude-main`, `claude-coders`) = Claude Code developers + Codex reviewers. Operating it → crisai-devteam-operations. |
| `hcom-attach` | `scripts/hcom_attach.sh` | Attach to the running hcom tmux session. |
| `knowledge` | Clone or `git pull --ff-only` `CRISAI_KNOWLEDGE_REPO` into `workspace/knowledge/` | Fails with guidance if the var is unset, or if the dir has non-clone content (prints one-time migration steps). |
| `knowledge-pr "desc"` | Branch + commit + push + `gh pr create` from `workspace/knowledge` edits | Needs `gh` logged in. **Refuses tracked-file deletions** (maintainer action). Never merges. |

### Ports — hardcoded, and a trap

- API: `127.0.0.1:8000`, hardcoded in `src/crisai/apps/web.py` (uvicorn config,
  line 1739 as of 2026-07-02). Web dev server: `127.0.0.1:5173`, hardcoded in
  `ui/apps/web/package.json` (`"dev": "vite --host 127.0.0.1 --port 5173"`).
- `CRISAI_API_PORT` / `CRISAI_WEB_PORT` are read **only by `./stop`** to find
  listeners to kill. Setting them changes what `./stop` kills, not what
  `./start` binds.

### `./stop` behaviour

Kills the api and web processes: collects PIDs listening on
`${CRISAI_API_PORT:-8000}` and `${CRISAI_WEB_PORT:-5173}` (via `ss`, falling
back to `lsof`) plus `pgrep -f` matches on the crisAI-specific patterns
`crisai-web`, `crisai.cli.main web-react`, `run dev:web`, `@crisai/web run dev`.
SIGTERM first, waits up to ~5 s, then SIGKILL; reports ports still in use.
**It deliberately leaves `./start gem` running** (it is your interactive
terminal).

## Fresh-clone gotchas

1. **A fresh clone has NO assistant rules.** `CLAUDE.md`, `AGENTS.md`, and
   `GEMINI.md` are gitignored ("local to each developer's toolchain") — copy
   them from a teammate's checkout. The three are kept byte-identical by
   convention; if you edit one, sync all three.
2. **`plans/` and `DESIGN-IS-*/` are gitignored** — local planning artefacts do
   not travel with the repo.
3. **`workspace/knowledge/` is empty on a fresh clone.** It is a separate plain
   git clone (not a submodule) of the repo named in `CRISAI_KNOWLEDGE_REPO`
   (currently github.com/crissdiamond/architecture-knowledge). Set the var in
   `.env` and run `./start knowledge`.
4. **`workspace/tasks/*/` contents are gitignored** — task workspaces and the
   de facto TestNNN eval corpus are per-machine state, not shared via git.
5. **`.env` is gitignored**; bootstrap copies `.env.example` only when `.env` is
   missing. If doctor reports `.env` missing keys from `.env.example`, add only
   the missing key names — never overwrite existing local secrets.

## Workspace layout — what lands where

Governed by `registry/workspace_spaces.yaml`. "Agent-visible" means reachable by
the workspace MCP tools; **dot-prefixed entries are invisible to agents by
design**.

| Path | Purpose | Access |
|---|---|---|
| `workspace/knowledge/` | Approved curated corpus; separate git clone (see above) | Agent read-only; gitignored |
| `workspace/knowledge_staging/` | Agent-writable drafting/review area for knowledge; excluded from production retrieval; promotion target is `knowledge/` | Read-write root |
| `workspace/tasks/<id>/artefacts/` | Task deliverables (designs, HLDs, options papers, ...) | Writable (tasks root) |
| `workspace/tasks/<id>/inputs/` | User-supplied inputs (also the UI upload target `task_inputs`) | Writable |
| `workspace/tasks/<id>/scratch/` | Working files | Writable |
| `workspace/tasks/<id>/exports/` | DOCX/PPTX exports from reviewed Markdown | Writable (document_formatter) |
| `workspace/tasks/<id>/sources/` | Materialised source cache (raw file + extracted sidecar per source-id/revision) when `CRISAI_MATERIALISE_SOURCES` is on. Deliberately at the visible task root — **not** under `.crisai/` — so agents can re-read it and users can inspect/delete it (ADR-015 2b) | Visible, user-deletable |
| `workspace/tasks/<id>/.crisai/` | Session state: manifest, history, compact memory, anchors, and `runs/<run_id>.json` web run history | Hidden from agents; **never write agent-consumable data here** |
| `workspace/outputs/` | General output root for non-task writes | Writable root |
| `workspace/chat_sessions/` | Legacy session files (`<s>.json`, `<s>.memory.json`), still read for compatibility | Internal |
| `workspace/.cache/` | Intranet page cache | Hidden |
| `logs/` | `crisai.log`, `agent_trace.jsonl`, per-MCP `*_mcp.log` — interpretation → crisai-diagnostics-and-tooling | Gitignored |
| `.tokens/`, `.auth/` | Microsoft token caches (0600 files / 0700 dirs on POSIX) | Never delete via cleanup scripts |

Settings precedence (one line; full catalogue → crisai-config-and-flags):
env vars > `<repo>/.crisai/settings.json` > `~/.crisai/settings.json` > defaults;
`load_settings()` resolves relative `CRISAI_{WORKSPACE,LOG,REGISTRY}_DIR` under
the repo root and **mkdirs them on every call**.

## Known setup traps and fixes

| Trap | Fix |
|---|---|
| `doctor --models` fails with a missing-key error despite no API call | Set `OPENAI_API_KEY` — build-time resolution (see API keys table). |
| Smoke tests skip/fail although keys are in `.env` | pytest does not read `.env`. Export first: `set -a; . ./.env; set +a`, then `CRISAI_RUN_SMOKE_TESTS=1 uv run pytest tests/smoke -q`. (Test policy detail → crisai-validation-and-qa.) |
| Created/activated a venv manually and imports break | Delete it; uv owns `.venv`. Use `uv run ...` for everything. |
| `./start web` / `./start gem` fail after bootstrap | npm was missing at bootstrap time and UI deps were skipped. Run `npm --prefix ui install` once. |
| Changed `CRISAI_API_PORT`/`CRISAI_WEB_PORT` but services still bind 8000/5173 | Expected: those vars only steer `./stop`. Binds are hardcoded. |
| Junk repo-root dirs literally named `--no-cov/`, `-q/`, `--collect-only/`, each containing `.auth/` | Live import-time bug (tracked as TODO-059, unfixed as of 2026-07-03): every MCP server module treats `sys.argv[1]` as a workspace root and mkdirs `<arg>/.auth` (`src/crisai/servers/sharepoint_server.py:29-34`), so any `pytest <arg> ...` invocation creates `<arg>/.auth/` — a leading flag litters the repo root, a leading path litters that path (`tests/unit/.auth/` exists from exactly this). Path-first is NOT safe, only differently placed; prefer plain `uv run pytest` from the repo root. Droppings are safe to delete. |
| Empty `custom-registry/`, `custom-workspace/`, `custom-logs/` at repo root look like an override feature | They are residue from `tests/unit/test_config.py` (which points `CRISAI_*_DIR` at them) plus the unconditional mkdir in `config.py`. Real override mechanism: `CRISAI_{REGISTRY,WORKSPACE,LOG}_DIR` env vars or `.crisai/settings.json`. Safe to delete; they recur when that test runs. |
| Agent "cannot see" a workspace file | Dot-prefixed entries and reserved names (`.auth/`, `.tokens/`, `.crisai/`, `chat_sessions/`, ...) are excluded from the agent-visible surface by design. Move content out of dotfiles. |
| Doctor passes but live Gemini/Anthropic calls fail | Malformed `base_url` — `doctor --models` never calls the provider. Test with a real request. |
| Behaviour on this machine differs from docs | As of 2026-07-02 the local `.env` runs two non-defaults: `CRISAI_MATERIALISE_SOURCES=true` (shipped default false) and `CRISAI_DEFAULT_MODEL=gpt-5.4-nano` (README example: gpt-5.4-mini). Always distinguish local config from shipped defaults. |
| API is wide open / no auth locally | Intended for 127.0.0.1 single-user use: auth is a no-op until `CRISAI_API_KEY` is set. Set a long random value before any network/team exposure. (Full security flags → crisai-config-and-flags.) |

## Daily operation

- Order matters: `./start api` first, then `web`/`gem`. `./stop` to tear down
  api+web; Ctrl-C the gem terminal yourself.
- Cheapest sanity check per surface: runtime `uv run crisai list-agents`;
  API `./start api`; then attach a client. Non-interactive one-shot:
  `uv run crisai ask --session X --message "..."`.
- Knowledge loop: `./start knowledge` to sync down; draft in
  `workspace/knowledge_staging/`; after human review/promotion into
  `workspace/knowledge/`, submit with `./start knowledge-pr "desc"`.
- Disk cleanup: `scripts/clean_local.sh` (dry-run by default; `--apply` to act;
  categories `--rebuildable` (default), `--deps` (.venv + node_modules),
  `--hcom`, `--logs`, `--workspace-state`; `--all` = everything except
  `--workspace-state`). It never removes `.env`, `.tokens`, `.auth`,
  `workspace/.auth`, or `workspace/knowledge`.
- `scripts/run_cli.sh` = `uv run python -m crisai.cli.main "$@"` with
  `PYTHONPATH` set — handy for ad-hoc CLI invocations.

## When NOT to use this skill

- **Env var / flag catalogue** (defaults, clamps, security-internal vars) →
  crisai-config-and-flags. This skill only names setup-critical keys.
- **Test commands, markers, coverage, smoke-test policy** → crisai-validation-and-qa.
- **Reading traces/logs, `crisai spend`, deep doctor usage, measuring behaviour**
  → crisai-diagnostics-and-tooling.
- **Operating the hcom dev team** (roster, profiles, review providers, resume
  semantics) → crisai-devteam-operations. This skill only lists the `./start
  hcom` entry points.
- **Runtime failures once services are up** (wrong routing, gate failures,
  timeouts) → crisai-debugging-playbook.
- **UI development** (React/Ink workspace, design system, contract sync) →
  crisai-ui-surfaces.
- **Branch/PR/commit discipline and change gating** → crisai-change-control.

## Provenance and maintenance

Verified against the working tree on 2026-07-02. Re-verify volatile facts with:

- `./start` subcommand set: `grep -n '^  [a-z-]*)' start`
- `./stop` ports/patterns: `sed -n '14,24p' stop`
- Bootstrap steps: `cat scripts/bootstrap.sh`
- Hardcoded API bind: `grep -n 'host="127.0.0.1", port=8000' src/crisai/apps/web.py`
- Hardcoded Vite bind: `grep -n '"dev"' ui/apps/web/package.json`
- Entry points: `grep -n -A2 'project.scripts' pyproject.toml`
- Python support: `grep -n 'requires-python' pyproject.toml && cat .python-version`; 3.14 caveat: `grep -n '3.14' README.md`
- CI doctor gate + matrix: `grep -n 'crisai doctor\|python-version' .github/workflows/ci.yml`
- Gitignored assistant rules / knowledge / plans: `grep -n 'CLAUDE.md\|knowledge/\|plans/' .gitignore`
- Task subdirs + writable roots: `grep -n -A6 'task_subdirs\|writable_roots' registry/workspace_spaces.yaml`
- Sources cache lands at visible task root: `grep -n 'task_state_dir = ' src/crisai/cli/pipelines.py` (note: the docstring in `src/crisai/workspace/source_cache.py` still says `.crisai/sources/` — stale; the call site comment at pipelines.py:256-258 is authoritative)
- OPENAI key at build time: `grep -n 'OpenAI key at build time' DOCUMENTATION.md`
- Materialisation default: `grep -n 'CRISAI_MATERIALISE_SOURCES' .env.example` vs local `.env`
- argv[1]/.auth bug still present: `sed -n '29,34p' src/crisai/servers/sharepoint_server.py`; droppings: `ls -d ./--no-cov ./-q ./--collect-only 2>/dev/null`
- Settings precedence + mkdir: `grep -n -A8 'def load_settings' src/crisai/config.py`
