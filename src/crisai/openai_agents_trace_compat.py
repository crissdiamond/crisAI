"""Compatibility fixes for the ``openai-agents`` SDK tracing exporter.

The OpenAI tracing API expects ``span_data.result`` on MCP list-tools spans to
be a JSON **array of strings**. The SDK sometimes leaves ``result`` as
``null`` (for example when ``list_tools`` fails before the span is updated),
which triggers non-fatal ``400 invalid_request_error`` responses from the
tracing client.

This module normalizes exports so ``result`` is never ``null``.
"""

from __future__ import annotations

_patch_applied = False


def apply_openai_agents_trace_export_patch() -> None:
    """Idempotently patch ``MCPListToolsSpanData.export`` to coerce ``result`` to a list."""
    global _patch_applied
    if _patch_applied:
        return
    try:
        from agents.tracing.span_data import MCPListToolsSpanData

        _original_export = MCPListToolsSpanData.export

        def _export_with_non_null_result(self: MCPListToolsSpanData) -> dict:  # type: ignore[type-arg]
            payload = _original_export(self)
            if payload.get("result") is None:
                return {**payload, "result": []}
            return payload

        MCPListToolsSpanData.export = _export_with_non_null_result  # type: ignore[method-assign]
    except Exception:
        # SDK layout or optional dependency changed; skip quietly.
        return
    _patch_applied = True
