---
id: PATT-INT-004
title: Consumer Pattern 3 - Enterprise API to System : Synchronous
type: pattern
status: draft
owner: crisAI
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, enterprise-api, synchronous
related: []
---

## Source
- Title: Consumer Pattern 3
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx

## Design overview
- Pattern name: Enterprise API to System : Synchronous
- Description: Send events received on the Enterprise API to the target system synchronously.
- Version: 0.1
- Status: APPROVED
- Date: 30 March 2023
- Classification: Consumer pattern
- Source: Enterprise API
- Target: System (API/DB/File)
- Delivery: Synchronous
- Core pattern: Yes
- NFRs: observability with standard logging and correlation IDs; reconciliation no; reliability yes with retry and dead letter queue; SLA guidance required; volumetric capacity depends on interface usage and concurrency; operational limits include payload and runtime thresholds.
- Security constraints: for communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account topics are open.

## When to use
- Use when data is requested over the Enterprise API and then synchronously transformed and sent to the target system.

## Implementation
- The scheduled event triggers the fetch from system molecule to synchronously send a request and receive a response payload.
- The payload from the API is transformed into a system data model and sent to the system.
- If an error occurs while pushing the message to the system, the message is pushed back to an internal queue for reprocessing.
- Physical implementation on AWS: CloudWatch Scheduler triggers Lambda; Lambda calls the Enterprise API; the received payload is published to SQS for reliability; SQS triggers Lambda; Lambda processes the payload and sends it to the system; the outcome is logged in CloudWatch.
- Physical implementation on Azure: Time Trigger service triggers Azure Function; the function calls the Enterprise API; the received payload is published to Service Bus Queue for reliability; the queue triggers Azure Function; the function processes the payload and sends it to the system; the outcome is logged in Azure Monitor.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx
