# crisAI test suite starter pack

This package adds a practical confidence layer around:

- agent factory behaviour
- heuristic routing
- pipeline mode sequencing
- peer mode sequencing and transcript handling
- import smoke tests for the main orchestration modules

## Included tests

```text
tests/
  conftest.py
  unit/
    test_agent_factory.py
    test_display.py
    test_peer_transcript.py
    test_router.py
  orchestration/
    test_pipeline_mode.py
    test_peer_mode.py
  cli/
    test_main_imports.py
```

## What these tests protect

- retrieval-only prompts keep routing to discovery
- mixed retrieval + drafting prompts keep routing to pipeline
- review prompts keep routing to review
- operations/debug prompts keep routing to operations
- `run_single(...)` continues to honour the selected agent
- `run_pipeline(...)` keeps the expected stage order
- `run_peer_pipeline(...)` keeps the expected stage order
- peer transcript assembly keeps the expected speaker sequence
- core CLI/orchestration modules still import cleanly

## Running the suite

From the repo root:

```bash
pytest tests/unit tests/orchestration tests/cli
```

Or run focused groups:

```bash
pytest tests/unit/test_router.py
pytest tests/orchestration/test_pipeline_mode.py
pytest tests/orchestration/test_peer_mode.py
pytest tests/cli/test_main_imports.py
```

## Notes

- The suite is intentionally network-free.
- It does not call real OpenAI or real MCP servers.
- The tests use monkeypatching and lightweight fakes so orchestration behaviour can be checked deterministically.
- `tests/conftest.py` adds `src/` to `sys.path` and provides minimal fallbacks if `openai-agents` is not installed in the test environment.

## Suggested next additions

Later, it would be worth adding:

- command parsing tests for `/mode`, `/agent`, `/review`
- text asset loader tests for all required CLI markdown files
- shallow CLI interaction tests for `/list servers` and `/list agents`
- SharePoint auth status tests with a mocked MSAL layer
