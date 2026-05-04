---
id: PATT-INT-005
title: Consumer Pattern 4 - Enterprise API to System : Asynchronous
type: pattern
status: draft
owner: crisAI
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, enterprise-api, asynchronous
related: []
---

## Source
- Title: Consumer Pattern 4
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx

## Design overview
- Pattern name: Enterprise API to System : Asynchronous
- Description: Send events received on the Enterprise API to the target system asynchronously.
- Version: 0.1
- Status: APPROVED
- Date: 30 March 2023
- Classification: Consumer pattern
- Source: Enterprise API
- Target: System (API/DB/File)
- Delivery: Asynchronous
- Core pattern: Yes
- NFRs: observability with standard logging and correlation IDs; reconciliation no; reliability yes with retry and dead letter queue; SLA guidance required; volumetric capacity depends on interface usage and concurrency; operational limits include payload and runtime thresholds.
- Security constraints: for communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account topics are open.

## When to use
- Use when consumer request data is collected over an enterprise API gateway and then processed asynchronously before being sent to the system.

## Implementation
- The scheduler event triggers the process to request data from the producer interface.
- The producer starts preparing data and once ready sends it over the consumer gateway.
- An event on the consumer gateway is captured and transformed into a system data model and sent to the system.
- If an error occurs while publishing to the system, the message is pushed back to an internal queue for reprocessing.
- Physical implementation on AWS: CloudWatch Scheduler triggers Lambda; Lambda calls the Enterprise API; the callback is received asynchronously over API Gateway; the message is saved to SQS; SQS triggers Lambda; Lambda processes and sends it to the system; the outcome is logged in CloudWatch.
- Physical implementation on Azure: Time Trigger service triggers Azure Function; Azure Function calls the Enterprise API; the callback is received asynchronously over API Management; the message is saved to Service Bus Queue; the queue triggers Azure Function; the function processes and sends it to the system; the outcome is logged in Azure Monitor.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx
