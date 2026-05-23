from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

USAGE_COST_SCHEMA_VERSION = "usage_cost_v1"
MODEL_OBSERVABILITY_SCHEMA_VERSION = "model_observability_v1"
PRICING_UNIT_PER_1M_TOKENS = "per_1m_tokens"
SUPPORTED_CURRENCIES = frozenset({"USD"})


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Registry-backed model pricing used for estimated cost telemetry."""

    currency: str
    unit: str
    input: Decimal
    output: Decimal
    cached_input: Decimal | None = None
    reasoning: Decimal | None = None

    @classmethod
    def from_mapping(cls, value: Any) -> ModelPricing | None:
        """Return pricing from a registry mapping, or ``None`` when absent."""
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("pricing must be a mapping")
        currency = str(value.get("currency") or "").strip().upper()
        unit = str(value.get("unit") or "").strip()
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError("pricing.currency must be USD")
        if unit != PRICING_UNIT_PER_1M_TOKENS:
            raise ValueError("pricing.unit must be per_1m_tokens")
        input_rate = _non_negative_decimal(value.get("input"), "pricing.input")
        output_rate = _non_negative_decimal(value.get("output"), "pricing.output")
        cached_input = _optional_non_negative_decimal(value.get("cached_input"), "pricing.cached_input")
        reasoning = _optional_non_negative_decimal(value.get("reasoning"), "pricing.reasoning")
        return cls(
            currency=currency,
            unit=unit,
            input=input_rate,
            output=output_rate,
            cached_input=cached_input,
            reasoning=reasoning,
        )

    def to_trace_dict(self) -> dict[str, object]:
        """Return a trace-safe pricing summary without provider credentials."""
        payload: dict[str, object] = {
            "currency": self.currency,
            "unit": self.unit,
            "input": _decimal_to_float(self.input),
            "output": _decimal_to_float(self.output),
        }
        if self.cached_input is not None:
            payload["cached_input"] = _decimal_to_float(self.cached_input)
        if self.reasoning is not None:
            payload["reasoning"] = _decimal_to_float(self.reasoning)
        return payload


def model_observability_metadata(*, provider: str, model_name: str, source: str) -> dict[str, object]:
    """Return trace-safe model identity metadata."""
    metadata: dict[str, object] = {
        "schema_version": MODEL_OBSERVABILITY_SCHEMA_VERSION,
        "provider": provider,
        "model_name": model_name,
        "source": source,
    }
    if source.startswith("model_ref:"):
        metadata["model_ref"] = source.split(":", 1)[1]
    return metadata


def usage_cost_metadata(
    provider_usage: dict[str, Any] | None,
    pricing: ModelPricing | None,
    *,
    pricing_source: str,
) -> dict[str, object] | None:
    """Estimate cost from provider usage and registry-backed pricing.

    Returns ``None`` when either side of the calculation is unavailable so
    callers can omit cost metadata gracefully instead of guessing.
    """
    if not provider_usage or pricing is None:
        return None

    input_tokens = _non_negative_int(provider_usage.get("input_tokens"))
    output_tokens = _non_negative_int(provider_usage.get("output_tokens"))
    cached_tokens = _non_negative_int(provider_usage.get("cached_tokens"))
    reasoning_tokens = _non_negative_int(provider_usage.get("reasoning_tokens"))
    if input_tokens == output_tokens == cached_tokens == reasoning_tokens == 0:
        return None

    billed_cached_tokens = min(cached_tokens, input_tokens)
    billed_input_tokens = input_tokens
    if pricing.cached_input is not None:
        billed_input_tokens = max(0, input_tokens - billed_cached_tokens)

    input_cost = _token_cost(billed_input_tokens, pricing.input)
    cached_input_cost = (
        _token_cost(billed_cached_tokens, pricing.cached_input)
        if pricing.cached_input is not None and billed_cached_tokens > 0
        else Decimal("0")
    )
    output_cost = _token_cost(output_tokens, pricing.output)
    reasoning_cost = (
        _token_cost(reasoning_tokens, pricing.reasoning)
        if pricing.reasoning is not None and reasoning_tokens > 0
        else Decimal("0")
    )
    total_cost = input_cost + cached_input_cost + output_cost + reasoning_cost

    payload: dict[str, object] = {
        "schema_version": USAGE_COST_SCHEMA_VERSION,
        "currency": pricing.currency,
        "estimated": True,
        "pricing_source": pricing_source,
        "pricing_unit": pricing.unit,
        "input_cost_usd": _decimal_to_float(input_cost),
        "output_cost_usd": _decimal_to_float(output_cost),
        "total_cost_usd": _decimal_to_float(total_cost),
    }
    if pricing.cached_input is not None:
        payload["cached_input_cost_usd"] = _decimal_to_float(cached_input_cost)
    if pricing.reasoning is not None:
        payload["reasoning_cost_usd"] = _decimal_to_float(reasoning_cost)
    return payload


def _non_negative_decimal(value: Any, field_name: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field_name} must be a non-negative number")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a non-negative number") from exc
    if parsed < 0:
        raise ValueError(f"{field_name} must be a non-negative number")
    return parsed


def _optional_non_negative_decimal(value: Any, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return _non_negative_decimal(value, field_name)


def _non_negative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _token_cost(tokens: int, rate_per_1m: Decimal) -> Decimal:
    return (Decimal(tokens) * rate_per_1m) / Decimal(1_000_000)


def _decimal_to_float(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))
