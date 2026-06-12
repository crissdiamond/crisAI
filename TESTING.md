# crisAI Testing

> **Guide to the current test suite, how to run it, and what it protects.**

The crisAI test suite covers the CLI, web app, orchestration flows, registry loading, semantic catalogues, MCP server adapters, workflow policy gates, and document handling helpers. The default `pytest` command also enforces project coverage through `pytest-cov`.

---

## 1. What the suite protects

The suite provides confidence around:

- agent factory behaviour
- provider-aware model resolution
- registry loading for agents and models
- registry examples and validation
- heuristic routing
- task-contract and source-constraint inference
- pipeline mode sequencing
- peer mode sequencing and transcript handling
- peer judge decision parsing, peer filesystem evidence collection, and peer verifier behaviour
- command parsing and chat controller behaviour
- CLI state rendering helpers
- session persistence
- prompt builder assembly
- web app job lifecycle, shared UI runtime API, integration path, and bounded eviction
- UI workspace scaffolding for shared TypeScript contracts, React web, and Ink Gem
- document export, workspace search, SharePoint helper behaviour, intranet MCP behaviour, diagram MCP behaviour, PowerPoint extraction, and vision MCP path safety/tool behaviour
- import smoke tests for main orchestration modules

---

## 2. Current test layout

```text
tests/
  conftest.py

  cli/
    test_main.py
    test_main_imports.py
    test_pipelines.py
    test_workflow_support.py

  integration/
    test_peer_pipeline.py
    test_pipeline_execution.py
    test_web_integration.py

  orchestration/
    test_graph_login.py          (manual smoke test; skipped by pytest)
    test_peer_mode.py
    test_pipeline_mode.py

  smoke/
    test_smoke.py                (opt-in provider smoke tests)

  unit/
    test_agent_display_icons.py
    test_agent_factory.py
    test_agent_factory_provider.py
    test_artefact_validation.py
    test_chat_context.py
    test_config.py
    test_diagram_server.py
    test_display.py
    test_document_context_retrieval.py
    test_document_export_server.py
    test_evidence_contract.py
    test_image_server.py
    test_interaction_patterns.py
    test_intranet_provider.py
    test_intranet_server.py
    test_logging_utils.py
    test_main_review_routing.py
    test_model_resolver.py
    test_openai_agents_trace_compat.py
    test_output_stability.py
    test_peer_contract.py
    test_peer_evidence.py
    test_peer_judge.py
    test_peer_transcript.py
    test_peer_verifier.py
    test_pipeline_engine.py
    test_prompt_builders.py
    test_powerpoint.py
    test_prompt_scaffolding.py
    test_registry_defaults.py
    test_registry_examples.py
    test_registry_models.py
    test_registry_validation.py
    test_retrieval_association_graph.py
    test_router.py
    test_router_publisher.py
    test_router_regression.py
    test_runtime.py
    test_runtime_mcp_timeout.py
    test_schema_resources.py
    test_semantic_catalog.py
    test_session_store.py
    test_sharepoint_browser_open.py
    test_sharepoint_item_normalise.py
    test_sharepoint_site_filter.py
    test_source_constraints.py
    test_status_views.py
    test_task_contract.py
    test_ui_events.py
    test_ui_workspace.py
    test_web_app.py
    test_workflow_policy.py
    test_workspace_server_search.py
```

---

## 3. What these tests cover

### Agent and model layer
- prompt file loading still works
- agent construction still passes the expected prompt and server list
- provider-aware model resolution works for:
  - OpenAI
  - Gemini
  - Anthropic
  - DeepSeek through LiteLLM-compatible configuration
- legacy raw `model` fallback still behaves as expected
- model registry entries load correctly from `registry/models.yaml`

### CLI support layer
- session history file handling
- session persistence and sanitisation
- chat history wrapping
- command parsing
- command-driven state transitions
- route display formatting
- mode and agent pin state display
- chat-state summary rendering

### Routing layer
- retrieval-only prompts still route to `retrieval_planner` (legacy id `discovery` is normalized)
- mixed retrieval + drafting prompts still route to pipeline
- review prompts still route to review
- operations/debug prompts still route to operations
- publisher-oriented requests still route appropriately
- task-contract facts preserve summary, design, source-resolution, and evidence-level intent
- source constraints protect explicit title and source-scope matching

### Workflow execution layer
- `run_single(...)` continues to honour the selected agent
- `run_pipeline(...)` keeps the expected stage order
- `run_peer_pipeline(...)` keeps the expected stage order
- workflow helper functions keep shared runtime behaviour stable
- integration tests cover pipeline, peer pipeline, and web execution paths with fakes

### Peer judge and evidence layer
- judge decision parsing correctly classifies `accept`, `revise`, `rework`, and `unknown` outcomes
- judge reason excerpt extraction prefers `Reason:` field, falls back to first non-decision line
- filesystem evidence builder reports changed markdown files with front-matter, source, and excerpt metadata
- filesystem evidence builder prioritises index-section content for index files
- peer verifier checks file-backed claims, staged artefact shape, and repairable final-text drift

### Web app layer
- `/api/run/start` returns correct job id and decision metadata
- `_run_job` wraps session history into chat input and saves history on completion
- `_evict_old_jobs` removes oldest completed/failed entries when the count exceeds the limit
- running jobs are never evicted

### Prompt layer
- prompt builders still assemble the expected runtime sections
- final-stage prompt assembly keeps the required handoff framing
- prompt-builder drift is reduced by keeping role policy in markdown prompts

### Document and vision layer
- document export server tests cover Markdown-to-native document tool behaviour
- diagram server tests cover Mermaid diagram tool behaviour
- PowerPoint extraction exposes slide text, tables, notes, and extraction limitations
- PowerPoint image extraction returns picture blobs in slide order
- vision server tools enforce workspace-bounded paths and supported image types
- vision server tests monkeypatch provider calls, so the suite remains network-free
- SharePoint helper tests cover item normalisation, browser opening, site filtering, and mocked server behaviour
- intranet tests cover provider-neutral behaviour and server tool handling

### Transcript and display layer
- peer transcript assembly keeps the expected speaker sequence
- display utilities continue to summarise and render output predictably

---

## 4. Running the full suite

From the repo root:

```bash
uv sync --extra litellm --group dev
uv run pytest
```

Use both `--extra litellm` and `--group dev` for local development. The dev
group installs test/static-analysis tooling; the LiteLLM extra installs the
provider bridge required by the default multi-provider registry.

That is the preferred command for checking the full current project state.
The default pytest configuration includes `--cov=crisai --cov-report=term-missing` and requires total coverage of at least 70%. CI runs the same suite with `pytest-timeout` enabled so hung async or web tests fail within the configured per-test timeout.

The CI workflow also runs the UI workspace checks:

```bash
npm --prefix ui ci
npm --prefix ui run typecheck
npm --prefix ui run build:web
npm --prefix ui run build:gem
```

CI includes a separate security scanning job. Run the same Python checks
locally from the repo root with:

```bash
uv run bandit -r src/crisai -c pyproject.toml --severity-level medium
uv export --locked --extra litellm --group dev --no-emit-project --no-header --output-file /tmp/crisai-requirements.txt >/dev/null
uv run pip-audit \
  --requirement /tmp/crisai-requirements.txt \
  --strict \
  --progress-spinner off \
  --ignore-vuln CVE-2026-35029 \
  --ignore-vuln CVE-2026-35030 \
  --ignore-vuln GHSA-69x8-hrgq-fjj8 \
  --ignore-vuln CVE-2026-42271
```

Secret scanning runs in CI through Gitleaks using `.gitleaks.toml`. To mirror
that locally, install the Gitleaks CLI and run:

```bash
gitleaks detect --source . --config .gitleaks.toml --redact --verbose
```

The pip-audit ignores are limited to current LiteLLM advisories whose fixed
versions require the OpenAI 2.x SDK line. Remove those ignores when crisAI and
the agents SDK can move from OpenAI 1.x to 2.x-compatible LiteLLM releases.

For a clean-install smoke check, also verify the supported launch modes:

```bash
./start api
./start gem
./start web
```

---

## 5. Running focused groups

### Unit tests only

```bash
uv run pytest tests/unit
```

### CLI-focused tests

```bash
uv run pytest tests/cli
```

Stage observability, token usage, and registry-backed cost telemetry are covered
by focused runtime tests:

```bash
uv run pytest tests/unit/test_usage_cost.py tests/unit/test_pipeline_engine.py tests/cli/test_pipelines.py tests/unit/test_registry_validation.py
```

### Orchestration sequencing tests

```bash
uv run pytest tests/orchestration
```

### Integration tests

```bash
uv run pytest tests/integration
```

### Smoke tests

Smoke tests are opt-in because they can call real provider APIs. They also
include a provider endpoint reachability check that opens a short TCP connection
to each configured API host without sending credentials or prompts. Export
`CRISAI_RUN_SMOKE_TESTS=1` and the provider keys in the current shell before
running them; if your keys are only in `.env`, source it first with
`set -a; . ./.env; set +a`. Tests for providers without a key skip
automatically:

```bash
uv run pytest tests/smoke
```

### Selected files

```bash
uv run pytest tests/unit/test_model_resolver.py
uv run pytest tests/unit/test_chat_context.py
uv run pytest tests/cli/test_pipelines.py
uv run pytest tests/orchestration/test_peer_mode.py
```

---

## 6. Notes on test design

- The suite is intentionally network-free.
- It does not call real OpenAI, Gemini, Anthropic, DeepSeek, or real MCP servers.
- `tests/smoke/` is the exception: it is opt-in and may reach provider API hosts.
- It relies on monkeypatching and lightweight fakes so orchestration and configuration behaviour can be checked deterministically.
- Optional provider integrations should not break test collection when those runtime extras are not installed.
- `tests/conftest.py` helps ensure `src/` is importable during local test runs.

---

## 7. Environment and dependency notes

### Base test environment
For the core suite, the project should import and run without requiring live provider credentials.

Install test and static-analysis tooling with the dev extra:

```bash
uv sync --extra litellm --group dev
```

The base uv install keeps runtime dependencies only; `pytest`, `pytest-timeout`,
`ruff`, and `mypy` live in the dev dependency group. The default registry also
needs the LiteLLM extra, so use both flags together for development installs.
`traced` remains a runtime dependency.

### Microsoft Graph auth smoke test (manual)
`tests/orchestration/test_graph_login.py` is a manual smoke test and is intentionally skipped by pytest.

Run it directly when you want to validate interactive Microsoft Entra login and Graph reachability:

```bash
uv run python tests/orchestration/test_graph_login.py
```

WSL note:
- the script uses WSL-aware browser launch (`wslview` or `explorer.exe` fallback) for interactive Microsoft Entra login
- if no browser opens, install `wslu` (`wslview`) or verify Windows browser integration

### Optional provider support
If you want to exercise OpenAI, Gemini, Anthropic, or DeepSeek in real runtime flows, you need the relevant optional runtime dependencies and environment variables configured in `.env`.

### Onboarding and doctor checks
After changing `.env.example` or doctor environment validation, run:

```bash
uv run pytest tests/unit/test_registry_validation.py -q
uv run crisai doctor
```

The unit suite checks that `.env.example` covers doctor-validated first-run
operator variables and that invalid environment overrides produce actionable
doctor warnings.

### Good practice
Run the suite after each improvement:

```bash
uv run pytest
```

This is especially important after changes to:
- CLI module boundaries
- workflow runtime plumbing
- registry schemas
- provider/model resolution
- prompt builders
- routing logic

---

## 8. Troubleshooting failures

### If model-related tests fail
Check:
- `registry/models.yaml`
- `registry/agents.yaml`
- `src/crisai/model_resolver.py`
- `src/crisai/agents/factory.py`

### If orchestration tests fail
Check:
- `src/crisai/cli/pipelines.py`
- `src/crisai/cli/workflow_support.py`
- `src/crisai/orchestration/peer_judge.py`
- `src/crisai/orchestration/peer_evidence.py`
- compatibility with existing monkeypatch seams (judge and evidence helpers are patched via their own modules, not via `pipelines`)

### If CLI tests fail
Check:
- `src/crisai/cli/main.py`
- `src/crisai/cli/status_views.py`
- `src/crisai/cli/session_store.py`

The suite is there to make incremental refactoring safer, so a failing test is usually a useful signal that a compatibility seam or behaviour contract has shifted.
