"""Reusable runtime prompt contracts.

These snippets keep tool, evidence, and rendering contracts in one place so
runtime prompts do not grow one-off patches for individual traces.
"""

from __future__ import annotations

from crisai import schemas as schemas_module

load_schema_text = schemas_module.load_schema_text

EVIDENCE_BUNDLE_CONTRACT = load_schema_text("evidence_bundle_v1.prompt.md").strip()

LINK_FORMATTING_CONTRACT = load_schema_text("link_formatting.prompt.md").strip()

SHAREPOINT_READ_HANDLE_CONTRACT = load_schema_text("sharepoint_read_handle.prompt.md").strip()

DOCUMENT_EXTRACTION_CONTRACT = load_schema_text("document_extraction.prompt.md").strip()

RETRIEVAL_EVIDENCE_POLICY_CONTRACT = load_schema_text("retrieval_evidence_policy.prompt.md").strip()

PROMPT_CONTRACT_TOOL_REFERENCES: dict[str, frozenset[str]] = {
    "documents": frozenset({"inspect_powerpoint_document"}),
    "sharepoint_docs": frozenset({"inspect_sharepoint_powerpoint_by_handle"}),
}
