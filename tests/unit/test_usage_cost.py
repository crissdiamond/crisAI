from __future__ import annotations

from decimal import Decimal

import pytest

from crisai.orchestration.usage_cost import (
    ModelPricing,
    model_observability_metadata,
    usage_cost_metadata,
)


def test_model_pricing_parses_registry_mapping() -> None:
    pricing = ModelPricing.from_mapping(
        {
            "currency": "USD",
            "unit": "per_1m_tokens",
            "input": "1.25",
            "output": 2.5,
            "cached_input": "0.125",
            "reasoning": "3.0",
        }
    )

    assert pricing is not None
    assert pricing.currency == "USD"
    assert pricing.unit == "per_1m_tokens"
    assert pricing.input == Decimal("1.25")
    assert pricing.output == Decimal("2.5")
    assert pricing.cached_input == Decimal("0.125")
    assert pricing.reasoning == Decimal("3.0")


@pytest.mark.parametrize(
    "pricing",
    [
        {"currency": "EUR", "unit": "per_1m_tokens", "input": 1, "output": 1},
        {"currency": "USD", "unit": "per_token", "input": 1, "output": 1},
        {"currency": "USD", "unit": "per_1m_tokens", "input": -1, "output": 1},
        {"currency": "USD", "unit": "per_1m_tokens", "input": 1, "output": "not-a-number"},
    ],
)
def test_model_pricing_rejects_invalid_registry_mapping(pricing: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ModelPricing.from_mapping(pricing)


def test_usage_cost_metadata_estimates_cost_from_usage_and_pricing() -> None:
    pricing = ModelPricing.from_mapping(
        {
            "currency": "USD",
            "unit": "per_1m_tokens",
            "input": "10",
            "output": "20",
            "cached_input": "1",
            "reasoning": "30",
        }
    )

    cost = usage_cost_metadata(
        {
            "input_tokens": 1_000,
            "output_tokens": 500,
            "cached_tokens": 100,
            "reasoning_tokens": 50,
        },
        pricing,
        pricing_source="model_ref:test_model",
    )

    assert cost == {
        "schema_version": "usage_cost_v1",
        "currency": "USD",
        "estimated": True,
        "pricing_source": "model_ref:test_model",
        "pricing_unit": "per_1m_tokens",
        "input_cost_usd": 0.009,
        "output_cost_usd": 0.01,
        "cached_input_cost_usd": 0.0001,
        "reasoning_cost_usd": 0.0015,
        "total_cost_usd": 0.0206,
    }


def test_usage_cost_metadata_omits_when_usage_or_pricing_absent() -> None:
    pricing = ModelPricing.from_mapping(
        {"currency": "USD", "unit": "per_1m_tokens", "input": "1", "output": "1"}
    )

    assert usage_cost_metadata(None, pricing, pricing_source="model_ref:x") is None
    assert usage_cost_metadata({"total_tokens": 10}, None, pricing_source="model_ref:x") is None
    assert usage_cost_metadata({}, pricing, pricing_source="model_ref:x") is None


def test_model_observability_metadata_is_trace_safe() -> None:
    assert model_observability_metadata(
        provider="openai",
        model_name="gpt-example",
        source="model_ref:openai_fast",
    ) == {
        "schema_version": "model_observability_v1",
        "provider": "openai",
        "model_name": "gpt-example",
        "source": "model_ref:openai_fast",
        "model_ref": "openai_fast",
    }
