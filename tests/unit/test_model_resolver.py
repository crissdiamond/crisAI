from __future__ import annotations

import pytest

from crisai.model_resolver import ModelResolver
from crisai.registry import AgentSpec, ModelSpec


@pytest.fixture
def model_specs() -> list[ModelSpec]:
    return [
        ModelSpec(id="openai_fast", provider="openai", model_name="gpt-5.4-mini", api_key_env="OPENAI_API_KEY"),
        ModelSpec(id="gemini_strong", provider="gemini", model_name="gemini/gemini-2.5-pro", api_key_env="GEMINI_API_KEY"),
        ModelSpec(id="anthropic_reasoning", provider="anthropic", model_name="anthropic/claude-sonnet-4-5", api_key_env="ANTHROPIC_API_KEY"),
        ModelSpec(id="deepseek_fast", provider="deepseek", model_name="deepseek/deepseek-v4-flash", api_key_env="DEEPSEEK_API_KEY"),
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


def test_resolve_deepseek_model_ref(model_specs, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    resolver = ModelResolver(model_specs)
    agent = AgentSpec(id="design", name="Design", prompt_file="p.md", allowed_servers=[], model_ref="deepseek_fast")
    resolved = resolver.resolve_for_agent(agent)
    assert resolved.provider == "deepseek"
    assert resolved.model_name == "deepseek/deepseek-v4-flash"
    assert resolved.api_key == "x"


def test_resolve_openai_with_base_url_defers_to_factory(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    resolver = ModelResolver(
        [
            ModelSpec(
                id="openai_gateway",
                provider="openai",
                model_name="gpt-5.4-mini",
                api_key_env="OPENAI_API_KEY",
                base_url="https://gateway.example.com/v1",
            )
        ]
    )
    agent = AgentSpec(id="design", name="Design", prompt_file="p.md", allowed_servers=[], model_ref="openai_gateway")
    resolved = resolver.resolve_for_agent(agent)
    assert resolved.provider == "openai"
    # runtime_model stays None so the factory builds a client-bound model.
    assert resolved.runtime_model is None
    assert resolved.base_url == "https://gateway.example.com/v1"
    assert resolved.api_key == "k"


def test_resolve_local_model_ref_without_api_key(monkeypatch):
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    resolver = ModelResolver(
        [ModelSpec(id="qwen_local", provider="local", model_name="openai/qwen3", base_url="http://localhost:11434/v1")]
    )
    agent = AgentSpec(id="operations", name="Operations", prompt_file="p.md", allowed_servers=[], model_ref="qwen_local")
    resolved = resolver.resolve_for_agent(agent)
    assert resolved.provider == "local"
    assert resolved.model_name == "openai/qwen3"
    assert resolved.base_url == "http://localhost:11434/v1"
    assert resolved.api_key is None
    assert resolved.runtime_model is None


def test_resolve_local_model_ref_with_optional_api_key(monkeypatch):
    monkeypatch.setenv("QWEN_API_KEY", "secret")
    resolver = ModelResolver(
        [
            ModelSpec(
                id="qwen_local",
                provider="local",
                model_name="openai/qwen3",
                api_key_env="QWEN_API_KEY",
                base_url="http://localhost:11434/v1",
            )
        ]
    )
    agent = AgentSpec(id="operations", name="Operations", prompt_file="p.md", allowed_servers=[], model_ref="qwen_local")
    resolved = resolver.resolve_for_agent(agent)
    assert resolved.api_key == "secret"


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
