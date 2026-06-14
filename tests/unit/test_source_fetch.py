from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest

from crisai.orchestration import source_fetch
from crisai.orchestration.source_fetch import SourceFetchError, fetch_source_bytes


class _FakeResult:
    def __init__(self, *, structured=None, content=None, is_error=False):
        self.structuredContent = structured
        self.content = content or []
        self.isError = is_error


class _FakeServer:
    """Minimal async-context-manager stand-in for an MCP server client."""

    def __init__(self, result):
        self._result = result
        self.calls: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self._result


class _FakeRuntime:
    def __init__(self, server):
        self._server = server
        self.build_kwargs: dict = {}

    def build_server(self, spec, env_overrides=None, *, include_internal=False):
        self.build_kwargs = {"include_internal": include_internal}
        return self._server


def _payload(raw: bytes) -> dict:
    return {
        "name": "UCL Integration Strategy v2.pptx",
        "suffix": ".pptx",
        "revision": "2022-10-12T11:25:56Z",
        "size": len(raw),
        "content_base64": base64.b64encode(raw).decode("ascii"),
    }


@pytest.mark.anyio
async def test_fetch_decodes_structured_payload_and_enables_internal_tools():
    raw = b"\x50\x4b\x03\x04 fake ooxml \x00\x01"
    server = _FakeServer(_FakeResult(structured=_payload(raw)))
    runtime = _FakeRuntime(server)

    fetched = await fetch_source_bytes(SimpleNamespace(raw={}), "spdoc-abc123", runtime=runtime)

    assert fetched.raw_bytes == raw
    assert fetched.revision == "2022-10-12T11:25:56Z"
    assert fetched.suffix == ".pptx"
    assert fetched.size == len(raw)
    # The deterministic path must enable internal tools to reach the download tool.
    assert runtime.build_kwargs["include_internal"] is True
    assert server.calls == [(source_fetch.DOWNLOAD_TOOL, {"read_handle": "spdoc-abc123"})]


@pytest.mark.anyio
async def test_fetch_falls_back_to_json_text_content():
    import json

    raw = b"bytes-via-text"
    text_item = SimpleNamespace(text=json.dumps(_payload(raw)))
    server = _FakeServer(_FakeResult(content=[text_item]))
    runtime = _FakeRuntime(server)

    fetched = await fetch_source_bytes(SimpleNamespace(raw={}), "spdoc-x", runtime=runtime)

    assert fetched.raw_bytes == raw
    assert fetched.suffix == ".pptx"


@pytest.mark.anyio
async def test_fetch_raises_on_tool_error_result():
    server = _FakeServer(_FakeResult(content=[SimpleNamespace(text="boom")], is_error=True))
    runtime = _FakeRuntime(server)

    with pytest.raises(SourceFetchError, match="reported an error"):
        await fetch_source_bytes(SimpleNamespace(raw={}), "spdoc-x", runtime=runtime)


@pytest.mark.anyio
async def test_fetch_requires_a_read_handle():
    runtime = _FakeRuntime(_FakeServer(_FakeResult(structured={})))
    with pytest.raises(SourceFetchError, match="read_handle is required"):
        await fetch_source_bytes(SimpleNamespace(raw={}), "   ", runtime=runtime)


def test_build_server_includes_internal_tools_only_when_requested():
    # Guards the agent-exclusion invariant: the default agent path excludes
    # internal tools; only include_internal=True surfaces them.
    from crisai.registry import ServerSpec
    from crisai.runtime import RuntimeManager

    captured: dict = {}

    spec = ServerSpec(
        id="sharepoint_docs",
        name="SP",
        enabled=True,
        transport="stdio",
        tags=[],
        raw={
            "command": "python",
            "args": [],
            "tools": {"allow": ["search_my_onedrive"], "internal": ["download_source_bytes_by_handle"]},
        },
    )

    import crisai.runtime as runtime_module

    def _fake_filter(*, allowed_tool_names):
        captured["allowed"] = list(allowed_tool_names)
        return object()

    original = runtime_module.create_static_tool_filter
    runtime_module.create_static_tool_filter = _fake_filter
    try:
        rm = RuntimeManager(root_dir=__import__("pathlib").Path("."))
        rm.build_server(spec)  # agent default
        agent_tools = captured["allowed"]
        rm.build_server(spec, include_internal=True)  # deterministic path
        internal_tools = captured["allowed"]
    finally:
        runtime_module.create_static_tool_filter = original

    assert "download_source_bytes_by_handle" not in agent_tools
    assert "download_source_bytes_by_handle" in internal_tools
    assert "search_my_onedrive" in agent_tools
