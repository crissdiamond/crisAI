"""Source capability contract (CRISAI-ADR-013): loading and doctor validation."""

from pathlib import Path

from crisai.registry import Registry, ServerSpec, SourceCapability
from crisai.registry_validation import _validate_source_capability

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registry"


def _cap(**overrides) -> SourceCapability:
    base = dict(
        source_families=("workspace",),
        source_types=("file",),
        operations={"search": ("search_workspace_text",)},
        evidence_levels=("content_read",),
        reference_handle="workspace_path",
        reference_stability="stable",
        auth_login_tool="",
        auth_status_tool="",
        pagination="none",
        freshness="mtime",
    )
    base.update(overrides)
    return SourceCapability(**base)


def _source(cap: SourceCapability | None, kind: str = "source") -> ServerSpec:
    return ServerSpec(
        id="s", name="S", enabled=True, transport="stdio", tags=[], raw={}, kind=kind, capabilities=cap
    )


def test_valid_source_capability_has_no_issues():
    errors: list = []
    warnings: list = []
    _validate_source_capability(_source(_cap()), ["search_workspace_text"], errors, warnings)
    assert errors == []
    assert warnings == []


def test_operation_tool_not_in_allow_is_an_error():
    errors: list = []
    warnings: list = []
    cap = _cap(operations={"search": ("not_exposed_tool",)})
    _validate_source_capability(_source(cap), ["search_workspace_text"], errors, warnings)
    assert any("not_exposed_tool" in e.message for e in errors)


def test_unknown_source_family_is_an_error():
    errors: list = []
    warnings: list = []
    _validate_source_capability(_source(_cap(source_families=("bogus",))), [], errors, warnings)
    assert any("source_family" in e.message and "bogus" in e.message for e in errors)


def test_unknown_evidence_level_is_an_error():
    errors: list = []
    warnings: list = []
    cap = _cap(evidence_levels=("read_failed",))  # not a declarable capability level
    _validate_source_capability(_source(cap), ["search_workspace_text"], errors, warnings)
    assert any("evidence_level" in e.message for e in errors)


def test_source_without_capabilities_is_an_error():
    errors: list = []
    warnings: list = []
    _validate_source_capability(_source(None), [], errors, warnings)
    assert any("missing a capabilities" in e.message for e in errors)


def test_tool_server_with_capabilities_warns():
    errors: list = []
    warnings: list = []
    _validate_source_capability(_source(_cap(), kind="tool"), [], errors, warnings)
    assert warnings
    assert errors == []


def test_invalid_kind_is_an_error():
    errors: list = []
    warnings: list = []
    server = ServerSpec(id="x", name="X", enabled=True, transport="stdio", tags=[], raw={}, kind="weird")
    _validate_source_capability(server, [], errors, warnings)
    assert any("invalid kind" in e.message for e in errors)


def test_live_registry_source_servers_validate_cleanly():
    servers = Registry(REGISTRY_DIR).load_servers()
    sources = [s for s in servers if s.kind == "source"]
    assert len(sources) == 5  # workspace, workspace_read, documents, sharepoint_docs, intranet
    for server in sources:
        errors: list = []
        warnings: list = []
        allow = server.raw.get("tools", {}).get("allow", [])
        _validate_source_capability(server, allow, errors, warnings)
        assert errors == [], (server.id, [e.message for e in errors])
