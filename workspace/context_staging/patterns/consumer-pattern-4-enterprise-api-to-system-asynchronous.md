---
id: PATT-INT-005
title: Consumer Pattern 4 - Enterprise API to System: Asynchronous
type: pattern
status: draft
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, enterprise-api, asynchronous
related: []
---

## Source
- Page title: Consumer Pattern 4
- Web URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx
- Open URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx

## Design overview
- Name: Enterprise API to System: Asynchronous
- Description: Send events received on the Enterprise API to the target system asynchronously.
- Version / status / date: Version 0.1; APPROVED; 30 March 2023.
- Classification: Consumer pattern; Source: Enterprise API; Target: System (API/DB/File); Delivery: Asynchronous; Core Pattern: Yes.
- NFRs: Observability yes, with standard logging and correlation IDs. Reconciliation no. Reliability yes, with retry and dead letter queue. SLA and volumetric guidance are referenced. Operational limits are stated.
- Security: For communication within AWS, use IAM permissions implemented using Terraform. Cross-cloud and cross-account topics are marked open.

## When to use
- For asynchronous request/reply integration where the consumer requests data from the producer and later forwards it to the System.

## Implementation
- The Consumer requests data from the producer and waits for the producer to send the data over a gateway.
- The event on the consumer gateway is captured, transformed into a System Data Model, and sent to the System.
- If an error occurs while publishing to the System, the message is pushed back to an internal queue for reprocessing.
- AWS implementation: CloudWatch scheduler triggers Lambda, the producer callback arrives asynchronously, the payload is saved to SQS, Lambda processes it, and status is logged to CloudWatch.
- Azure implementation: Time Trigger starts Azure Function, the producer callback arrives asynchronously, the payload is saved to Service Bus, Azure Function processes it, and status is logged to Azure Monitor.

## References
- [Integration patterns](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/integration-patterns.aspx)
- [Consumer Pattern 4](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx)
