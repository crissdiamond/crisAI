---
id: PATT-INT-003
title: Consumer Pattern 2 - Enterprise Channel to System : Asynchronous
type: pattern
status: draft
owner: crisAI
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, enterprise-channel, asynchronous
related: []
---

## Source
- Title: Consumer Pattern 2
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx

## Design overview
- Pattern name: Enterprise Channel to System : Asynchronous
- Description: Send events received on the Enterprise Channel to the target System asynchronously.
- Version: 0.1
- Status: APPROVED
- Date: 30 March 2023
- Classification: Consumer pattern
- Source: Enterprise Channel
- Target: System (API/DB/File)
- Delivery: Asynchronous
- Core pattern: Yes
- NFRs: observability with standard logging and correlation IDs; reconciliation yes; reliability yes with retry and dead letter queue; SLA guidance required; volumetric capacity depends on interface usage and concurrency; operational limits include payload and runtime thresholds.
- Security constraints: for communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account topics are open.

## When to use
- Use when events arrive on the Enterprise Channel and the target system is updated asynchronously through queued processing.

## Implementation
- The event on the Enterprise Channel triggers the flow.
- The payload from the Enterprise Channel is transformed into a system data model.
- The payload is saved to a queue.
- A separate scheduler triggers subsequent processing at configured frequency intervals.
- The saved messages are read and sent to the target system via API, DB or file.
- If an error occurs while communicating with the target system, the message is pushed back to the queue for reprocessing.
- Physical implementation on AWS: Enterprise Channel publishes to SQS; Lambda transforms the message; the transformed message is saved to another SQS for batch processing; CloudWatch triggers batch processing; Lambda sends the processed batch to the system; the outcome is logged in CloudWatch; the final call is made to the Reconciliation API; failures go to a dead letter queue.
- Physical implementation on Azure: Enterprise Channel publishes to Service Bus Queue; Azure Function transforms the message; the transformed message is saved to another Service Bus Queue for batch processing; a Time Trigger service triggers batch processing; Azure Function sends the processed batch to the system; the outcome is logged in Azure Monitor; the final call is made to the Reconciliation API; failures go to a dead letter queue.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx
