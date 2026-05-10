SharePoint / OneDrive document reads:
- Search and list results include `read_handle` when the item can be read.
- Use `read_sharepoint_document_by_handle(read_handle)` for content reads.
- Use `get_sharepoint_document_metadata_by_handle(read_handle)` for metadata reads.
- Do not copy, infer, or alter raw `driveId` / `id` values from browser URLs, filenames, or prose.
