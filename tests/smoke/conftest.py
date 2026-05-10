"""Smoke test fixtures.

Smoke tests call real LLM APIs and are opt-in:

    CRISAI_RUN_SMOKE_TESTS=1 python -m pytest tests/smoke/ -v

Individual provider tests additionally require the relevant API key env vars:

    OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY

Tests skip automatically when the guard env var or required keys are absent.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from crisai.registry import Registry

_ROOT = Path(__file__).resolve().parents[2]
_ENABLE_ENV = "CRISAI_RUN_SMOKE_TESTS"

# Cheapest configured model ref per provider (for single-mode provider tests).
CHEAP_MODEL_REF: dict[str, str] = {
    "openai": "openai_nano",
    "gemini": "gemini_fast",
    "anthropic": "anthropic_fast",
    "deepseek": "deepseek_fast",
}

# API key env var per provider.
PROVIDER_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}


def require_smoke() -> None:
    """Skip unless CRISAI_RUN_SMOKE_TESTS=1."""
    if not os.environ.get(_ENABLE_ENV):
        pytest.skip(f"Set {_ENABLE_ENV}=1 to run smoke tests")


def require_providers(*providers: str) -> None:
    """Skip if smoke tests are disabled or any listed provider lacks an API key."""
    require_smoke()
    missing = [p for p in providers if not os.environ.get(PROVIDER_KEY_ENV[p])]
    if missing:
        keys = ", ".join(PROVIDER_KEY_ENV[p] for p in missing)
        pytest.skip(f"Missing API key(s): {keys}")


@pytest.fixture
def smoke_settings(tmp_path: Path) -> SimpleNamespace:
    """Settings wired to real API keys from the environment."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return SimpleNamespace(
        # openai_api_key must be non-empty to pass ensure_openai_api_key guard.
        # A placeholder is acceptable for tests that use only non-OpenAI agents.
        openai_api_key=os.environ.get("OPENAI_API_KEY", "smoke-placeholder"),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        log_dir=log_dir,
        registry_dir=str(_ROOT / "registry"),
        root_dir=str(_ROOT),
    )


@pytest.fixture
def smoke_registry() -> dict:
    """Real agent and model specs from disk; no MCP server specs.

    Server specs are intentionally empty so agents run without tools.
    The pipelines skip missing servers rather than raising.
    """
    registry = Registry(_ROOT / "registry")
    return {
        "server_specs": {},
        "agent_specs": {a.id: a for a in registry.load_agents()},
        "model_specs": registry.load_models(),
    }


def read_trace(log_dir: Path) -> list[dict]:
    """Parse agent_trace.jsonl lines from log_dir into a list of dicts."""
    trace_file = log_dir / "agent_trace.jsonl"
    if not trace_file.exists():
        return []
    return [
        json.loads(line)
        for line in trace_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def assert_stage_traced(trace: list[dict], stage: str) -> None:
    """Assert a non-empty stage_output trace entry exists for the given stage."""
    outputs = [
        e for e in trace
        if e.get("stage") == stage and e.get("event_type") == "stage_output"
    ]
    assert outputs, f"No stage_output trace entry found for stage '{stage}'"
    assert any(
        e.get("content", "").strip() for e in outputs
    ), f"Stage '{stage}' produced empty content in trace"
