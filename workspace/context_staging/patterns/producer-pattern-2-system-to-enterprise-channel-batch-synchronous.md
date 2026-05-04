---
id: PATT-INT-007
title: Producer Pattern 2 - System to Enterprise Channel: Batch Synchronous
type: pattern
status: draft
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, producer, enterprise-channel, batch, synchronous
related: []
---

## Source
- Page title: Producer Pattern 2
- Web URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx
- Open URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx

## Design overview
- Name: System to Enterprise Channel - Batch Synchronous.
- Description: Fetch data from System on a scheduled basis and send over Enterprise Channel synchronously.
- Version / status / date: Version 0.1; APPROVED; 21 March 2023.
- Classification: Producer pattern; Source: System (API/DB/File); Target: Enterprise Channel; Invocation: Batch; Delivery: Synchronous; Core Pattern: No.
- NFRs: Observability yes, with standard logging and correlation IDs. Reconciliation yes. Reliability yes, with retry and dead letter queue. SLA and volumetric guidance are referenced. Operational limits are stated.
- Security: For communication within AWS, use IAM permissions implemented using Terraform. Cross-cloud and cross-account topics are marked open.

## When to use
- For scheduled extraction from a system to publish updates to the Enterprise Channel.
- Example use case is stated for a scheduled event querying UPI changes to user roles.

## Implementation
- A scheduled event triggers the data fetch from the System.
- The response from System API is translated into Enterprise Data Model and published to the channel.
- If an error occurs while publishing to the Enterprise Channel, the message is saved to Dead Letter for reprocessing.
- AWS implementation: CloudWatch Scheduler triggers Lambda, Lambda fetches credentials from Secrets Manager, calls the downstream system, logs to CloudWatch, publishes to SNS, and makes a reconciliation call.
- Azure implementation: Time Trigger starts Azure Function, Azure Function fetches credentials from Key Vault, calls the downstream system, logs to Azure Monitor, publishes to Event Grid, and makes a reconciliation call.

## References
- [Integration patterns](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/integration-patterns.aspx)
- [Producer Pattern 2](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx)
