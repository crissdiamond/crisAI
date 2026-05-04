---
id: PATT-INT-009
title: Ingestion Pattern 1 - Database to Ingestion API
type: pattern
status: draft
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, ingestion, database, api
related: []
---

## Source
- Page title: Ingestion Pattern 1
- Web URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx
- Open URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx

## Design overview
- Name: Database to Ingestion API.
- Description: Send application delta files using POST method to Data Lake.
- Version / status / date: Version 0.1; Draft; 07 Aug 2025.
- Classification: Producer pattern; Source: Database (API/DB/File); Target: Ingestion API; Invocation: Synchronous; Core Pattern: Yes.
- NFRs: Observability yes, with standard logging and correlation IDs. Reconciliation no. Reliability yes, with retry; failed messages are not saved to dead letter because error response is communicated synchronously. SLA and volumetric guidance are referenced. Operational limits are stated.
- Security: For communication within AWS, use IAM permissions implemented using Terraform. Cross-cloud and cross-account topics are marked open.

## When to use
- For an application sharing data with a data platform by extracting data from a database and pushing the data set using the ingestion API.

## Implementation
- A micro batch is scheduled to trigger a process to fetch delta data from the application database.
- A listener triggers a call to the ingestion API using standard authentication to post the delta files.
- If an error occurs during the process, it is modelled and sent into a standard error response.

## References
- [Integration patterns](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/integration-patterns.aspx)
- [Ingestion Pattern 1](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx)
