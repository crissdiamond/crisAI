from __future__ import annotations

import os

import pytest

from crisai.model_resolver import ModelResolver
from crisai.registry import AgentSpec, ModelSpec


@pytest.fixture
def model_specs() -> list[ModelSpec]:
    return [
        ModelSpec(id="openai_fast", provider="openai", model_name="gpt-5.4-mini", api_key_env="OPENAI_API_KEY"),
        ModelSpec(id="gemini_strong", provider="gemini", model_name="gemini/gemini-2.5-pro", api_key_env="GEMINI_API_KEY"),
        ModelSpec(id="anthropic_reasoning", provider="anthropic", model_name="anthropic/claude-sonnet-4-5", api_key_env="ANTHROPIC_API_KEY"),
    ]


def test_resolve_openai_model_ref(model_specs, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    resolver = ModelResolver(model_specs)
    agent = AgentSpec(id="retrieval_planner", name="Retrieval Planner", prompt_file="p.md", allowed_servers=[], model_ref="openai_fast")
    resolved = resolver.resolve_for_agent(agent)
    assert resolved.provider == "openai"
    assert resolved.runtime_model == "gpt-5.4-mini"


def test_resolve_gemini_model_ref(model_specs, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    resolver = ModelResolver(model_specs)
    agent = AgentSpec(id="judge", name="Judge", prompt_file="p.md", allowed_servers=[], model_ref="gemini_strong")
    resolved = resolver.resolve_for_agent(agent)
    assert resolved.provider == "gemini"
    assert resolved.model_name == "gemini/gemini-2.5-pro"


def test_resolve_anthropic_model_ref(model_specs, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    resolver = ModelResolver(model_specs)
    agent = AgentSpec(id="challenger", name="Challenger", prompt_file="p.md", allowed_servers=[], model_ref="anthropic_reasoning")
    resolved = resolver.resolve_for_agent(agent)
    assert resolved.provider == "anthropic"
    assert resolved.model_name == "anthropic/claude-sonnet-4-5"


def test_unknown_model_ref_raises(model_specs):
    resolver = ModelResolver(model_specs)
    agent = AgentSpec(id="x", name="X", prompt_file="p.md", allowed_servers=[], model_ref="missing")
    with pytest.raises(ValueError, match="Unknown model_ref"):
        resolver.resolve_for_agent(agent)


def test_missing_api_key_raises(model_specs, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    resolver = ModelResolver(model_specs)
    agent = AgentSpec(id="judge", name="Judge", prompt_file="p.md", allowed_servers=[], model_ref="gemini_strong")
    with pytest.raises(ValueError, match="Missing required API key"):
        resolver.resolve_for_agent(agent)


def test_legacy_model_fallback(model_specs):
    resolver = ModelResolver(model_specs)
    agent = AgentSpec(id="legacy", name="Legacy", prompt_file="p.md", allowed_servers=[], model="gpt-5.4-mini")
    resolved = resolver.resolve_for_agent(agent)
    assert resolved.source == "legacy:model"
    assert resolved.runtime_model == "gpt-5.4-mini"
