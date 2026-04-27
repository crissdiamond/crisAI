from __future__ import annotations

from pathlib import Path
from typing import Any

from crisai.openai_agents_trace_compat import apply_openai_agents_trace_export_patch

apply_openai_agents_trace_export_patch()

from agents import Agent

from crisai.model_resolver import ModelResolver, ResolvedModel
from crisai.registry import AgentSpec, ModelSpec


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
            mcp_servers=mcp_servers,
        )

    def _build_runtime_model(self, resolved_model: ResolvedModel) -> Any:
        """Build the concrete runtime model object expected by the SDK."""
        if resolved_model.runtime_model is not None:
            return resolved_model.runtime_model

        if resolved_model.provider in {"gemini", "anthropic"}:
            try:
                from agents.extensions.models.litellm_model import LitellmModel
            except ImportError as exc:
                raise ImportError(
                    "LiteLLM support is required for Gemini or Anthropic models. "
                    "Install it with `pip install 'openai-agents[litellm]'` or add `litellm` to your environment."
                ) from exc

            kwargs: dict[str, Any] = {}
            if resolved_model.api_key:
                kwargs["api_key"] = resolved_model.api_key
            if resolved_model.base_url:
                kwargs["base_url"] = resolved_model.base_url
            kwargs.update(resolved_model.extra)
            return LitellmModel(model=resolved_model.model_name, **kwargs)

        raise ValueError(f"Unsupported model provider: {resolved_model.provider}")
