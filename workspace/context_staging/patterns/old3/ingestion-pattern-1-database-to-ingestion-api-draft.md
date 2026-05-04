---
id: PATT-INT-009
title: Ingestion Pattern 1 - Database to Ingestion API - DRAFT
type: pattern
status: draft
owner: Design Author
last_reviewed: 2026-05-04
applies_to: all
tags: integration, ingestion, database, api, draft
related: []
---

## Source
- Title: Ingestion Pattern 1
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx

## Design overview
- Name: Database to Ingestion API.
- Description: send application Delta Files using POST method to Data Lake.
- Version: 0.1.
- Status: early draft.
- Classification: application database to ingestion API.

## When to use
- Use when application Delta Files are to be sent using POST to the Data Lake.

## Implementation
- Source: application database.
- Payload: Delta Files.
- Method: POST.
- Target: Data Lake.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx
