---
id: PATT-INT-004
title: Consumer Pattern 3 - Enterprise API to System: Synchronous
type: pattern
status: draft
owner: Design Author
last_reviewed: 2026-05-04
applies_to: integration
tags: consumer, enterprise-api, synchronous, system, integration
related: []
---

## Source
- Title: Consumer Pattern 3 — EA it-architecture
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx

## Design overview
- Name: Enterprise API to System : Synchronous
- Version: 0.1
- Status: APPROVED
- Date: 30 March 2023
- Classification: Consumer pattern; source: Enterprise API; target: System (API/DB/File); delivery: Synchronous; core pattern: Yes
- NFRs: observability; reconciliation: No; reliability; SLA guidance; volumetric guidance; operational limits
- Security: For communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account items are open topics

## When to use
- Use when the Producer delivers requested data to the Consumer endpoint, which is transformed and sent to the System synchronously.

## Implementation
- Trigger molecule: Scheduled Event; API Gateway Event
- Processing molecule: Convert to System Data Model
- Connector molecule: Send to System; Fetch from System
- AWS physical implementation: CloudWatch scheduler triggers Lambda; Lambda calls Enterprise API; payload is published to SQS for reliability; SQS triggers Lambda for transformation; Lambda sends payload to System; outcome is logged in CloudWatch.
- Azure physical implementation: Time Trigger service triggers Azure Function; Azure Function calls Enterprise API; payload is published to Service Bus Queue for reliability; queue triggers Azure Function for transformation; Azure Function sends payload to System; outcome is logged in Azure Monitor.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx
