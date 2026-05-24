from __future__ import annotations

import json

from crisai.cli import main
from crisai.orchestration.usage_cost import USAGE_COST_SCHEMA_VERSION


def _cost_event(
    *,
    run_id: str = "run-abc123",
    stage: str = "design",
    agent_id: str = "design",
    provider: str = "openai",
    model_name: str = "gpt-4o",
    input_tokens: int = 1000,
    output_tokens: int = 500,
    total_cost_usd: float = 0.001500,
    timestamp: str = "2026-05-24T10:00:00+00:00",
) -> str:
    """Build a fixture JSONL trace line with cost observability."""
    return json.dumps(
        {
            "timestamp": timestamp,
            "event_type": "stage_output",
            "stage": stage,
            "agent_id": agent_id,
            "run_id": run_id,
            "content": "output",
            "metadata": {
                "observability": {
                    "schema_version": "ui_stage_observability_v1",
                    "provider_usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                    "model": {
                        "schema_version": "model_observability_v1",
                        "provider": provider,
                        "model_name": model_name,
                        "source": f"model_ref:{agent_id}",
                    },
                    "cost": {
                        "schema_version": USAGE_COST_SCHEMA_VERSION,
                        "currency": "USD",
                        "estimated": True,
                        "pricing_source": f"model_ref:{agent_id}",
                        "pricing_unit": "per_1m_tokens",
                        "input_cost_usd": round(total_cost_usd * 0.6, 8),
                        "output_cost_usd": round(total_cost_usd * 0.4, 8),
                        "total_cost_usd": total_cost_usd,
                    },
                }
            },
        }
    )


def _no_cost_event(run_id: str = "run-abc123") -> str:
    """Build a fixture JSONL trace line without cost observability."""
    return json.dumps(
        {
            "timestamp": "2026-05-24T10:00:00+00:00",
            "event_type": "stage_output",
            "stage": "retrieval",
            "run_id": run_id,
            "content": "retrieved",
        }
    )


def test_parse_spend_events_returns_cost_events():
    lines = [_cost_event(), _no_cost_event()]
    result, warnings = main._parse_spend_events(lines)
    assert "run-abc123" in result
    assert len(result["run-abc123"]) == 1
    assert not warnings


def test_parse_spend_events_skips_events_without_cost():
    lines = [_no_cost_event()]
    result, warnings = main._parse_spend_events(lines)
    assert not result
    assert not warnings


def test_parse_spend_events_warns_on_malformed_line():
    lines = ["{bad json", _cost_event()]
    result, warnings = main._parse_spend_events(lines)
    assert len(warnings) == 1
    assert "malformed" in warnings[0].lower()
    assert len(result) == 1


def test_parse_spend_events_groups_by_run_id():
    lines = [
        _cost_event(run_id="run-aaa", timestamp="2026-05-24T09:00:00+00:00"),
        _cost_event(run_id="run-bbb", timestamp="2026-05-24T10:00:00+00:00"),
    ]
    result, _ = main._parse_spend_events(lines, last=2)
    assert set(result.keys()) == {"run-aaa", "run-bbb"}


def test_parse_spend_events_last_returns_most_recent():
    lines = [
        _cost_event(run_id="run-old", timestamp="2026-05-24T08:00:00+00:00"),
        _cost_event(run_id="run-new", timestamp="2026-05-24T10:00:00+00:00"),
    ]
    result, _ = main._parse_spend_events(lines, last=1)
    assert list(result.keys()) == ["run-new"]


def test_parse_spend_events_run_filter_exact_match():
    lines = [_cost_event(run_id="run-aaa"), _cost_event(run_id="run-bbb")]
    result, _ = main._parse_spend_events(lines, run_filter="run-aaa")
    assert list(result.keys()) == ["run-aaa"]


def test_parse_spend_events_run_filter_prefix_match():
    lines = [_cost_event(run_id="run-abc123"), _cost_event(run_id="run-xyz999")]
    result, _ = main._parse_spend_events(lines, run_filter="run-abc")
    assert list(result.keys()) == ["run-abc123"]


def test_parse_spend_events_run_filter_no_match_returns_empty():
    lines = [_cost_event(run_id="run-abc123")]
    result, _ = main._parse_spend_events(lines, run_filter="run-zzz")
    assert not result


def test_parse_spend_events_skips_wrong_schema_version():
    event = json.loads(_cost_event())
    event["metadata"]["observability"]["cost"]["schema_version"] = "usage_cost_v0"
    lines = [json.dumps(event)]
    result, _ = main._parse_spend_events(lines)
    assert not result


def test_parse_spend_events_empty_input():
    result, warnings = main._parse_spend_events([])
    assert not result
    assert not warnings


def test_parse_spend_events_multiple_events_per_run():
    lines = [
        _cost_event(run_id="run-abc", stage="design", agent_id="design"),
        _cost_event(run_id="run-abc", stage="summary", agent_id="summary"),
    ]
    result, _ = main._parse_spend_events(lines, last=1)
    assert len(result["run-abc"]) == 2


def test_parse_spend_events_skips_blank_lines():
    lines = ["", "   ", _cost_event()]
    result, warnings = main._parse_spend_events(lines)
    assert len(result) == 1
    assert not warnings
