---
id: PATT-INT-009
title: Ingestion Pattern 1 - Database to Ingestion API - DRAFT
type: pattern
status: draft
owner: Architecture
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
- Status: Draft.
- Description: send application delta files using POST to the Data Lake.
- Classification: application database to ingestion API.
- Version: 0.1.
- Delivery mode: micro-batch schedule.

## When to use
- Use when application delta files are to be sent using POST to the Data Lake.

## Implementation
- Source: application database.
- Payload: delta files.
- Method: POST.
- Target: Data Lake.
- Trigger: listener trigger and micro-batch schedule.
- The flow calls the ingestion API.

## Anti-patterns or when not to use
- Not stated in the source.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx