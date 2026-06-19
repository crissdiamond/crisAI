from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

from crisai.agents.factory import AgentFactory
from crisai.registry import AgentSpec, ModelSpec


def test_build_agent_uses_resolved_runtime_model(tmp_path: Path, monkeypatch):
    prompt_path = tmp_path / 'prompts' / 'x.md'
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text('hello', encoding='utf-8')

    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr('crisai.agents.factory.Agent', FakeAgent)
    monkeypatch.setenv('OPENAI_API_KEY', 'x')

    factory = AgentFactory(
        tmp_path,
        model_specs=[ModelSpec(id='openai_fast', provider='openai', model_name='gpt-5.4-mini', api_key_env='OPENAI_API_KEY')],
    )
    spec = AgentSpec(id='retrieval_planner', name='Retrieval Planner', prompt_file='prompts/x.md', allowed_servers=[], model_ref='openai_fast')
    factory.build_agent(spec, mcp_servers=[])

    assert captured['model'] == 'gpt-5.4-mini'
    assert captured['name'] == 'Retrieval Planner'


def test_openai_without_base_url_uses_default_string_model(tmp_path: Path, monkeypatch):
    prompt_path = tmp_path / 'prompts' / 'x.md'
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text('hello', encoding='utf-8')

    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    def fail_client(*args, **kwargs):
        raise AssertionError("AsyncOpenAI should not be constructed without a base_url")

    monkeypatch.setattr('crisai.agents.factory.Agent', FakeAgent)
    monkeypatch.setattr('crisai.agents.factory.AsyncOpenAI', fail_client)
    monkeypatch.setenv('OPENAI_API_KEY', 'x')

    factory = AgentFactory(
        tmp_path,
        model_specs=[ModelSpec(id='openai_fast', provider='openai', model_name='gpt-5.4-mini', api_key_env='OPENAI_API_KEY')],
    )
    spec = AgentSpec(id='retrieval_planner', name='Retrieval Planner', prompt_file='prompts/x.md', allowed_servers=[], model_ref='openai_fast')
    factory.build_agent(spec, mcp_servers=[])

    assert captured['model'] == 'gpt-5.4-mini'


def test_openai_with_base_url_builds_configured_client_model(tmp_path: Path, monkeypatch):
    prompt_path = tmp_path / 'prompts' / 'x.md'
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text('hello', encoding='utf-8')

    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeAsyncOpenAI:
        def __init__(self, api_key=None, base_url=None):
            self.api_key = api_key
            self.base_url = base_url

    class FakeResponsesModel:
        def __init__(self, model, openai_client):
            self.model = model
            self.openai_client = openai_client

    monkeypatch.setattr('crisai.agents.factory.Agent', FakeAgent)
    monkeypatch.setattr('crisai.agents.factory.AsyncOpenAI', FakeAsyncOpenAI)
    monkeypatch.setattr('crisai.agents.factory.OpenAIResponsesModel', FakeResponsesModel)
    monkeypatch.setenv('OPENAI_API_KEY', 'sekret')

    factory = AgentFactory(
        tmp_path,
        model_specs=[
            ModelSpec(
                id='openai_gateway',
                provider='openai',
                model_name='gpt-5.4-mini',
                api_key_env='OPENAI_API_KEY',
                base_url='https://gateway.example.com/v1',
            )
        ],
    )
    spec = AgentSpec(id='retrieval_planner', name='Retrieval Planner', prompt_file='prompts/x.md', allowed_servers=[], model_ref='openai_gateway')
    factory.build_agent(spec, mcp_servers=[])

    model = captured['model']
    assert isinstance(model, FakeResponsesModel)
    assert model.model == 'gpt-5.4-mini'
    assert model.openai_client.base_url == 'https://gateway.example.com/v1'
    assert model.openai_client.api_key == 'sekret'


def test_build_litellm_model_ignores_unsupported_registry_extras(tmp_path: Path, monkeypatch, caplog):
    prompt_path = tmp_path / 'prompts' / 'x.md'
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text('hello', encoding='utf-8')

    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeLitellmModel:
        def __init__(self, model, api_key=None, base_url=None, should_replay_reasoning_content=None):
            self.model = model
            self.api_key = api_key
            self.base_url = base_url
            self.should_replay_reasoning_content = should_replay_reasoning_content

    monkeypatch.setattr('crisai.agents.factory.Agent', FakeAgent)
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'x')
    monkeypatch.setitem(
        __import__('sys').modules,
        'agents.extensions.models.litellm_model',
        SimpleNamespace(LitellmModel=FakeLitellmModel),
    )

    with caplog.at_level(logging.DEBUG, logger='crisai.agents.factory'):
        factory = AgentFactory(
            tmp_path,
            model_specs=[
                ModelSpec(
                    id='deepseek_reasoner',
                    provider='deepseek',
                    model_name='deepseek/deepseek-v4-flash',
                    api_key_env='DEEPSEEK_API_KEY',
                    extra={
                        'thinking': {'type': 'enabled'},
                        'reasoning_effort': 'max',
                        'should_replay_reasoning_content': 'always',
                    },
                )
            ],
        )
        spec = AgentSpec(id='custom_agent', name='Custom Agent', prompt_file='prompts/x.md', allowed_servers=[], model_ref='deepseek_reasoner')
        factory.build_agent(spec, mcp_servers=[])

    model = captured['model']
    assert model.model == 'deepseek/deepseek-v4-flash'
    assert model.api_key == 'x'
    assert model.should_replay_reasoning_content == 'always'
    assert captured['model_settings'].extra_body == {'thinking': {'type': 'enabled'}}
    assert captured['model_settings'].reasoning.effort == 'high'
    assert captured['model_settings'].extra_args == {
        'allowed_openai_params': ['thinking', 'reasoning_effort'],
    }
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert "Ignoring unsupported LiteLLM model registry option(s)" not in caplog.text


def test_build_local_model_uses_litellm_with_base_url_and_placeholder_key(tmp_path: Path, monkeypatch):
    prompt_path = tmp_path / 'prompts' / 'x.md'
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text('hello', encoding='utf-8')

    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeLitellmModel:
        def __init__(self, model, api_key=None, base_url=None):
            self.model = model
            self.api_key = api_key
            self.base_url = base_url

    monkeypatch.setattr('crisai.agents.factory.Agent', FakeAgent)
    monkeypatch.delenv('QWEN_API_KEY', raising=False)
    monkeypatch.setitem(
        __import__('sys').modules,
        'agents.extensions.models.litellm_model',
        SimpleNamespace(LitellmModel=FakeLitellmModel),
    )

    factory = AgentFactory(
        tmp_path,
        model_specs=[
            ModelSpec(
                id='qwen_local',
                provider='local',
                model_name='openai/qwen3',
                base_url='http://localhost:11434/v1',
            )
        ],
    )
    spec = AgentSpec(id='operations', name='Operations', prompt_file='prompts/x.md', allowed_servers=[], model_ref='qwen_local')
    factory.build_agent(spec, mcp_servers=[])

    model = captured['model']
    assert model.model == 'openai/qwen3'
    assert model.base_url == 'http://localhost:11434/v1'
    # Local servers need no real key, but the client still requires a value.
    assert model.api_key == 'local'


def test_deepseek_thinking_disabled_for_any_tool_enabled_agent_without_reasoning_replay(tmp_path: Path, monkeypatch):
    prompt_path = tmp_path / 'prompts' / 'x.md'
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text('hello', encoding='utf-8')

    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeLitellmModel:
        def __init__(self, model, api_key=None, base_url=None):
            self.model = model
            self.api_key = api_key
            self.base_url = base_url

    monkeypatch.setattr('crisai.agents.factory.Agent', FakeAgent)
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'x')
    monkeypatch.setitem(
        __import__('sys').modules,
        'agents.extensions.models.litellm_model',
        SimpleNamespace(LitellmModel=FakeLitellmModel),
    )

    factory = AgentFactory(
        tmp_path,
        model_specs=[
            ModelSpec(
                id='deepseek_reasoner',
                provider='deepseek',
                model_name='deepseek/deepseek-v4-flash',
                api_key_env='DEEPSEEK_API_KEY',
                extra={
                    'thinking': {'type': 'enabled'},
                    'reasoning_effort': 'max',
                },
            )
        ],
    )
    spec = AgentSpec(id='custom_tool_agent', name='Custom Tool Agent', prompt_file='prompts/x.md', allowed_servers=[], model_ref='deepseek_reasoner')
    factory.build_agent(spec, mcp_servers=[object()])

    settings = captured['model_settings']
    assert settings.extra_body == {'thinking': {'type': 'disabled'}}
    assert settings.reasoning is None
    assert settings.extra_args == {'allowed_openai_params': ['thinking']}


def test_deepseek_thinking_kept_for_any_tool_enabled_agent_when_reasoning_replay_supported(tmp_path: Path, monkeypatch):
    prompt_path = tmp_path / 'prompts' / 'x.md'
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text('hello', encoding='utf-8')

    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeLitellmModel:
        def __init__(self, model, api_key=None, base_url=None, should_replay_reasoning_content=None):
            self.model = model
            self.api_key = api_key
            self.base_url = base_url
            self.should_replay_reasoning_content = should_replay_reasoning_content

    monkeypatch.setattr('crisai.agents.factory.Agent', FakeAgent)
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'x')
    monkeypatch.setitem(
        __import__('sys').modules,
        'agents.extensions.models.litellm_model',
        SimpleNamespace(LitellmModel=FakeLitellmModel),
    )

    factory = AgentFactory(
        tmp_path,
        model_specs=[
            ModelSpec(
                id='deepseek_reasoner',
                provider='deepseek',
                model_name='deepseek/deepseek-v4-flash',
                api_key_env='DEEPSEEK_API_KEY',
                extra={
                    'thinking': {'type': 'enabled'},
                    'reasoning_effort': 'max',
                },
            )
        ],
    )
    spec = AgentSpec(id='custom_tool_agent', name='Custom Tool Agent', prompt_file='prompts/x.md', allowed_servers=[], model_ref='deepseek_reasoner')
    factory.build_agent(spec, mcp_servers=[object()])

    model = captured['model']
    settings = captured['model_settings']
    assert model.should_replay_reasoning_content == 'always'
    assert settings.extra_body == {'thinking': {'type': 'enabled'}}
    assert settings.reasoning.effort == 'high'
