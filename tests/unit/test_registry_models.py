from __future__ import annotations

from pathlib import Path

from crisai.registry import Registry


def test_load_models(tmp_path: Path):
    registry_dir = tmp_path
    (registry_dir / 'models.yaml').write_text(
        'version: 1\nmodels:\n  - id: openai_fast\n    provider: openai\n    model_name: gpt-5.4-mini\n',
        encoding='utf-8',
    )
    registry = Registry(registry_dir)
    models = registry.load_models()
    assert len(models) == 1
    assert models[0].id == 'openai_fast'
    assert models[0].provider == 'openai'


def test_load_agents_with_model_ref(tmp_path: Path):
    registry_dir = tmp_path
    (registry_dir / 'agents.yaml').write_text(
        'version: 1\nagents:\n  - id: discovery\n    name: Discovery\n    model_ref: openai_fast\n    prompt_file: prompts/discovery.md\n    allowed_servers: []\n',
        encoding='utf-8',
    )
    registry = Registry(registry_dir)
    agents = registry.load_agents()
    assert agents[0].model_ref == 'openai_fast'
    assert agents[0].display_model == 'openai_fast'
