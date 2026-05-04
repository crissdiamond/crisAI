---
id: PATT-INT-002
title: Consumer Pattern 1 - Enterprise Channel to System: Synchronous
type: pattern
status: draft
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, enterprise-channel, synchronous
related: []
---

## Source
- Page title: Consumer Pattern 1
- Web URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx
- Open URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx

## Design overview
- Name: Enterprise Channel to System: Synchronous
- Description: Send events received on the Enterprise Channel to the target system synchronously.
- Version / status / date: Version 0.1; APPROVED; 21 March 2023.
- Classification: Consumer pattern; Source: Enterprise Channel; Target: System (API/DB/File); Delivery: Synchronous; Core Pattern: Yes.
- NFRs: Observability yes, with standard logging and correlation IDs. Reconciliation yes. Reliability yes, with retry and dead letter queue. SLA and volumetric guidance are referenced. Operational limits are stated.
- Security: For communication within AWS, use IAM permissions implemented using Terraform. Cross-cloud and cross-account topics are marked open.

## When to use
- For consuming events from the Enterprise Channel and sending them to a target system in a synchronous flow.

## Implementation
- The event arriving on the Enterprise Channel is transformed to a System Data Model.
- The payload is passed to the System via API, DB or File.
- If an error occurs while pushing to the System, the message is pushed back to the Enterprise Channel queue for reprocessing.
- AWS implementation: SQS receives the message, Lambda processes it, logs to CloudWatch, and records status via a Reconciliation API.
- Azure implementation: Service Bus receives the message, Azure Function processes it, logs to Azure Monitor, and records status via a Reconciliation API.

## References
- [Integration patterns](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/integration-patterns.aspx)
- [Consumer Pattern 1](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx)
