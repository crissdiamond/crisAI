---
id: PATT-INT-002
title: Consumer Pattern 1 - Enterprise Channel to System : Synchronous
type: pattern
status: draft
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, enterprise-channel, synchronous
related: []
---

## Source
- Title: Consumer Pattern 1
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx

## Design overview
- Pattern name: Enterprise Channel to System : Synchronous.
- Description: send events received on the Enterprise Channel to the target system synchronously.
- Classification: consumer pattern.
- Source: Enterprise Channel.
- Target: System.
- Delivery: synchronous.
- Version: 0.1.
- Status: APPROVED.
- Date: 21 March 2023.
- NFRs: standard logging and correlation IDs; reconciliation; retry; dead letter queue; SLA guidance; volumetric capacity and operational limits.
- Security: AWS communication uses IAM permissions implemented using Terraform; cross-cloud and cross-account topics are open.

## When to use
- Use when events arrive on the Enterprise Channel and must be transformed and sent to the target system synchronously.

## Implementation
- The event arriving on the Enterprise Channel triggers the integration flow.
- The payload is transformed into a system-specific data model.
- The payload is passed to the system via API, DB, or file.
- If an error occurs while pushing the message to the system, the message is pushed back to the Enterprise Channel queue for reprocessing.
- Physical implementation on AWS: SQS receives the message; Lambda is triggered; CloudWatch records the outcome; the Reconciliation API is called; failures go to a dead letter queue.
- Physical implementation on Azure: Service Bus Queue receives the message; Azure Function is triggered; Azure Monitor records the outcome; the Reconciliation API is called; failures go to a dead letter queue.

## Anti-patterns or when not to use
- Not stated in the source.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx