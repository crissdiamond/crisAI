from __future__ import annotations

import importlib
import sys

import pytest


def _load_diagram_server(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["diagram_server.py", str(tmp_path)])
    import crisai.servers.diagram_server as diagram_server

    return importlib.reload(diagram_server)


def test_generate_mermaid_supports_flow_sequence_and_default(monkeypatch: pytest.MonkeyPatch, tmp_path):
    diagram_server = _load_diagram_server(monkeypatch, tmp_path)

    flow = diagram_server.generate_mermaid("flow", "Reporting API")
    sequence = diagram_server.generate_mermaid("sequence", "Reporting API")
    fallback = diagram_server.generate_mermaid("unknown", "Reporting API")

    assert flow.startswith("flowchart TD")
    assert "Reporting API" in flow
    assert sequence.startswith("sequenceDiagram")
    assert "Request about Reporting API" in sequence
    assert fallback.startswith("flowchart TD")


def test_validate_mermaid_checks_supported_prefixes(monkeypatch: pytest.MonkeyPatch, tmp_path):
    diagram_server = _load_diagram_server(monkeypatch, tmp_path)

    assert diagram_server.validate_mermaid("flowchart TD\nA-->B")["valid"] is True
    assert diagram_server.validate_mermaid("sequenceDiagram\nA->>B: hi")["valid"] is True
    assert diagram_server.validate_mermaid("plain text")["valid"] is False


def test_save_diagram_slugifies_and_restricts_outputs(monkeypatch: pytest.MonkeyPatch, tmp_path):
    diagram_server = _load_diagram_server(monkeypatch, tmp_path)

    rel_path = diagram_server.save_diagram("My Diagram!", "flowchart TD\nA-->B")

    assert rel_path == "outputs/diagrams/my-diagram.mmd"
    assert (tmp_path / rel_path).read_text(encoding="utf-8") == "flowchart TD\nA-->B"

    with pytest.raises(ValueError, match="restricted"):
        diagram_server.save_diagram("bad", "flowchart TD\nA-->B", subdir="scratch")

    with pytest.raises(ValueError, match="escapes"):
        diagram_server.save_diagram("bad", "flowchart TD\nA-->B", subdir="../outside")


def test_save_diagram_enforces_byte_limit(monkeypatch: pytest.MonkeyPatch, tmp_path):
    diagram_server = _load_diagram_server(monkeypatch, tmp_path)
    monkeypatch.setenv("CRISAI_DIAGRAM_MAX_WRITE_BYTES", "1024")

    with pytest.raises(ValueError, match="maximum size"):
        diagram_server.save_diagram("large", "x" * 1025)
