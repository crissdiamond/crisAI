---
id: PATT-INT-003
title: Consumer Pattern 2 - Enterprise Channel to System: Asynchronous
type: pattern
status: draft
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, enterprise-channel, asynchronous
related: []
---

## Source
- Page title: Consumer Pattern 2
- Web URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx
- Open URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx

## Design overview
- Name: Enterprise Channel to System: Asynchronous
- Description: Send events received on the Enterprise Channel to the target System asynchronously.
- Version / status / date: Version 0.1; APPROVED; 30 March 2023.
- Classification: Consumer pattern; Source: Enterprise Channel; Target: System (API/DB/File); Delivery: Asynchronous; Core Pattern: Yes.
- NFRs: Observability yes, with standard logging and correlation IDs. Reconciliation yes. Reliability yes, with retry and dead letter queue. SLA and volumetric guidance are referenced. Operational limits are stated.
- Security: For communication within AWS, use IAM permissions implemented using Terraform. Cross-cloud and cross-account topics are marked open.

## When to use
- For consuming Enterprise Channel events and publishing them to a System with asynchronous processing.

## Implementation
- The event arriving on the Enterprise Channel is transformed into a System Data Model and saved to a queue.
- Messages are consumed on a scheduled basis and sent to the target System after processing.
- If an error occurs while communicating with the target System, the message is pushed back to the queue for reprocessing.
- AWS implementation: Enterprise Channel publishes to SQS, Lambda transforms and stores to a batch SQS, CloudWatch cron triggers batch processing, then Lambda sends to System and logs status.
- Azure implementation: Enterprise Channel publishes to Service Bus, Azure Function transforms and stores to a batch queue, Time Trigger starts batch processing, then Azure Function sends to System and logs status.

## References
- [Integration patterns](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/integration-patterns.aspx)
- [Consumer Pattern 2](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx)
