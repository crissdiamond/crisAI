---
id: PATT-INT-009
title: Ingestion Pattern 2 - System to Enterprise API: onDemand Synchronous
type: pattern
status: draft
owner: Architecture
related: []
---

## Source
- [Ingestion Pattern 2](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-2.aspx)

## Design overview
- Name: System to Enterprise API - onDemand Synchronous
- Version: 0.1
- Status: APPROVED
- Date: 21 March 2023
- Classification: Producer pattern
- Source: System (API/DB/File)
- Target: Enterprise API
- Invocation: Synchronous
- Core pattern: Yes
- Description: Send requested data to consumer over Enterprise API synchronously.

## When to use
- Use when a consumer sends a request to the producer gateway and requires a synchronous enterprise modelled response.
- Use for application integration and enrichment scenarios where immediate delivery is required.

## Implementation
- The pattern takes request from the consumer, models it into system data model and invokes the system API.
- The response from the System is translated into an Enterprise Data Model and sent to the Enterprise API.
- If an error occurs during the process, it is modelled and sent into the standard error response.
- Physical implementation notes for AWS use API Gateway, Lambda, Secrets Manager and CloudWatch; Azure uses API Management, Azure Function, Key Vaults and Azure Monitor.

## Anti-patterns or when not to use
- Not suitable when the request must be decoupled from the response transaction.

## References
- [Ingestion Pattern 2](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-2.aspx)
