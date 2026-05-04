---
id: PATT-INT-002
title: Consumer Pattern 1 - Enterprise Channel to System : Synchronous
type: pattern
status: draft
owner: crisAI
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
- Pattern name: Enterprise Channel to System: Synchronous
- Description: Send events received on the Enterprise Channel to the target system synchronously.
- Version: 0.1
- Status: APPROVED
- Date: 21 March 2023
- Classification: Consumer pattern
- Source: Enterprise Channel
- Target: System (API/DB/File)
- Delivery: Synchronous
- Core pattern: Yes
- NFRs: observability with standard logging and correlation IDs; reconciliation yes; reliability yes with retry and dead letter queue; SLA guidance required; volumetric capacity depends on interface usage and concurrency; operational limits include payload and runtime thresholds.
- Security constraints: for communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account topics are open.

## When to use
- Use when events arrive on the Enterprise Channel and must be transformed and sent to the target system synchronously.

## Implementation
- The event arriving on the Enterprise Channel triggers the integration flow.
- The payload from the channel is transformed into a system-specific data model.
- The payload is passed to the system via API, DB or file.
- If an error occurs while pushing the message to the system, the message is pushed back to the Enterprise Channel queue for reprocessing.
- Physical implementation on AWS: SQS queue receives the message; Lambda is triggered; the request is processed and sent to the system; the outcome is logged in CloudWatch; the final call is made to the Reconciliation API; failures go to a dead letter queue.
- Physical implementation on Azure: Service Bus Queue receives the message; Azure Function is triggered; the request is processed and sent to the system; the outcome is logged in Azure Monitor; the final call is made to the Reconciliation API; failures go to a dead letter queue.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx
