Retrieval evidence policy:
- Metadata and search hits are not enough to summarise a document, deck, presentation, or file.
- Summaries must use `content_read` evidence.
- Treat `search_hit_only`, `metadata_read`, and `read_failed` items as candidates or gaps, not as source content.
- For latest/most recent/master requests, include the top matching candidate metadata in the evidence bundle before/alongside the selected `content_read` item, especially title, read handle/open URL, `createdDateTime`, and `lastModifiedDateTime`.
- Do not invent missing details.
