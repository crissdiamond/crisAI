---
id: PATT-INT-003
title: Consumer Pattern 2 - Enterprise Channel to System: Asynchronous
type: pattern
status: draft
owner: Design Author
last_reviewed: 2026-05-04
applies_to: integration
tags: consumer, enterprise-channel, asynchronous, system, integration
related: []
---

## Source
- Title: Consumer Pattern 2 — EA it-architecture
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx

## Design overview
- Name: Enterprise Channel to System : Asynchronous
- Version: 0.1
- Status: APPROVED
- Date: 30 March 2023
- Classification: Consumer pattern; source: Enterprise Channel; target: System (API/DB/File); delivery: Asynchronous; core pattern: Yes
- NFRs: observability; reconciliation: Yes; reliability; SLA guidance; volumetric guidance; operational limits
- Security: For communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account items are open topics

## When to use
- Use when events arriving on the Enterprise Channel are transformed into a System data model, saved to a queue, and later consumed on a scheduled basis.

## Implementation
- Trigger molecule: Scheduled Event
- Processing molecule: Fetch Event; Convert to System Data Model; Save File
- Connector molecule: Send to System
- AWS physical implementation: Enterprise Channel publishes to SQS; Lambda transforms the message; the message is saved to another SQS for batch processing; CloudWatch logs processing status; a cron-triggered Lambda performs batch processing; a final Lambda sends processed records to the System; reconciliation API records processing status; dead-letter handling is used on failure.
- Azure physical implementation: Enterprise Channel publishes to Service Bus Queue; Azure Function transforms the message; the message is saved to another Service Bus Queue for batch processing; Azure Monitor logs processing status; a time-triggered Azure Function performs batch processing; a final Azure Function sends processed records to the System; reconciliation API records processing status; dead-letter handling is used on failure.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx
