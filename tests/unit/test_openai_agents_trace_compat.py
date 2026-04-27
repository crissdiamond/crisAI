from __future__ import annotations

from crisai.openai_agents_trace_compat import apply_openai_agents_trace_export_patch


def test_mcp_list_tools_span_export_coerces_null_result_to_empty_list():
    apply_openai_agents_trace_export_patch()
    from agents.tracing.span_data import MCPListToolsSpanData

    span = MCPListToolsSpanData(server="test-server", result=None)
    exported = span.export()
    assert exported["result"] == []
    assert exported["server"] == "test-server"


def test_mcp_list_tools_span_export_preserves_nonempty_result():
    apply_openai_agents_trace_export_patch()
    from agents.tracing.span_data import MCPListToolsSpanData

    span = MCPListToolsSpanData(server="s", result=["a", "b"])
    assert span.export()["result"] == ["a", "b"]
