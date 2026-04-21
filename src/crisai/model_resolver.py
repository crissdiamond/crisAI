from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from crisai.registry import AgentSpec, ModelSpec


@dataclass(slots=True)
class ResolvedModel:
    """Resolved provider-aware model configuration for an agent.

    The resolver validates the configuration and required credentials, but it
    avoids constructing optional provider runtime objects eagerly. This keeps
    import-time and unit-test behaviour stable even when optional dependencies
    such as LiteLLM are not installed.
    """

    provider: str
    model_name: str
    source: str
    runtime_model: Any | None = None
    api_key: str | None = None
    api_key_env: str | None = None
    base_url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class ModelResolver:
    """Resolve logical model references into provider-aware model settings."""

    def __init__(self, models: list[ModelSpec] | dict[str, ModelSpec], settings: Any | None = None) -> None:
        self.settings = settings
        if isinstance(models, dict):
            self.models = models
        else:
            self.models = {spec.id: spec for spec in models}

    def resolve_for_agent(self, spec: AgentSpec) -> ResolvedModel:
        """Resolve the configured model for the supplied agent spec."""
        if getattr(spec, "model_ref", None):
            return self._resolve_model_ref(str(spec.model_ref))

        legacy_model = getattr(spec, "model", None)
        if legacy_model:
            return ResolvedModel(
                provider="openai",
                model_name=str(legacy_model),
                source="legacy:model",
                runtime_model=str(legacy_model),
            )

        raise ValueError(f"Agent '{spec.id}' does not define model_ref or legacy model.")

    def _resolve_model_ref(self, model_ref: str) -> ResolvedModel:
        spec = self.models.get(model_ref)
        if spec is None:
            raise ValueError(f"Unknown model_ref: {model_ref}")

        provider = (spec.provider or "").strip().lower()
        api_key_env = getattr(spec, "api_key_env", None)
        api_key: str | None = None
        runtime_model: Any | None = None

        if provider == "openai":
            runtime_model = spec.model_name
        elif provider in {"gemini", "anthropic"}:
            api_key = self._get_api_key(provider, api_key_env)
        else:
            raise ValueError(f"Unsupported model provider: {spec.provider}")

        return ResolvedModel(
            provider=provider,
            model_name=spec.model_name,
            source=f"model_ref:{model_ref}",
            runtime_model=runtime_model,
            api_key=api_key,
            api_key_env=api_key_env,
            base_url=getattr(spec, "base_url", None),
            extra=dict(getattr(spec, "extra", {}) or {}),
        )

    def _get_api_key(self, provider: str, api_key_env: str | None) -> str:
        """Return the configured API key for the provider or raise clearly."""
        env_name = api_key_env or self._default_api_key_env(provider)
        value = os.getenv(env_name, "")
        if value:
            return value

        if self.settings is not None:
            settings_value = getattr(self.settings, f"{provider}_api_key", "")
            if settings_value:
                return str(settings_value)

        raise ValueError(
            f"Missing required API key for provider '{provider}'. "
            f"Expected environment variable '{env_name}'."
        )

    @staticmethod
    def _default_api_key_env(provider: str) -> str:
        defaults = {
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        return defaults.get(provider, f"{provider.upper()}_API_KEY")
