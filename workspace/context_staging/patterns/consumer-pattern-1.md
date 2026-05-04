---
id: PATT-INT-002
title: Consumer Pattern 1 - Enterprise Channel to System: Synchronous
type: pattern
status: draft
owner: Design Author
last_reviewed: 2026-05-04
applies_to: integration
tags: consumer, enterprise-channel, synchronous, system, integration
related: []
---

## Source
- Title: Consumer Pattern 1 — EA it-architecture
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx

## Design overview
- Name: Enterprise Channel to System: Synchronous
- Version: 0.1
- Status: APPROVED
- Date: 21 March 2023
- Classification: Consumer pattern; source: Enterprise Channel; target: System (API/DB/File); delivery: Synchronous; core pattern: Yes
- NFRs: observability; reconciliation: Yes; reliability; SLA guidance; volumetric guidance; operational limits
- Security: For communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account items are open topics

## When to use
- Use when an event arriving on the Enterprise Channel must be transformed to a System data model and sent to the target System synchronously.
- Example use cases were not stated.

## Implementation
- Trigger molecule: Fetch Event
- Processing molecule: Convert to System Data Model
- Connector molecule: Send to System
- AWS physical implementation: SQS queue receives message; Lambda is triggered; message is processed; request is formed; Lambda sends request to System; outcome is logged in CloudWatch; reconciliation API records processing status; errors after retry go to Dead Letter Queue.
- Azure physical implementation: Service Bus Queue receives message; Azure Function is triggered; message is processed; request is formed; Azure Function sends request to System; outcome is logged in Azure Monitor; reconciliation API records processing status; errors after retry go to Dead Letter Queue.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx
