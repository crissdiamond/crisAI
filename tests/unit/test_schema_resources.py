from __future__ import annotations

import json

from crisai.cli.prompt_contracts import EVIDENCE_BUNDLE_CONTRACT
from crisai.schemas import load_schema_text


def test_schema_resources_are_valid_json() -> None:
    for name in (
        "evidence_bundle_v1.schema.json",
        "task_contract_v1.schema.json",
        "request_contract_v1.schema.json",
        "deterministic_context_v1.schema.json",
        "peer_run_contract.schema.json",
        "ui_event_v1.schema.json",
        "ui_run_request_v1.schema.json",
        "ui_run_state_v1.schema.json",
        "ui_theme_v1.schema.json",
    ):
        payload = json.loads(load_schema_text(name))
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_prompt_contracts_load_from_schema_resources() -> None:
    assert EVIDENCE_BUNDLE_CONTRACT == load_schema_text("evidence_bundle_v1.prompt.md").strip()
    assert "schema_version: \"evidence_bundle_v1\"" in EVIDENCE_BUNDLE_CONTRACT
