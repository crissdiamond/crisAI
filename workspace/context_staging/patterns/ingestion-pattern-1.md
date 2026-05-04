---
id: PATT-INT-009
title: Ingestion Pattern 1 - Database to Ingestion API
type: pattern
status: draft
owner: Design Author
last_reviewed: 2026-05-04
applies_to: integration
tags: ingestion, database, ingestion-api, synchronous, data-platform
related: []
---

## Source
- Title: Ingestion Pattern 1 — EA it-architecture
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx

## Design overview
- Name: Database to Ingestion API
- Version: 0.1
- Status: Draft
- Date: 07 Aug 2025
- Classification: Producer pattern; source: Database (API/DB/File); target: Ingestion API; invocation: Synchronous; core pattern: Yes
- NFRs: observability; reconciliation: No; reliability; SLA guidance; volumetric guidance; operational limits
- Security: For communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account items are open topics

## When to use
- Use when an application shares data with a data platform by extracting data from a database and pushing the dataset using the Ingestion API.

## Implementation
- Trigger molecule: API Gateway Request
- Processing molecule: Convert to System Data Model; Convert to Enterprise Data Model
- Publish molecule: Send to API
- Connector molecule: Fetch from System; Send to System
- Description details: a micro-batch is scheduled to fetch delta data from the application database; a listener calls the ingestion API using standard authentication to post delta files.
- AWS physical implementation: not stated.
- Azure physical implementation: not stated.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx
