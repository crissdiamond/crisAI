# SharePoint vs OneDrive (retrieval)

For **SharePoint** (team sites, libraries, organisation content) **without** an explicit **personal OneDrive-only** scope:

- Prefer **`search_sharepoint_site_documents`** or **`list_sites`** then **`search_site_drive_documents`** per site.

Do **not** satisfy SharePoint-only requests using **only** `list_my_drives` + `search_drive_documents`, because that path skews to the user’s **personal OneDrive**.

When the user explicitly wants **personal OneDrive**, use `list_my_drives` / `search_drive_documents` on the correct drive.
