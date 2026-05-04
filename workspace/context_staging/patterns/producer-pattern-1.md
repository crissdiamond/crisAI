---
id: PATT-INT-006
title: Producer Pattern 1 - System to Enterprise API: onDemand Synchronous
type: pattern
status: draft
owner: Design Author
last_reviewed: 2026-05-04
applies_to: integration
tags: producer, enterprise-api, synchronous, system, integration
related: []
---

## Source
- Title: Producer Pattern 1 — EA it-architecture
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx

## Design overview
- Name: System to Enterprise API - onDemand Synchronous
- Version: 0.1
- Status: APPROVED
- Date: 21 March 2023
- Classification: Producer pattern; source: System (API/DB/File); target: Enterprise API; invocation: Synchronous; core pattern: Yes
- NFRs: observability; reconciliation: No; reliability; SLA guidance; volumetric guidance; operational limits
- Security: For communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account items are open topics

## When to use
- Use when consumer requests data from a producer gateway, the response is translated from System data model to Enterprise Data Model, and returned in the same call.

## Implementation
- Trigger molecule: API Gateway Request
- Processing molecule: Convert to System Data Model; Convert to Enterprise Data Model
- Connector molecule: Fetch from System; Send to API
- AWS physical implementation: API Gateway validates JWT; forwards request to Lambda; Lambda fetches credentials from Secrets Manager; Lambda calls downstream system; response is logged in CloudWatch; response returns via API Gateway.
- Azure physical implementation: API Management validates JWT and request; forwards request to Azure Function; Azure Function fetches credentials from Key Vaults; Azure Function calls downstream system; response is logged in Azure Monitor; response returns via API Management.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx
