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
        spec = AgentSpec(id='summary', name='Summary', prompt_file='prompts/x.md', allowed_servers=[], model_ref='deepseek_reasoner')
        factory.build_agent(spec, mcp_servers=[])

    model = captured['model']
    assert model.model == 'deepseek/deepseek-v4-flash'
    assert model.api_key == 'x'
    assert model.should_replay_reasoning_content == 'always'
    assert captured['model_settings'].extra_body == {
        'thinking': {'type': 'enabled'},
        'reasoning_effort': 'max',
    }
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert "Ignoring unsupported LiteLLM model registry option(s)" not in caplog.text
