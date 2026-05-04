---
id: PATT-INT-008
title: Ingestion Pattern 1 - Database to Ingestion API
type: pattern
status: draft
owner: Architecture
related: []
---

## Source
- [Ingestion Pattern 1](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx)

## Design overview
- Name: Database to Ingestion API
- Version: 0.1
- Status: Draft
- Date: 07 Aug 2025
- Classification: Producer pattern
- Source: Database (API/DB/File)
- Target: Ingestion API
- Invocation: Synchronous
- Core pattern: Yes
- Description: Send application delta files using POST method to Data Lake.

## When to use
- Use when an application shares data with a data platform by extracting the data from a database and pushing it via the ingestion API.
- Use when a micro-batch is scheduled to fetch delta data from the application database.

## Implementation
- A micro-batch is scheduled to trigger a process to fetch delta data from the application database.
- A listener triggers a call to the ingestion API using standard authentication to post the delta files.
- If an error occurs during the process, it is modelled and sent into the standard error response.
- Solution overview is currently sparse in the fetched page.
- Physical implementation is marked as N/A / blank in the fetched page.

## Anti-patterns or when not to use
- Not suitable where the source cannot provide delta data for scheduled extraction.

## References
- [Ingestion Pattern 1](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx)
