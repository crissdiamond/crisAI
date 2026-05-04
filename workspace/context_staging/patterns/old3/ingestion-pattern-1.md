---
id: PATT-INT-009
title: Ingestion Pattern 1 - Database to Ingestion API
type: pattern
status: draft
owner: crisAI
last_reviewed: 2026-05-04
applies_to: all
tags: integration, ingestion, database, ingestion-api, draft
related: []
---

## Source
- Title: Ingestion Pattern 1
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx

## Design overview
- Pattern name: Database to Ingestion API
- Description: Send application Delta Files using POST method to Data Lake.
- Version: 0.1
- Status: Draft
- Date: 07 Aug 2025
- Classification: Producer pattern
- Source: Database (API/DB/File)
- Target: Ingestion API
- Invocation: Synchronous
- Core pattern: Yes
- NFRs: observability with standard logging and correlation IDs; reconciliation no; reliability yes with retry and no dead letter queue because the error response is synchronous; SLA guidance required; volumetric capacity depends on interface usage and concurrency; operational limits include payload and runtime thresholds.
- Security constraints: for communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account topics are open.

## When to use
- Use when an application shares data with a data platform by extracting data from a database and pushing the data set using the ingestion API.

## Implementation
- A micro batch is scheduled to trigger a process to fetch the delta data from the application database.
- A listener triggers a call to the ingestion API, using standard authentication to post the delta files.
- If an error occurs during the process, it is modelled and sent into a standard error response.
- Physical implementation: not stated on the fetched page.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx
