---
id: PATT-INT-011
title: Ingestion Pattern 3 - DMS to Ingestion API
type: pattern
status: draft
owner: crisAI
last_reviewed: 2026-05-04
applies_to: all
tags: integration, ingestion, dms, ingestion-api, draft
related: []
---

## Source
- Title: Ingestion Pattern 3
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-3.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-3.aspx

## Design overview
- Pattern name: DMS to Enterprise API : onDemand Synchronous.
- Description: Send requested data to consumer over Enterprise API synchronously.
- Version: 0.1
- Status: APPROVED
- Date: 21 March 2023
- Classification: Producer pattern
- Source: System (API/DB/File)
- Target: Enterprise API
- Invocation: Synchronous
- Core pattern: Yes
- NFRs: observability with standard logging and correlation IDs; reconciliation no; reliability yes with retry and no dead letter queue because the response is synchronous; SLA guidance required; volumetric capacity depends on interface usage and concurrency; operational limits include payload and runtime thresholds.
- Security constraints: for communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account topics are open.

## When to use
- Use for application integration where there is an end user session.
- Use for enrichment such as UCL photo ID app getting additional information about the student.

## Implementation
- The pattern takes a request from the consumer, models it into system data model and invokes the system API.
- The response from the system is translated into Enterprise Data Model and sent to the Enterprise API.
- If an error occurs during the process, it is modelled and sent into a standard error response.
- Physical implementation on AWS and Azure is described on the fetched page as the standard synchronous producer pattern implementation.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-3.aspx
