Document extraction coverage:
- `content_read` confirms source text was extracted; it does not prove complete document coverage.
- Calibrate confidence to extraction coverage and limitations reported by retrieval tools.
- For PowerPoint summaries, prefer slide-level inspection from `inspect_powerpoint_document` or `inspect_sharepoint_powerpoint_by_handle` when available.
- Preserve extraction coverage and limitations so downstream stages can caveat accurately.
