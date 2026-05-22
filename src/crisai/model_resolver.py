from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from crisai import registry


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

    def __init__(self, models: list[registry.ModelSpec] | dict[str, registry.ModelSpec], settings: Any | None = None) -> None:
        """Initializes the ModelResolver.

        Args:
            models: A list or dictionary of model specifications from the registry.
            settings: Optional application settings for fallback credentials.
        """
        self.settings = settings
        if isinstance(models, dict):
            self.models = models
        else:
            self.models = {spec.id: spec for spec in models}

    def resolve_for_agent(self, spec: registry.AgentSpec) -> ResolvedModel:
        """Resolves the configured model for the supplied agent spec.

        Args:
            spec: The agent specification structure containing a model ref.

        Returns:
            A ResolvedModel instance containing validated settings.

        Raises:
            ValueError: If the agent does not define a model_ref or legacy model.
        """
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
        """Resolves a model reference ID to a ResolvedModel instance.

        Args:
            model_ref: The logical identifier of the model spec to resolve.

        Returns:
            A ResolvedModel instance populated from the registry specification.

        Raises:
            ValueError: If the model provider is unsupported or reference is unknown.
        """
        spec = self.models.get(model_ref)
        if spec is None:
            raise ValueError(f"Unknown model_ref: {model_ref}")

        provider = (spec.provider or "").strip().lower()
        api_key_env = getattr(spec, "api_key_env", None)
        api_key: str | None = None
        runtime_model: Any | None = None

        if provider == "openai":
            runtime_model = spec.model_name
        elif provider in {"gemini", "anthropic", "deepseek"}:
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
        """Returns the configured API key for the provider or raises clearly.

        Args:
            provider: The lowercase name of the LLM provider (e.g. 'openai').
            api_key_env: An optional override environment variable name.

        Returns:
            The API key string.

        Raises:
            ValueError: If the API key is not found in env or settings.
        """
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
        """Returns the default environment variable name for a provider's API key.

        Args:
            provider: The lowercase provider name.

        Returns:
            The name of the environment variable (e.g. 'OPENAI_API_KEY').
          """
        defaults = {
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }
        return defaults.get(provider, f"{provider.upper()}_API_KEY")

