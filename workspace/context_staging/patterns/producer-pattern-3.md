---
id: PATT-INT-008
title: Producer Pattern 3 - System to Enterprise Channel: onChange Synchronous
type: pattern
status: draft
owner: Design Author
last_reviewed: 2026-05-04
applies_to: integration
tags: producer, enterprise-channel, onchange, synchronous, system, integration
related: []
---

## Source
- Title: Producer Pattern 3 — EA it-architecture
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx

## Design overview
- Name: System to Enterprise Channel - onChange Synchronous
- Version: 0.1
- Status: APPROVED
- Date: 21 March 2023
- Classification: Producer pattern; source: System (API/DB/File/Event); target: Enterprise Channel; invocation: onChange; delivery: Synchronous; core pattern: Yes
- NFRs: observability; reconciliation: Yes; reliability; SLA guidance; volumetric guidance; operational limits
- Security: For communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account items are open topics

## When to use
- Use when a source system emits a webhook on data change, the event is acknowledged, and the transformed event is published to the Enterprise Channel.
- Example use case: SITS produces a message when a student accepts an offer, and StarRez consumes it to update accommodation information.

## Implementation
- Trigger molecule: API Gateway Event
- Processing molecule: Convert to Enterprise Data Model
- Publish molecule: Send to Channel; Respond to Gateway Event
- AWS physical implementation: Webhook reaches API Gateway; API Gateway validates token and forwards request; request is saved into SQS; API Gateway returns 200 OK; SQS triggers Lambda; Lambda processes and publishes to SNS; SNS forwards to subscriptions; Lambda calls reconciliation API; dead-letter handling is used on failure.
- Azure physical implementation: Webhook reaches API Management; API Management validates token and forwards request; request is saved into Service Bus Queue; API Management returns 200 OK; Service Bus Queue triggers Azure Function; Azure Function processes and publishes to Event Grid; Event Grid forwards to subscriptions; Azure Function calls reconciliation API; dead-letter handling is used on failure.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx
