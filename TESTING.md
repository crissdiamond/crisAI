# crisAI Testing

> **Guide to the current test suite, how to run it, and what it protects.**

The crisAI test suite now covers more than the initial orchestration starter pack. It includes unit tests for the split CLI modules, workflow helpers, prompt builders, provider-aware model resolution, routing logic, and orchestration sequencing.

---

## 1. What the suite protects

The suite provides confidence around:

- agent factory behaviour
- provider-aware model resolution
- registry loading for agents and models
- heuristic routing
- pipeline mode sequencing
- peer mode sequencing and transcript handling
- command parsing and chat controller behaviour
- CLI state rendering helpers
- session persistence
- prompt builder assembly
- import smoke tests for main orchestration modules

---

## 2. Current test layout

```text
tests/
  conftest.py

  cli/
    test_main_imports.py
    test_pipelines.py
    test_workflow_support.py

  orchestration/
    test_pipeline_mode.py
    test_peer_mode.py

  unit/
    test_agent_factory.py
    test_agent_factory_provider.py
    test_chat_context.py
    test_chat_controller.py
    test_chat_pin_state.py
    test_cli_commands.py
    test_display.py
    test_main_review_routing.py
    test_model_resolver.py
    test_output_stability.py
    test_peer_transcript.py
    test_prompt_builders.py
    test_registry_models.py
    test_router.py
    test_router_publisher.py
    test_session_store.py
    test_status_views.py
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
- retrieval-only prompts still route to discovery
- mixed retrieval + drafting prompts still route to pipeline
- review prompts still route to review
- operations/debug prompts still route to operations
- publisher-oriented requests still route appropriately

### Workflow execution layer
- `run_single(...)` continues to honour the selected agent
- `run_pipeline(...)` keeps the expected stage order
- `run_peer_pipeline(...)` keeps the expected stage order
- workflow helper functions keep shared runtime behaviour stable

### Prompt layer
- prompt builders still assemble the expected runtime sections
- final-stage prompt assembly keeps the required handoff framing
- prompt-builder drift is reduced by keeping role policy in markdown prompts

### Transcript and display layer
- peer transcript assembly keeps the expected speaker sequence
- display utilities continue to summarise and render output predictably

---

## 4. Running the full suite

From the repo root:

```bash
pytest
```

That is the preferred command for checking the full current project state.

For a clean-install smoke check, also verify both launch modes:

```bash
./start cli
./start web
```

---

## 5. Running focused groups

### Unit tests only

```bash
pytest tests/unit
```

### CLI-focused tests

```bash
pytest tests/cli
```

### Orchestration sequencing tests

```bash
pytest tests/orchestration
```

### Selected files

```bash
pytest tests/unit/test_model_resolver.py
pytest tests/unit/test_chat_controller.py
pytest tests/cli/test_pipelines.py
pytest tests/orchestration/test_peer_mode.py
```

---

## 6. Notes on test design

- The suite is intentionally network-free.
- It does not call real OpenAI, Gemini, Anthropic, or real MCP servers.
- It relies on monkeypatching and lightweight fakes so orchestration and configuration behaviour can be checked deterministically.
- Optional provider integrations should not break test collection when those runtime extras are not installed.
- `tests/conftest.py` helps ensure `src/` is importable during local test runs.

---

## 7. Environment and dependency notes

### Base test environment
For the core suite, the project should import and run without requiring live provider credentials.

### Optional provider support
If you want to exercise Gemini or Anthropic in real runtime flows, you need the relevant optional runtime dependencies and environment variables configured in `.env`.

### Good practice
Run the suite after each improvement:

```bash
pytest
```

This is especially important after changes to:
- CLI module boundaries
- workflow runtime plumbing
- registry schemas
- provider/model resolution
- prompt builders
- routing logic

---

## 8. Suggested next additions

Useful future additions would be:

- a small integration test for loading `registry/models.yaml` through the full CLI runtime path
- tests for `/list agents` showing `model_ref` or model display labels clearly
- SharePoint auth status tests with a mocked MSAL layer
- tests for `.env.example` coverage and configuration completeness
- optional smoke tests for provider selection when Gemini or Anthropic are configured

---

## 9. Troubleshooting failures

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
- compatibility with existing monkeypatch seams

### If CLI tests fail
Check:
- `src/crisai/cli/main.py`
- `src/crisai/cli/chat_controller.py`
- `src/crisai/cli/status_views.py`
- `src/crisai/cli/session_store.py`

The suite is there to make incremental refactoring safer, so a failing test is usually a useful signal that a compatibility seam or behaviour contract has shifted.
