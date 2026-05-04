---
id: PATT-INT-003
title: Consumer Pattern 2 - Enterprise Channel to System: Asynchronous
type: pattern
status: reviewed
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, asynchronous, enterprise-channel, system
related: []
---

## Design overview
- Name: Enterprise Channel to System: Asynchronous
- Description: Send events received on the Enterprise Channel to the target System asynchronously.
- Version / status / date: Version 0.1; Status APPROVED; Date 30 March 2023.
- Classification: Consumer pattern; Source Enterprise Channel; Target System (API/DB/File); Delivery Asynchronous; Core Pattern Yes.

## When to use
- Use when events received from the Enterprise Channel are transformed, queued, and sent to the target system on a scheduled basis.
- Use when batch processing is required after the initial capture of channel events.
- Use when retry and dead-letter handling are needed for target-system communication.

## Implementation
- The event on the Enterprise Channel triggers the flow.
- The payload from the Enterprise Channel is transformed into a system data model.
- The payload is saved to a queue.
- A separate scheduler triggers subsequent processing at configured frequency intervals.
- It reads all saved messages and sends them to the target System via API/DB/File.
- If an error occurs while communicating with the target System, the message is pushed back to the queue for reprocessing.
- Physical implementation on AWS uses SQS, Lambda, CloudWatch, and a batch-processing Lambda.
- Physical implementation on Azure uses Service Bus Queue, Azure Function, Azure Monitor, and a Time Trigger service.

## NFRS
- Observability: standard logging framework with correlation ID in logs for tracing.
- Reconciliation: yes, to maintain the integrity of the systems involved because this pattern reads data from the Enterprise Channel.
- Reliability: retry is incorporated; failed messages after retry are saved to a dead letter queue for reprocessing.
- SLA: refer to guidelines to calculate SLA.
- Volumetric: interface usage expectations and compute concurrency determine sizing; stress-test is required.
- Operational limits: payload request 256 KB on AWS, 256 KB on Azure consumption tier, 100 MB on Azure Premium Tier; max supported runtime 15 mins on AWS and 10 mins on Azure.

## Anti-patterns or when not to use
- Not stated on the fetched page for this subsection.

## Source
- Title: Consumer Pattern 2
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx
- graph_site_id: liveuclac.sharepoint.com,333b8e95-f1ea-4007-a9a1-7181b5aeffaa,294849b5-8e5a-4992-8a50-d8274e79dae5
- graph_page_id: 314a9795-a4f6-40b7-94c0-aaf05985ec14

## References
- None stated on the fetched page.
