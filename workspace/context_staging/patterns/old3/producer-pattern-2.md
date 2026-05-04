---
id: PATT-INT-007
title: Producer Pattern 2 - System to Enterprise Channel : Batch Synchronous
type: pattern
status: draft
owner: crisAI
last_reviewed: 2026-05-04
applies_to: all
tags: integration, producer, enterprise-channel, batch, synchronous
related: []
---

## Source
- Title: Producer Pattern 2
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx

## Design overview
- Pattern name: System to Enterprise Channel - Batch Synchronous
- Description: Fetch data from system on a scheduled basis and send over Enterprise Channel synchronously.
- Version: 0.1
- Status: APPROVED
- Date: 21 March 2023
- Classification: Producer pattern
- Source: System (API/DB/File)
- Target: Enterprise Channel
- Invocation: Batch
- Delivery: Synchronous
- Core pattern: No
- NFRs: observability with standard logging and correlation IDs; reconciliation yes; reliability yes with retry and dead letter queue; SLA guidance required; volumetric capacity depends on interface usage and concurrency; operational limits include payload and runtime thresholds.
- Security constraints: for communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account topics are open.

## When to use
- Use when a scheduled event must query a system and publish updates or additions to the Enterprise Channel.
- Use when the source system has no event-driven capability and near real-time behaviour is simulated by scheduling.

## Implementation
- A scheduled event triggers the data fetch from the system.
- The response from the system API is translated into Enterprise Data Model and published to the channel.
- If an error occurs while publishing to the Enterprise Channel, the message is saved to dead letter for reprocessing.
- Physical implementation on AWS: CloudWatch Scheduler triggers Lambda; Lambda fetches credentials from Secrets Manager; Lambda calls the system; the response is logged in CloudWatch; Lambda publishes to SNS for distribution; SNS distributes to subscriptions; Lambda calls the Reconciliation API; failures go to a dead letter queue.
- Physical implementation on Azure: Time Trigger service triggers Azure Function; the function fetches credentials from Key Vault; the function calls the system; the response is logged in Azure Monitor; the function publishes to Event Grid for distribution; Event Grid distributes to subscriptions; the function calls the Reconciliation API; failures go to a dead letter queue.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx
