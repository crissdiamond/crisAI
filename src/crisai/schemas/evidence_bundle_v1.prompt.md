Evidence bundle contract:
- Return a fenced `json` block with `schema_version: "evidence_bundle_v1"`, `request`, `items`, and `gaps`.
- For document/deck/file summary requests, this fenced JSON block is mandatory even when the prose already lists retrieved findings.
- If a required read fails, still return the bundle with a `read_failed` item and the raw tool error.
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
}
