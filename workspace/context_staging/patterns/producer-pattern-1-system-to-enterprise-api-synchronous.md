---
id: PATT-INT-006
title: Producer Pattern 1 - System to Enterprise API: onDemand Synchronous
type: pattern
status: draft
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, producer, enterprise-api, synchronous
related: []
---

## Source
- Page title: Producer Pattern 1
- Web URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx
- Open URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx

## Design overview
- Name: System to Enterprise API - onDemand Synchronous.
- Description: Send requested data to consumer over Enterprise API synchronously.
- Version / status / date: Version 0.1; APPROVED; 21 March 2023.
- Classification: Producer pattern; Source: System (API/DB/File); Target: Enterprise API; Invocation: Synchronous; Core Pattern: Yes.
- NFRs: Observability yes, with standard logging and correlation IDs. Reconciliation no, because communication is completed in the same transaction. Reliability yes, with retry; failed messages are not saved to dead letter because error response is communicated synchronously. SLA and volumetric guidance are referenced. Operational limits are stated.
- Security: For communication within AWS, use IAM permissions implemented using Terraform. Cross-cloud and cross-account topics are marked open.

## When to use
- For application integration where a consumer needs an on-demand synchronous response from a system through an Enterprise API.
- For enrichment use cases, including the examples cited on the page.

## Implementation
- Consumer sends a request to the producer gateway using enterprise standard authentication.
- The request is modelled into system data model and the system API is invoked.
- The response from the System is translated into Enterprise Data Model and sent to the Enterprise API.
- An error is modelled and sent into a standard error response.
- AWS implementation: API Gateway validates JWT, forwards to Lambda, Lambda fetches credentials from Secrets Manager, calls the downstream system, logs to CloudWatch, and returns via API Gateway.
- Azure implementation: API Management validates JWT and request, forwards to Azure Function, Azure Function fetches credentials from Key Vault, calls the downstream system, logs to Azure Monitor, and returns via API Management.

## References
- [Integration patterns](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/integration-patterns.aspx)
- [Producer Pattern 1](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx)
