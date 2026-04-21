from __future__ import annotations

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
    spec = AgentSpec(id='discovery', name='Discovery', prompt_file='prompts/x.md', allowed_servers=[], model_ref='openai_fast')
    factory.build_agent(spec, mcp_servers=[])

    assert captured['model'] == 'gpt-5.4-mini'
    assert captured['name'] == 'Discovery'
