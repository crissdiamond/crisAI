from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import Any

from crisai.openai_agents_trace_compat import apply_openai_agents_trace_export_patch

apply_openai_agents_trace_export_patch()

from agents import Agent
from agents.model_settings import ModelSettings, Reasoning

from crisai.model_resolver import ModelResolver, ResolvedModel
from crisai.registry import AgentSpec, ModelSpec

logger = logging.getLogger(__name__)


class AgentFactory:
    """Build SDK agents from registry specs and prompt assets."""

    def __init__(self, root_dir: Path, model_specs: list[ModelSpec] | None = None, settings: Any | None = None) -> None:
        self.root_dir = root_dir
        self.model_resolver = ModelResolver(model_specs or [], settings=settings)

    def load_prompt(self, relative_path: str) -> str:
        """Load a prompt file relative to the repository root."""
        return (self.root_dir / relative_path).read_text(encoding="utf-8")

    def build_agent(self, spec: AgentSpec, mcp_servers: list) -> Agent:
        """Build an agent with the resolved runtime model for the spec."""
        resolved_model = self.model_resolver.resolve_for_agent(spec)
        return Agent(
            name=spec.name,
            instructions=self.load_prompt(spec.prompt_file),
            model=self._build_runtime_model(resolved_model),
            model_settings=_build_model_settings(resolved_model),
            mcp_servers=mcp_servers,
        )

    def _build_runtime_model(self, resolved_model: ResolvedModel) -> Any:
        """Build the concrete runtime model object expected by the SDK."""
        if resolved_model.runtime_model is not None:
            return resolved_model.runtime_model

        if resolved_model.provider in {"gemini", "anthropic", "deepseek"}:
            try:
                from agents.extensions.models.litellm_model import LitellmModel
            except ImportError as exc:
                raise ImportError(
                    "LiteLLM support is required for Gemini, Anthropic, or DeepSeek models. "
                    "Install it with `pip install 'openai-agents[litellm]'` or add `litellm` to your environment."
                ) from exc

            kwargs: dict[str, Any] = {}
            if resolved_model.api_key:
                kwargs["api_key"] = resolved_model.api_key
            if resolved_model.base_url:
                kwargs["base_url"] = resolved_model.base_url
            kwargs.update(_supported_litellm_kwargs(LitellmModel, resolved_model.extra))
            return LitellmModel(model=resolved_model.model_name, **kwargs)

        raise ValueError(f"Unsupported model provider: {resolved_model.provider}")


def _supported_litellm_kwargs(model_cls: Any, extra: dict[str, Any]) -> dict[str, Any]:
    """Return registry extras accepted by the installed LiteLLM adapter."""
    if not extra:
        return {}
    extra = _constructor_extra(extra)
    try:
        parameters = inspect.signature(model_cls).parameters
    except (TypeError, ValueError):
        logger.warning("Could not inspect LiteLLM model signature; ignoring registry model extras.")
        return {}
    supported = {
        key: value
        for key, value in extra.items()
        if key in parameters and key not in {"self", "model", "api_key", "base_url"}
    }
    ignored = sorted(set(extra) - set(supported))
    if ignored:
        logger.debug(
            "Ignoring unsupported LiteLLM model registry option(s): %s",
            ", ".join(ignored),
        )
    return supported


def _constructor_extra(extra: dict[str, Any]) -> dict[str, Any]:
    """Return registry extras that belong to runtime model construction."""
    model_setting_keys = {"thinking", "reasoning_effort"}
    return {key: value for key, value in extra.items() if key not in model_setting_keys}


def _build_model_settings(resolved_model: ResolvedModel) -> ModelSettings:
    """Build provider-specific call settings from registry model extras."""
    if resolved_model.provider != "deepseek":
        return ModelSettings()

    extra_body: dict[str, Any] = {}
    thinking = resolved_model.extra.get("thinking")
    if thinking is not None:
        extra_body["thinking"] = thinking

    reasoning_effort = _normalize_reasoning_effort(resolved_model.extra.get("reasoning_effort"))
    reasoning = Reasoning(effort=reasoning_effort) if reasoning_effort is not None else None
    return ModelSettings(extra_body=extra_body or None, reasoning=reasoning)


def _normalize_reasoning_effort(value: Any) -> str | None:
    """Map registry reasoning labels to the Agents SDK supported values."""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized == "max":
        return "high"
    if normalized in {"minimal", "low", "medium", "high"}:
        return normalized
    logger.debug("Ignoring unsupported reasoning_effort registry option: %s", value)
    return None
