---
name: crisai-config-and-flags
description: Complete catalogue of every crisAI environment variable (default, effect, guards/clamps, production vs experimental) and every registry/*.yaml file (owner, loader, hard-fail vs fail-open, cached vs live-reload). Load this when you need to know what a CRISAI_* / MS_* / VITE_* variable does, what its real code default is, why setting a value "did nothing" (silent fallback, clamp, hardcoded port), which registry file owns a behaviour, how settings precedence works (env > .crisai/settings.json > defaults), or when adding a new flag and needing the add-a-flag checklist. Also covers the two security-internal variables that must never be set manually.
---

# crisAI configuration and flags

Ground-truth reference for runtime configuration, verified against the repo on 2026-07-02
(branch `main`). Every default below cites the file and line that defines it; re-verification
one-liners are at the end.

## 1. How configuration is loaded

Precedence, highest first (`src/crisai/config.py:141-149`):

1. Environment variables
2. Project settings `<repo>/.crisai/settings.json`
3. Global settings `~/.crisai/settings.json`
4. Code defaults

Mechanics you must know:

- `config.py:11` calls `load_dotenv()` at import time, so `.env` at the repo root is read by
  every Python entry point. `./start` additionally exports `.env` into the shell environment
  (`start:14-18`, `set -a; source .env; set +a`).
- `load_settings()` **mkdirs the workspace/log/registry directories on every call**
  (`config.py:214-216`). This is why pointing `CRISAI_WORKSPACE_DIR` at a non-existent path
  silently creates it — and why the stray `custom-workspace/`, `custom-logs/`,
  `custom-registry/` directories at the repo root exist: they are residue of
  `tests/unit/test_config.py`, **not** an override feature. The real override mechanism is
  the `CRISAI_{WORKSPACE,LOG,REGISTRY}_DIR` variables or `.crisai/settings.json`
  (whole-directory replacement).
- Boolean env vars accept `1/true/yes/on` and `0/false/no/off`; anything else falls back to
  the default (`config.py:87-97`). Most feature gates elsewhere in the codebase test only the
  truthy set `{"1","true","yes","on"}` (e.g. `cli/pipelines.py:221`).
- Numeric resolvers **never raise** on bad input — they silently return the default
  (`config.py:100-109` and every `_resolve_*` helper cited below). `uv run crisai doctor` is
  the only thing that will tell you your value was ignored: it validates the tables in
  `src/crisai/registry_validation.py:29-34` (`_BOOLEAN_ENV_VARS`) and `:76-91`
  (`_NUMERIC_ENV_VARS`).
- Smoke tests need provider keys exported in the shell, not just present in `.env`
  (DOCUMENTATION.md section 17: `set -a; . ./.env; set +a`).

## 2. Environment variable catalogue

Status legend: **prod** = stable default path; **exp** = experimental/opt-in, validate before
relying on it; **script** = read only by a shell script, not by Python.

### 2.1 Core paths, logging, CLI display (`config.py:185-197` env map)

| Variable | Default | Effect | Status | Guard/clamp |
|---|---|---|---|---|
| `CRISAI_LOG_LEVEL` | `INFO` (`config.py:155`) | Log level for `logs/crisai.log` | prod | — |
| `CRISAI_WORKSPACE_DIR` | `<repo>/workspace` (`config.py:156`) | Workspace root (agent-visible files) | prod | Relative paths resolved under repo root; auto-created |
| `CRISAI_LOG_DIR` | `<repo>/logs` (`config.py:157`) | Log/trace directory | prod | Same |
| `CRISAI_REGISTRY_DIR` | `<repo>/registry` (`config.py:158`) | Registry YAML directory (whole-directory override) | prod | Same |
| `CRISAI_DEFAULT_MODEL` | `gpt-5.4-mini` (`config.py:34,169`) | General default model label where applicable | prod | Model names are user config from `registry/models.yaml`; never treat as fixed |
| `CRISAI_VERBOSE` | `false` (`config.py:25`) | Verbose CLI display | prod | Boolean parse |
| `CRISAI_THEME` | `default` (`config.py:27`) | CLI display theme name | prod | — |
| `CRISAI_TERMINAL_TITLE_ENABLED` | `false` (`config.py:28`; gate also at `cli/display.py:110`) | OSC terminal-title updates | prod | Boolean parse; doctor-validated |
| `CRISAI_RETRIEVAL_CHECKPOINT_ENABLED` | `true` (`config.py:26`) | Human pause after pipeline retrieval (continue/redirect/stop) | prod | Boolean parse; doctor-validated |
| `CRISAI_RETRIEVAL_CHECKPOINT_MAX_REDIRECTS` | `2` (`config.py:39`) | Max redirect attempts at one retrieval checkpoint | prod | **Quirk**: parsed by `_env_positive_int` (`config.py:100-109`), so `0` falls back to `2` — the env var cannot express "no redirects", even though doctor (`registry_validation.py:79`) accepts `0` as valid. Verified 2026-07-02, unfixed. |

### 2.2 Web API (`src/crisai/apps/web.py`)

| Variable | Default | Effect | Status | Guard/clamp |
|---|---|---|---|---|
| `CRISAI_API_KEY` | empty (`web.py:194`) | When set: `Authorization: Bearer <key>` required on **all** `/api` requests (constant-time compare, 401 + `WWW-Authenticate` otherwise, `web.py:194-205`). When empty: **auth middleware is a no-op** — deliberate local single-user default; doctor warns (`registry_validation.py:746-753`) | prod | Whitespace-stripped |
| `CRISAI_RATE_LIMIT_RPM` | `0` = disabled (`web.py:133`) | Max POST/minute on `/api/run`, `/api/run/start`, `/api/v1/runs` (`web.py:134`); 429 + `Retry-After`. Single **global in-memory fixed 60 s window** shared by all clients (`web.py:135,150-180`) | prod | Non-positive or unparsable → disabled (`web.py:138-147`); doctor-validated |
| `CRISAI_CORS_ORIGINS` | `http://127.0.0.1:5173, http://localhost:5173` (`web.py:215-218`) | Comma-separated CORS allow-list. CORS middleware is registered last = outermost (`web.py:221-231`) — do not reorder middleware, or 401/429 become opaque CORS failures in the browser | prod | — |

The API bind `127.0.0.1:8000` and Vite bind `127.0.0.1:5173` are **hardcoded**
(`web.py:1739`; `ui/apps/web/package.json:7`). No env var changes them.

### 2.3 Agent execution and peer workflow

| Variable | Default | Effect | Status | Guard/clamp |
|---|---|---|---|---|
| `CRISAI_AGENT_MAX_TURNS` | `30` (`cli/pipeline_display.py:51,112-127`) | Max turns per agent before the run aborts (web surfaces it as a 422, `web.py:688`) | prod | ≤0 or unparsable → 30; doctor-validated (min 1) |
| `CRISAI_AGENT_STAGE_TIMEOUT_SECONDS` | `300.0` (`cli/pipeline_engine.py:33,38-45`) | Max seconds for one pipeline/peer stage before it is failed and traced | prod | ≤0 or unparsable → 300; doctor-validated (>0 float) |
| `CRISAI_PEER_MAX_REFINEMENT_ROUNDS` | `2` (`orchestration/peer_judge.py:19,119-133`) | Extra refiner/judge rounds after the first judge pass | prod | `max(0, parsed)`; doctor-validated |
| `CRISAI_PEER_MAX_ESCALATIONS` | `1` (`orchestration/peer_judge.py:20,136-150`) | Author/challenger rerun attempts when revise loops stall | prod | `max(0, parsed)`; doctor-validated |

### 2.4 Feature gates (experimental — the flag-to-default lifecycle lives here)

| Variable | Default | Effect | Status | Guard/clamp |
|---|---|---|---|---|
| `CRISAI_MATERIALISE_SOURCES` | off (`cli/pipelines.py:212-222`; `.env.example:84` = `false`) | CRISAI-ADR-015 Phase 2b: fetch checkpoint-confirmed sources once and cache raw file + extracted sidecar under the task's visible `sources/` dir so later turns read a stable local copy. Best-effort; failures traced, never abort the run (`pipelines.py` `_materialise_confirmed_sources`) | **exp** — "opt-in while validated". As of 2026-07-02 this machine's local `.env:82` sets `true` (non-default); shipped default is false | Truthy-set parse only |
| `CRISAI_DETERMINISTIC_MCP_ADVISORY` | off (`cli/pipelines.py:208-209`) | Advisory deterministic retrieval MCP lookups for peer challenger/judge guidance; canonical deterministic context stays authoritative | **exp** | Truthy-set parse; doctor-validated boolean |
| `CRISAI_RUN_SMOKE_TESTS` | unset (`tests/smoke/conftest.py:26`) | `=1` enables live-LLM smoke tests (otherwise skipped) | prod (test guard) | — |

### 2.5 MCP servers and workspace write controls

| Variable | Default | Effect | Status | Guard/clamp |
|---|---|---|---|---|
| `CRISAI_MCP_CLIENT_TIMEOUT_SECONDS` | `60` (`runtime.py:24`) | MCP ClientSession timeout for `list_tools`/tool calls (SDK default of 5 s is too short for heavy stdio servers) | prod | **Min-clamped to 10** (`runtime.py:29`) — you cannot set it lower. Per-server `client_timeout_seconds` in `registry/servers.yaml` overrides it and **bypasses the clamp** (`runtime.py:32-47`); shipped overrides: documents 120, sharepoint_docs 240, intranet 600 |
| `CRISAI_WORKSPACE_MAX_WRITE_BYTES` | `1_000_000` (`servers/workspace_server.py:23,66-71`) | Byte cap per workspace write/append call | prod | **Floor 1024** (`workspace_server.py:71`); doctor-validated (min 1024) |
| `CRISAI_WORKSPACE_WRITE_SUBDIRS` | from `registry/workspace_spaces.yaml` `writable_roots`, falling back to `outputs, scratch, knowledge_staging, tasks` (`workspace_server.py:21,60-62`) | Comma-separated subdirs the workspace MCP may write into | prod | Empty → default |
| `CRISAI_WORKSPACE_WRITE_EXTENSIONS` | `.md,.txt,.json,.yaml,.yml,.csv,.mmd` (`workspace_server.py:22,86`) | Extension allowlist for workspace writes | prod | Empty → default |
| `CRISAI_DIAGRAM_MAX_WRITE_BYTES` | `500_000` (`servers/diagram_server.py:16,42-46`) | Byte cap per `save_diagram` call | prod | **Floor 1024**; doctor-validated (min 1024) |
| `CRISAI_VISION_MODEL` | `gpt-4o-mini` (`vision.py:18,24`) | OpenAI model the vision server uses to describe images/PPTX pictures/scanned PDF pages | prod | — |
| `CRISAI_PDF_VISION_MAX_PAGES` | `8` (`servers/document_server.py:61,152-161`) | Max image-only PDF pages read per file via vision (each page = one vision call = cost). `0` disables the fallback | prod | `max(0, parsed)`; doctor-validated (min 0) |

### 2.6 Session memory (defaults come from `registry/session_memory.yaml`; env overrides in `cli/chat_context.py:122-153`)

| Variable | Registry default | Effect | Guard/clamp |
|---|---|---|---|
| `CRISAI_SESSION_MEMORY_STRATEGY` | `deterministic` | `deterministic` or `agentic`; anything else silently coerced to `deterministic` (`chat_context.py:147-149`); doctor warns (`registry_validation.py:755-760`). `agentic` (via `memory_summarizer`) is the non-default path — treat as **exp** | Enum coercion |
| `CRISAI_SESSION_MEMORY_AGENT_ID` | `memory_summarizer` | Agent used by the agentic strategy | — |
| `CRISAI_SESSION_MEMORY_MAX_RECENT_TURNS` | `2` | Recent turns kept verbatim | `max(0, …)` (`chat_context.py:150`) |
| `CRISAI_SESSION_MEMORY_MAX_RUNTIME_CHARS` | `6000` | Runtime context budget | **Floor 1000** (`chat_context.py:151`) |
| `CRISAI_SESSION_MEMORY_MAX_MEMORY_CHARS` | `3000` | Compact memory budget | **Floor 500** (`chat_context.py:152`) |
| `CRISAI_SESSION_MEMORY_TASK_DRIFT_NUDGE` | `true` | Task-drift nudge toggle | Boolean; doctor-validated |

### 2.7 Model provider credentials

| Variable | Effect |
|---|---|
| `OPENAI_API_KEY` | OpenAI key; also feeds `settings.model.openai_api_key` (`config.py:190`). **Required at agent build time** — even `uv run crisai doctor --models` — because the shipped OpenAI models set `base_url` in `registry/models.yaml`, which forces eager `AsyncOpenAI` client construction (`model_resolver.py:94-103`, `agents/factory.py`) |
| `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY` | Provider-default key env names, resolved in `model_resolver.py:140-160`; a per-model `api_key_env` in `registry/models.yaml` overrides the name (`model_resolver.py:135,154`) |
| `QWEN_API_KEY` (or any name you choose) | Optional key for the `local` provider (OpenAI-compatible endpoints: Ollama/vLLM/LM Studio); missing key is **not** an error for `local` (`model_resolver.py:122-138`) |
| `OPENAI_AGENTS_DISABLE_TRACING` | Consumed by the OpenAI Agents SDK, not by crisAI code (only reference: `.env.example:64`). Stops sending traces to OpenAI; no effect on crisAI's own JSONL traces |

For remote SSE/streamable-http MCP servers, `api_key_env` in `registry/servers.yaml` names an
env var whose value is injected as `Authorization: Bearer …` (`runtime.py:57-73`).

### 2.8 Microsoft Graph / SharePoint (`src/crisai/ms_graph.py`)

| Variable | Default | Effect |
|---|---|---|
| `MS_TENANT_ID`, `MS_CLIENT_ID` | empty (`ms_graph.py:40-41`) | Entra app identity for delegated Graph auth (SharePoint + intranet MCPs) |
| `MS_CLIENT_SECRET` | empty | **Ignored** (verified 2026-07-02): present in `.env.example:139` but never read by code; `ms_graph.py:121-123` uses the public-client flow only and its docstring explicitly states a client secret "is not used for auth flows; it is ignored here" |
| `MS_REDIRECT_URI` | `http://localhost` (`.env.example:140`) | **Dead key** (verified 2026-07-02): listed in `.env.example:140` but read by nothing in `src/`, `tests/`, or `scripts/`; the delegated device-code/interactive flows do not consume it — setting it changes nothing |
| `MS_GRAPH_SCOPES` | — | **Dead key** (verified 2026-07-02): listed in `.env.example:147` but read by nothing in `src/`, `tests/`, or `scripts/`. Actual scopes are the hardcoded `DEFAULT_SCOPES` list `User.Read, Sites.Read.All, Files.Read.All` (`ms_graph.py:34-38`); setting this env var changes nothing |
| `MS_TOKEN_CACHE_PATH`, `MS_TOKEN_INFO_PATH` | derived under `<workspace-root>/.auth/` per namespace (`ms_graph.py:49-75`) | MSAL token cache locations. Files written 0600, dirs 0700. Both names are in `SENSITIVE_PATH_ENV_VARS` (`workspace/safety.py:27-30`) so their targets are deny-listed from workspace access (`safety.py:158-161`); doctor warns if they point inside the workspace (`registry_validation.py:584-604`) and audits permissions on known candidates (`registry_validation.py:607-637`) |
| `WSL_DISTRO_NAME` | set by WSL itself | Checked at `ms_graph.py:134` to adapt the interactive-login flow |

### 2.9 Intranet

| Variable | Default | Effect |
|---|---|---|
| `INTRANET_PAGE_CACHE_TTL_HOURS` | env > `registry/intranet.yaml` `limits.page_cache_ttl_hours` > `4` (`intranet/config.py:60-61`) | On-disk TTL of the intranet page catalogue. Digits-only parse; doctor-validated (min 1) |

### 2.10 UI clients (React web + Ink Gem)

| Variable | Default | Effect |
|---|---|---|
| `CRISAI_RUNTIME_URL` | `http://127.0.0.1:8000` (Gem: `ui/apps/gem/src/index.tsx:81`) | Runtime API base URL for clients |
| `VITE_CRISAI_RUNTIME_URL` | `http://127.0.0.1:8000` (`ui/apps/web/src/lib/runtime.ts:10`) | Same, web build-time var. The `web-react` launcher maps `CRISAI_RUNTIME_URL` → `VITE_CRISAI_RUNTIME_URL` unless already set (`cli/main.py:897-910`) |
| `VITE_CRISAI_API_KEY` / `VITE_CRISAI_API_TOKEN` | empty (`runtime.ts:5-6`) | Bearer token for the web client; launcher maps `CRISAI_API_KEY`/`CRISAI_API_TOKEN` into these (`cli/main.py:900-907`) |
| `CRISAI_API_TOKEN` | — | **Legacy client-side alias only.** Gem reads it as a fallback (`index.tsx:85`); the server checks only `CRISAI_API_KEY`. Prefer `CRISAI_API_KEY` |

### 2.11 Script-only variables (never read by Python runtime)

| Variable | Default | Read by | Effect |
|---|---|---|---|
| `CRISAI_API_PORT` | `8000` (`stop:14`) | `./stop` **only** | Which port to hunt for listeners to kill. Does **not** change the API bind (hardcoded 127.0.0.1:8000) |
| `CRISAI_WEB_PORT` | `5173` (`stop:15`) | `./stop` **only** | Same for the Vite dev server (hardcoded 127.0.0.1:5173) |
| `CRISAI_KNOWLEDGE_REPO` | unset (`start:204`) | `./start knowledge` / `knowledge-pr` | Git URL cloned/ff-pulled into `workspace/knowledge` |
| `HCOM_TEAM_*`, `HCOM_*` | various | `./start hcom`, `scripts/hcom_*.sh` | Dev-team tmux apparatus configuration — see the **crisai-devteam-operations** skill |

## 3. Security-internal variables — NEVER set manually

These two are part of the runtime security model, set and cleared by orchestration code.
Setting them by hand widens agent access.

| Variable | Set by | Mechanism | Why manual setting is dangerous |
|---|---|---|---|
| `CRISAI_WORKSPACE_AUTHORIZED_WRITE_PATHS` | `cli/workflow_policy.py:128-146` (`workspace_write_authorization_env` context manager), per run, restored/cleared afterwards | Comma-separated **exact** workspace-relative paths the workspace MCP may write outside the normal writable roots (`servers/workspace_server.py:24,55-57,81`). Granted only for user-requested knowledge-promotion targets, with validation required | A manually exported value persists across runs and grants every agent write access to those paths, bypassing the writable-roots policy |
| `CRISAI_SESSION_MEMORY_SESSION` | `cli/pipelines.py:398-402` (`_session_memory_env`), injected into the session-memory MCP subprocess env per run | Scopes session-memory tools to the active session; the server raises `PermissionError` without it and rejects any other session name (`servers/session_memory_server.py:21,41-53`) | Manually pinning it lets agents read another session's memory (cross-session leakage) |

## 4. Registry file inventory (`registry/`)

All behaviour-tuning YAML. Whole-directory replacement via `CRISAI_REGISTRY_DIR`. `uv run
crisai doctor` hard-requires seven of these files to exist and parse
(`registry_validation.py:460-468`): agents, servers, models, workflow_policy, session_memory,
semantic_catalog, semantic_graph.

| File | Owns | Loaded by | Missing/invalid behaviour | Caching |
|---|---|---|---|---|
| `agents.yaml` | Agent roster: id, name, `model_ref`, `prompt_file`, `allowed_servers` (15 agents) | `Registry.load_agents` (`registry.py:152`) | **Hard-fail** (unguarded `read_text`) | Re-read per call |
| `servers.yaml` | MCP server specs: transport, `kind: source\|tool`, capabilities, `tools.allow` vs `tools.internal`, `client_timeout_seconds`, `api_key_env` | `Registry.load_servers` (`registry.py:113`) | **Hard-fail** | Re-read per call |
| `models.yaml` | Logical model refs → provider/model_name/api_key_env/base_url/thinking/pricing. Single source of model names | `Registry.load_models` (`registry.py:130-132`) | **Fail-open: returns `[]` when missing** (unlike agents/servers) | Re-read per call |
| `semantic_catalog.yaml` | Router term lists, peer-verifier regexes, peer-contract/judge markers, lexicon, retrieval source-fit constraints (see **crisai-semantic-registry-reference**) | `load_semantic_catalog` (`orchestration/semantic_catalog.py:591-613`) | **Hard-fail**: `FileNotFoundError` / `SemanticCatalogError` on missing/invalid required keys | **`functools.lru_cache(maxsize=8)`** (`semantic_catalog.py:591`) — a long-running `crisai-web` process does NOT see edits; restart the API after editing |
| `semantic_graph.yaml` | Task-intent vertices, deliverable types, source families, deterministic retrieval expansion | `load_retrieval_association_graph` (`orchestration/retrieval_association_graph.py:148-166`) | **Fail-open**: warning logged, graph disabled ("retrieval nudge disabled"), run continues | Re-read per run; content SHA1[:12] traced as `graph_version` (`retrieval_association_graph.py:322-331`) |
| `workflow_policy.yaml` | Capability markers → hard gates (intranet_grounded, produce_artifacts), write target subdir | `_load_policy_config` (`cli/workflow_policy.py:154-175`) | **Fail-open** to `_STRUCTURAL_DEFAULTS` (`workflow_policy.py:80-87`) | Re-read per call |
| `session_memory.yaml` | Compact task-memory defaults (strategy, budgets) | `load_session_memory_config` (`cli/chat_context.py:122-153`) | **Fail-open** to code defaults; env vars in §2.6 override | Re-read per call |
| `workspace_spaces.yaml` | Workspace root names (knowledge/knowledge_staging/tasks), task subdirs, writable roots, knowledge corpora | `load_workspace_spaces` (`workspace/spaces.py:195-225`) | **Fail-open** to `WorkspaceSpaces()` defaults | Re-read per call |
| `workspace_artifact_profiles.yaml` | Artefact validation profiles for promoted knowledge | `load_artefact_profiles` (`workspace/artefact_validation.py:143-175`) | **Hard-fail** when validation runs: `FileNotFoundError` / `ValueError` | Re-read per call |
| `intranet.yaml` | Intranet provider, allow_hosts, sites, limits (incl. page cache TTL) | `load_intranet_settings` (`intranet/config.py:42-53`) | **Fail-open** to defaults with empty sites | Loaded at provider construction |
| `search_synonyms.yaml` | Intranet search synonym groups | Provider constructor (`intranet/providers/sharepoint_pages.py:273-278`) | **Fail-open**: absent file disables synonym expansion | **Loaded once per MCP server process** — restart the intranet server to pick up edits |
| `ui.yaml` | `ui_theme_v1` design tokens + stage labels served at `/api/v1/ui/theme` | `apps/web.py:468-480` (labels), `:836-847` (theme) | Labels **fail-open** to `{}`; theme endpoint **hard-fails**: 404 when missing, 500 when not `schema_version: ui_theme_v1` | Re-read per request |
| `policies.yaml` | Declares `approvals`, `tracing`, `runtime` blocks | **Nothing.** Verified 2026-07-02: no Python code reads any of its keys (`approvals`, `redact_secrets`, `auto_start_local_stdio_servers`, …) | n/a — the `approvals.enabled: true` block has **no enforcement behind it** (TODO-032). Do not describe or rely on an approval gate; real protection is the workspace server's path/write restrictions | n/a |
| `examples/agents.{openai,gemini,anthropic,deepseek,local}.yaml` | Mono-provider roster overlays — copy over `agents.yaml` to run on one provider | Human operator | n/a | n/a |

## 5. Add-a-flag checklist

Derived from how `CRISAI_RATE_LIMIT_RPM` was added (commit `8badc2e`, plus follow-ups
`47cdc97`, `65389d3`). A new operator flag is complete only when ALL of these exist:

1. **Code default + safe resolver** next to the consumer: a module-level
   `_DEFAULT_*` constant and a `_resolve_*()` that parses the env var, falls back to the
   default on any bad value, and applies the clamp (pattern: `web.py:133,138-147`).
   Never raise on a malformed value.
2. **Doctor registration** in `src/crisai/registry_validation.py`: add an
   `EnvValueSpec` entry to `_NUMERIC_ENV_VARS` (`:76-91`) or the name to
   `_BOOLEAN_ENV_VARS` (`:29-34`), matching the clamp exactly. This is the only place a
   user learns their value was silently ignored.
3. **`.env.example` entry** with a comment stating default, effect, and unit. Add optional
   flags **commented out**: doctor diffs uncommented `.env.example` keys against `.env`
   and nags about missing ones (`registry_validation.py:718-745`), so an uncommented
   optional flag forces every operator to add it.
4. **Docs**: DOCUMENTATION.md (env tables around line 1398 and wherever the feature is
   described; `CRISAI_RATE_LIMIT_RPM` landed at `DOCUMENTATION.md:1524`), plus README.md
   if setup-facing.
5. **Tests** under `tests/` using `monkeypatch.setenv`/`delenv`, including the
   default-off case; reset any module-level state (see the `_reset_rate_limit_state`
   fixture, `tests/integration/test_web_integration.py:45`).
   **Trap**: any pytest invocation creates a `.auth/` dropping at whatever
   `argv[1]` resolves to — MCP server modules treat `sys.argv[1]` as a workspace
   root at import time, so a leading flag creates `<flag>/.auth/` at the repo root
   and a leading path creates `<path>/.auth/` (e.g. `tests/unit/.auth/` exists on
   disk from exactly this). Path-first is NOT safe, only differently placed.
   Prefer plain `uv run pytest` from the repo root; full mechanics →
   **crisai-validation-and-qa**.
6. **Mode parity**: if the flag gates pipeline behaviour, wire it into `run_single`,
   `run_pipeline`, AND `run_peer_pipeline` (`cli/pipelines.py`). Fixes landing in one
   mode but not peer are this repo's dominant regression pattern.
7. **Experimental gates default OFF** (`CRISAI_MATERIALISE_SOURCES` is the live worked
   example: shipped false, validated locally as true, default flip pending) — see
   **crisai-research-methodology** for the flag-to-default lifecycle.

If the "flag" is actually vocabulary (routing terms, markers, regexes), it does not belong
in env at all — it goes in `registry/semantic_catalog.yaml` or `semantic_graph.yaml`
(CLAUDE.md rule; see **crisai-semantic-registry-reference**).

## 6. Known quirks worth re-checking before you debug config

- Per-server `client_timeout_seconds` in `servers.yaml` bypasses the 10 s minimum clamp
  that applies to `CRISAI_MCP_CLIENT_TIMEOUT_SECONDS` (`runtime.py:32-47` vs `:29`).
- `CRISAI_RETRIEVAL_CHECKPOINT_MAX_REDIRECTS=0` silently becomes 2 (§2.1).
- Rate limiter is one global window, not per client; auth middleware runs before it
  (middleware LIFO, `web.py:150-158` docstring).
- Local machine non-defaults as of 2026-07-02: `.env:9` `CRISAI_DEFAULT_MODEL=gpt-5.4-nano`,
  `.env:82` `CRISAI_MATERIALISE_SOURCES=true`. Behaviour observed locally is not shipped
  default behaviour — always check `.env` before comparing against defaults.
- `semantic_catalog.yaml` edits need an API restart (lru_cache); `semantic_graph.yaml`
  edits are picked up per run.
- `models.yaml` missing is silent (`[]`), which surfaces later as "unknown model_ref"
  doctor errors rather than a missing-file error.

## When NOT to use this skill

- Setting up the environment from scratch, `./start`/`./stop` anatomy, ports, doctor as a
  daily tool, workspace directory conventions → **crisai-build-run-operate**
- Editing `semantic_catalog.yaml` / `semantic_graph.yaml` contents, matching semantics,
  adding intents → **crisai-semantic-registry-reference**
- Reading traces/logs/run JSONLs, `crisai spend`, measuring behaviour →
  **crisai-diagnostics-and-tooling**
- Whether a change is a registry edit vs code change, gating, PR discipline →
  **crisai-change-control**
- Test commands and evidence standards → **crisai-validation-and-qa**
- hcom dev-team apparatus and its `HCOM_*` variables → **crisai-devteam-operations**
- Runtime failure triage ("why did my run fail") → **crisai-debugging-playbook**

## Provenance and maintenance

All facts verified directly against the repo on 2026-07-02 (branch `main`, HEAD `c39273b`).
Re-verify any drifted claim with:

```bash
# Full env-read inventory (the master list this catalogue was built from)
grep -rn "os.environ\|os.getenv" src/

# Settings precedence, env map, mkdir side effect
grep -n "env_map\|load_dotenv\|mkdir" src/crisai/config.py

# Doctor validation tables (numeric specs incl. clamps, boolean vars)
sed -n '29,91p' src/crisai/registry_validation.py

# Web defaults: rate limit, auth, CORS
grep -n "_DEFAULT_RATE_LIMIT_RPM\|CRISAI_API_KEY\|CRISAI_CORS_ORIGINS\|_RATE_LIMITED_PATHS" src/crisai/apps/web.py

# MCP timeout clamp and per-server override
sed -n '17,47p' src/crisai/runtime.py

# Workspace/diagram/document/vision server defaults
grep -n "DEFAULT_MAX_WRITE_BYTES\|DEFAULT_WRITE_SUBDIRS\|DEFAULT_WRITE_EXTENSIONS\|AUTHORIZED_WRITE_PATHS_ENV" src/crisai/servers/workspace_server.py
grep -n "DEFAULT_MAX_DIAGRAM_BYTES" src/crisai/servers/diagram_server.py
grep -n "_DEFAULT_PDF_VISION_MAX_PAGES" src/crisai/servers/document_server.py
grep -n "_DEFAULT_VISION_MODEL" src/crisai/vision.py

# Execution limits and peer budgets
grep -n "_DEFAULT_AGENT_MAX_TURNS" src/crisai/cli/pipeline_display.py
grep -n "_DEFAULT_STAGE_TIMEOUT_SECONDS" src/crisai/cli/pipeline_engine.py
grep -n "_DEFAULT_PEER_MAX" src/crisai/orchestration/peer_judge.py

# Experimental gates
grep -n "CRISAI_MATERIALISE_SOURCES\|CRISAI_DETERMINISTIC_MCP_ADVISORY" src/crisai/cli/pipelines.py

# Security-internal vars
grep -n "AUTHORIZED_WRITE_PATHS_ENV" src/crisai/cli/workflow_policy.py src/crisai/servers/workspace_server.py
grep -n "ACTIVE_SESSION_ENV\|CRISAI_SESSION_MEMORY_SESSION" src/crisai/servers/session_memory_server.py src/crisai/cli/pipelines.py

# Session memory defaults and clamps
sed -n '122,155p' src/crisai/cli/chat_context.py && cat registry/session_memory.yaml

# Registry loaders: hard-fail vs fail-open, catalog cache
grep -n "def load_servers\|def load_models\|def load_agents\|path.exists" src/crisai/registry.py
grep -n "lru_cache" src/crisai/orchestration/semantic_catalog.py
grep -n "retrieval nudge disabled\|graph_version" src/crisai/orchestration/retrieval_association_graph.py

# policies.yaml still has no consumer? (expect no hits outside the YAML itself)
grep -rn "auto_start_local_stdio_servers\|redact_secrets\|approvals" src/ tests/ --include='*.py'

# Script-only ports and knowledge repo
grep -n "CRISAI_API_PORT\|CRISAI_WEB_PORT" stop
grep -n "CRISAI_KNOWLEDGE_REPO" start

# UI client defaults
grep -n "127.0.0.1:8000" ui/apps/web/src/lib/runtime.ts ui/apps/gem/src/index.tsx
sed -n '897,910p' src/crisai/cli/main.py

# MS_GRAPH_SCOPES / MS_REDIRECT_URI still dead, MS_CLIENT_SECRET still ignored?
# (expect hits only in .env.example, plus ms_graph.py docstrings for the secret)
grep -rn "MS_GRAPH_SCOPES\|MS_REDIRECT_URI\|MS_CLIENT_SECRET" src/ tests/ scripts/ .env.example

# The add-a-flag reference commit
git show --stat 8badc2e

# Local non-defaults on this machine
grep -n "CRISAI_DEFAULT_MODEL\|CRISAI_MATERIALISE_SOURCES" .env .env.example
```
