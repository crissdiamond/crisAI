---
id: PATT-INT-008
title: Producer Pattern 3 - System to Enterprise Channel : onChange Synchronous
type: pattern
status: draft
owner: crisAI
last_reviewed: 2026-05-04
applies_to: all
tags: integration, producer, enterprise-channel, onchange, synchronous
related: []
---

## Source
- Title: Producer Pattern 3
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx

## Design overview
- Pattern name: System to Enterprise Channel - onChange Synchronous
- Description: System events are received and sent over the Enterprise Channel synchronously.
- Version: 0.1
- Status: APPROVED
- Date: 21 March 2023
- Classification: Producer pattern
- Source: System (API/DB/File/Event)
- Target: Enterprise Channel
- Invocation: onChange
- Delivery: Synchronous
- Core pattern: Yes
- NFRs: observability with standard logging and correlation IDs; reconciliation yes; reliability yes with retry and dead letter queue; SLA guidance required; volumetric capacity depends on interface usage and concurrency; operational limits include payload and runtime thresholds.
- Security constraints: for communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account topics are open.

## When to use
- Use when a source system triggers a webhook on data change and the event needs to be published to the Enterprise Channel.
- Use for synchronising downstream systems with master data.

## Implementation
- A change in the system triggers the event via webhook to the producer gateway.
- The event is acknowledged and published to an internal queue.
- The event is read from the queue, modelled into Enterprise Data Model and published to the configured Enterprise Channel.
- If an error occurs while publishing to the channel, the event is saved to dead letter for reprocessing.
- Physical implementation on AWS: the webhook is validated by API Gateway; the request is saved into SQS; API Gateway responds with 200 OK; SQS triggers Lambda; Lambda processes the request and publishes to SNS; SNS forwards to subscriptions; Lambda calls the Reconciliation API; failures go to a dead letter queue.
- Physical implementation on Azure: the webhook is validated by API Management; the request is saved into Service Bus Queue; API Management responds with 200 OK; Service Bus Queue triggers Azure Function; Azure Function processes the request and publishes to Event Grid; Event Grid forwards to subscriptions; Azure Function calls the Reconciliation API; failures go to a dead letter queue.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx
