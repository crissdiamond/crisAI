---
id: PATT-INT-008
title: Producer Pattern 3 - System to Enterprise Channel: onChange Synchronous
type: pattern
status: draft
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, producer, enterprise-channel, onchange, synchronous
related: []
---

## Source
- Page title: Producer Pattern 3
- Web URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx
- Open URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx

## Design overview
- Name: System to Enterprise Channel - onChange Synchronous.
- Description: System events are received and sent over Enterprise Channel synchronously.
- Version / status / date: Version 0.1; APPROVED; 21 March 2023.
- Classification: Producer pattern; Source: System (API/DB/File/Event); Target: Enterprise Channel; Invocation: onChange; Delivery: Synchronous; Core Pattern: Yes.
- NFRs: Observability yes, with standard logging and correlation IDs. Reconciliation yes. Reliability yes, with retry and dead letter queue. SLA and volumetric guidance are referenced. Operational limits are stated.
- Security: For communication within AWS, use IAM permissions implemented using Terraform. Cross-cloud and cross-account topics are marked open.

## When to use
- For change-driven publication from a source system to the Enterprise Channel.
- The page gives a student offer acceptance to accommodation update example.

## Implementation
- A change in the System triggers a webhook to the producer gateway.
- The event is acknowledged and published to an internal queue.
- The event is read from the queue, modelled into Enterprise Data Model, and published to the configured Enterprise Channel.
- If an error occurs while publishing to the channel, the event is saved to Dead Letter for reprocessing.
- AWS implementation: webhook hits API Gateway, request is saved into SQS, Lambda processes it, publishes to SNS, logs to CloudWatch, and calls Reconciliation API.
- Azure implementation: webhook hits API Management, request is saved into Service Bus Queue, Azure Function processes it, publishes to Event Grid, logs to Azure Monitor, and calls Reconciliation API.

## References
- [Integration patterns](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/integration-patterns.aspx)
- [Producer Pattern 3](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx)
