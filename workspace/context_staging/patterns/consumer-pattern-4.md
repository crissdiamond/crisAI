---
id: PATT-INT-005
title: Consumer Pattern 4 - Enterprise API to System: Asynchronous
type: pattern
status: draft
owner: Design Author
last_reviewed: 2026-05-04
applies_to: integration
tags: consumer, enterprise-api, asynchronous, system, integration
related: []
---

## Source
- Title: Consumer Pattern 4 — EA it-architecture
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx

## Design overview
- Name: Enterprise API to System : Asynchronous
- Version: 0.1
- Status: APPROVED
- Date: 30 March 2023
- Classification: Consumer pattern; source: Enterprise API; target: System (API/DB/File); delivery: Asynchronous; core pattern: Yes
- NFRs: observability; reconciliation: No; reliability; SLA guidance; volumetric guidance; operational limits
- Security: For communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account items are open topics

## When to use
- Use when Consumer request data is requested from a Producer interface, then transformed into a System data model and sent to the System asynchronously.

## Implementation
- Trigger molecule: Scheduled Event; Request Data
- Processing molecule: Receive Request; Convert to System Data Model
- Connector molecule: Send to System
- AWS physical implementation: CloudWatch scheduler triggers Lambda; Lambda calls Enterprise API; callback data is saved to SQS; SQS triggers Lambda for processing; Lambda sends payload to System; outcome is logged in CloudWatch.
- Azure physical implementation: Time Trigger service triggers Azure Function; Azure Function calls Enterprise API; callback data is saved to Service Bus Queue; queue triggers Azure Function for processing; Azure Function sends payload to System; outcome is logged in Azure Monitor.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx
