---
id: PATT-INT-010
title: Ingestion Pattern 3 - DMS to Enterprise API: onDemand Synchronous
type: pattern
status: draft
owner: Architecture
related: []
---

## Source
- [Ingestion Pattern 3](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-3.aspx)

## Design overview
- Name: DMS to Enterprise API: onDemand Synchronous
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
- Use when a consumer sends a request to the producer gateway and expects a synchronous enterprise modelled response.
- Use for application integration scenarios requiring immediate result delivery.

## Implementation
- The pattern takes request from the consumer, models it into system data model and invokes the system API.
- The response from the System is translated into an Enterprise Data Model and sent to the Enterprise API.
- If an error occurs during the process, it is modelled and sent into the standard error response.
- Physical implementation notes for AWS use API Gateway, Lambda, Secrets Manager and CloudWatch; Azure uses API Management, Azure Function, Key Vaults and Azure Monitor.

## Anti-patterns or when not to use
- Not suitable when the interface should publish to a channel instead of responding synchronously.

## References
- [Ingestion Pattern 3](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-3.aspx)
