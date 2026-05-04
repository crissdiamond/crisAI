---
id: PATT-INT-999
title: Integration patterns retrieval gaps
type: pattern
status: draft
owner: Design Author
last_reviewed: 2026-05-04
applies_to: UCL IT Architecture integration patterns
tags: integration, patterns, retrieval-gaps, catalogue
related: []
---

## Source
- Page title: Integration patterns
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/integration-patterns.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/integration-patterns.aspx

## Retrieval gaps
- Consumer Pattern 0 - Direct: list_page_links on the catalogue found the leaf URL; intranet_fetch of the leaf returned only "Details coming soon" and no grounded detail was available for drafting.
- Ingestion Pattern 1 - Database to Ingestion API - DRAFT: list_page_links on the catalogue found a page link; intranet_fetch returned a mislabelled draft headed "Producer Pattern 1 - Application Database to Ingestion API (Early Draft)" and the content was not stable enough for a grounded draft.
- Ingestion Pattern 2 - API to Ingestion API - DRAFT: list_page_links on the catalogue did not yield a usable leaf; intranet_fetch returned a mislabelled page headed "Producer Pattern 2 - System to Enterprise API : onDemand Synchronous (Draft)" rather than ingestion-specific detail.
- Ingestion Pattern 3 - DMS (rename) to Ingestion API - DRAFT: list_page_links on the catalogue did not yield a usable leaf; intranet_fetch returned a mislabelled page headed "Producer Pattern 3 - DMS to Enterprise API : onDemand Synchronous" rather than ingestion-specific detail.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/integration-patterns.aspx
