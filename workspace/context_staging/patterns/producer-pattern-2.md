---
id: PATT-INT-007
title: Producer Pattern 2 - System to Enterprise Channel: Batch Synchronous
type: pattern
status: draft
owner: Design Author
last_reviewed: 2026-05-04
applies_to: integration
tags: producer, enterprise-channel, batch, synchronous, system, integration
related: []
---

## Source
- Title: Producer Pattern 2 — EA it-architecture
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx

## Design overview
- Name: System to Enterprise Channel - Batch Synchronous
- Version: 0.1
- Status: APPROVED
- Date: 21 March 2023
- Classification: Producer pattern; source: System (API/DB/File); target: Enterprise Channel; invocation: Batch; delivery: Synchronous; core pattern: No
- NFRs: observability; reconciliation: Yes; reliability; SLA guidance; volumetric guidance; operational limits
- Security: For communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account items are open topics

## When to use
- Use when a scheduled event fetches data from a System, translates it to Enterprise Data Model, and publishes it to the Enterprise Channel.
- Example use case: a scheduled event queries the UPI system to identify changes to user roles and publishes messages accordingly.

## Implementation
- Trigger molecule: Scheduled Event
- Processing molecule: Convert to Enterprise Data Model
- Connector molecule: Fetch from System; Fetch and Combine Watermark
- Publish molecule: Send to Channel
- AWS physical implementation: CloudWatch Scheduler triggers Lambda; Lambda fetches credentials from AWS Secrets Manager; Lambda calls the System; the outcome is logged to CloudWatch; Lambda publishes to SNS; SNS distributes to subscriptions; Lambda calls reconciliation API; dead-letter handling is used on failure.
- Azure physical implementation: Time Trigger service triggers Azure Function; Azure Function fetches credentials from Azure Key Vault; Azure Function calls the System; the outcome is logged to Azure Monitor; Azure Function publishes to Event Grid; Event Grid distributes to subscriptions; the Function calls reconciliation API; dead-letter handling is used on failure.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx
