"""Reusable runtime prompt contracts.

These snippets keep tool, evidence, and rendering contracts in one place so
runtime prompts do not grow one-off patches for individual traces.
"""

from __future__ import annotations

EVIDENCE_BUNDLE_CONTRACT = """Evidence bundle contract:
- Return a fenced `json` block with `schema_version: "evidence_bundle_v1"`, `request`, `items`, and `gaps`.
- Each item must include `source`, `evidence_level`, `read_status`, `read_tool`, `content_excerpt`, and `raw_error`.
- `source` must be an object with `source_type`, `title`, and at least one durable reference such as `open_url`, `read_handle`, `workspace_path`, or `content_id`.
- Use `evidence_level: "content_read"` only after successful source text extraction. Use `read_failed` with raw tool error text when reading fails.

Example item shape:
{
  "schema_version": "evidence_bundle_v1",
  "request": "Summarise the deck",
  "items": [
    {
      "source": {
        "source_type": "sharepoint_document",
        "title": "Deck.pptx",
        "open_url": "https://example.com/deck.pptx",
        "read_handle": "sharepoint_doc:...",
        "metadata": {}
      },
      "evidence_level": "content_read",
      "read_status": "read",
      "read_tool": "read_sharepoint_document_by_handle",
      "content_excerpt": "Short quoted or paraphrased excerpt from the read content.",
      "raw_error": ""
    }
  ],
  "gaps": []
}"""

LINK_FORMATTING_CONTRACT = """Link formatting:
- Use markdown links as `[visible file name](url)` only.
- Link text is the file or page name; URL appears only inside parentheses.
- Graph URL source: `open_url` or `webUrl`. Workspace URL source: `file_uri` or `workspace_file_link`.
- Do not duplicate raw URLs as plain text.
- Do not append query strings such as `&action=edit` to visible link text.
- When listing three or more files, use one markdown table with columns `File` | `Location` | `Note`."""

SHAREPOINT_READ_HANDLE_CONTRACT = """SharePoint / OneDrive document reads:
- Search and list results include `read_handle` when the item can be read.
- Use `read_sharepoint_document_by_handle(read_handle)` for content reads.
- Use `get_sharepoint_document_metadata_by_handle(read_handle)` for metadata reads.
- Do not copy, infer, or alter raw `driveId` / `id` values from browser URLs, filenames, or prose."""

DOCUMENT_EXTRACTION_CONTRACT = """Document extraction coverage:
- `content_read` confirms source text was extracted; it does not prove complete document coverage.
- Calibrate confidence to extraction coverage and limitations reported by retrieval tools.
- For PowerPoint summaries, prefer slide-level inspection from `inspect_powerpoint_document` or `inspect_sharepoint_powerpoint_by_handle` when available.
- Preserve extraction coverage and limitations so downstream stages can caveat accurately."""

RETRIEVAL_EVIDENCE_POLICY_CONTRACT = """Retrieval evidence policy:
- Metadata and search hits are not enough to summarise a document, deck, presentation, or file.
- Summaries must use `content_read` evidence.
- Treat `search_hit_only`, `metadata_read`, and `read_failed` items as candidates or gaps, not as source content.
- For latest/most recent/master requests, include the top matching candidate metadata in the evidence bundle before/alongside the selected `content_read` item, especially title, read handle/open URL, `createdDateTime`, and `lastModifiedDateTime`.
- Do not invent missing details."""

PROMPT_CONTRACT_TOOL_REFERENCES: dict[str, frozenset[str]] = {
    "documents": frozenset({"inspect_powerpoint_document"}),
    "sharepoint_docs": frozenset({"inspect_sharepoint_powerpoint", "inspect_sharepoint_powerpoint_by_handle"}),
}
