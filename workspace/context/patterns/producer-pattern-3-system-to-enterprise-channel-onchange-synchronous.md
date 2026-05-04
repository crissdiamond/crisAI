---
id: PATT-INT-008
title: Producer Pattern 3 - System to Enterprise Channel: onChange Synchronous
type: pattern
status: reviewed
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, producer, onchange, synchronous, enterprise-channel, system
related: []
---

## Design overview
- Name: System to Enterprise Channel - onChange Synchronous
- Description: System events are received and sent over Enterprise Channel synchronously.
- Version / status / date: Version 0.1; Status APPROVED; Date 21 March 2023.
- Classification: Producer pattern; Source System (API/DB/File/Event); Target Enterprise Channel; Invocation onChange; Delivery Synchronous; Core Pattern Yes.

## When to use
- Use when a change in a source system should trigger a webhook-driven integration flow.
- Use when the changed object state must be modelled into the Enterprise Data Model and published to the Enterprise Channel.
- Use when dead-letter handling is required for publication failures.

## Implementation
- A change in System triggers an event via webhook to the Producer Gateway.
- The event is acknowledged and published to an internal queue.
- The event is read from the queue, modelled into Enterprise Data Model, and published to the configured Enterprise Channel.
- If an error occurs while publishing to the channel, the event is saved to Dead Letter for reprocessing.
- Physical implementation on AWS uses API Gateway, SQS, Lambda, SNS, CloudWatch, and a Reconciliation API.
- Physical implementation on Azure uses API Management, Service Bus Queue, Azure Function, Event Grid, Azure Monitor, and a Reconciliation API.

## NFRS
- Observability: standard logging framework and correlation IDs for traceability.
- Reconciliation: yes, to maintain the integrity of the systems involved because this pattern reads data from the Enterprise Channel.
- Reliability: retry is incorporated while sending to the System; failed messages after retry are saved to a dead letter queue for reprocessing.
- SLA: refer to guidelines to calculate SLA.
- Volumetric: interface usage expectations and compute concurrency determine sizing; stress-test is required.
- Operational limits: payload request 10 MB on AWS and 1 GB on Azure consumption tier; max supported runtime 15 mins on AWS and 10 mins on Azure.

## Anti-patterns or when not to use
- Not stated on the fetched page for this subsection.

## Source
- Title: Producer Pattern 3
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx
- graph_site_id: liveuclac.sharepoint.com,333b8e95-f1ea-4007-a9a1-7181b5aeffaa,294849b5-8e5a-4992-8a50-d8274e79dae5
- graph_page_id: 8016ebe5-b799-4422-aa40-fc519bb9ab0d

## References
- None stated on the fetched page.
