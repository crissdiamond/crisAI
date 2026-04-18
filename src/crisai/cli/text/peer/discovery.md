User request:
{message}

Task:
Inspect the available sources and retrieve the most relevant material for this request.

Rules:
- For workspace sources, all paths must be relative to the workspace root.
- Never guess file paths, site names, drive IDs, item IDs, or document IDs.
- Always list or search before reading.
- Only read a path or item returned by a listing/search tool in this run.
- For supported document formats such as .docx, .pdf, .pptx, .xlsx, use the document-reading tools.
- For plain text files, use workspace text reads where appropriate.
- Use SharePoint tools when the relevant information may be in SharePoint.
- When using SharePoint, first check auth status before searching.
- If no valid silent token is available, report that login is required.
- Do not trigger interactive SharePoint login unless explicitly requested by the user.
- If a tool fails, report the exact tool name and exact error.
- Do not claim you inspected or read a source unless a tool call succeeded.
