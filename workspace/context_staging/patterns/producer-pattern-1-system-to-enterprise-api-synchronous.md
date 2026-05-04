---
id: PATT-INT-005
title: Producer Pattern 1 - System to Enterprise API: onDemand Synchronous
type: pattern
status: draft
owner: Architecture
related: []
---

## Source
- [Producer Pattern 1](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx)

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
- Use when a consumer requests data from a producer gateway and requires an enterprise modelled response in the same call.
- Use for application integration or enrichment scenarios where immediate end-user or consumer response is needed.

## Implementation
- The pattern takes request from the consumer, models it into system data model and invokes the system API.
- The response from the System is translated into an Enterprise Data Model and sent to the Enterprise API.
- If an error occurs during the process, it is modelled and sent into the standard error response.
- Solution overview includes API Gateway request, processing, publish and connector molecules.
- Physical implementation notes for AWS use API Gateway, Lambda, Secrets Manager and CloudWatch; Azure uses API Management, Azure Function, Key Vaults and Azure Monitor.

## Anti-patterns or when not to use
- Not suitable when the interface must be decoupled from the consumer request/response transaction.

## References
- [Producer Pattern 1](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx)
