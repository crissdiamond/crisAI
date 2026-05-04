---
id: PATT-INT-005
title: Consumer Pattern 4 - Enterprise API to System: Asynchronous
type: pattern
status: reviewed
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, asynchronous, enterprise-api, system
related: []
---

## Design overview
- Name: Enterprise API to System: Asynchronous
- Description: Send events received on the Enterprise API to the target system asynchronously.
- Version / status / date: Version 0.1; Status APPROVED; Date 30 March 2023.
- Classification: Consumer pattern; Source Enterprise API; Target System (API/DB/File); Delivery Asynchronous; Core Pattern Yes.

## When to use
- Use when a consumer requests data from a producer and waits for the producer to send the requested data over a gateway.
- Use when the returned data must be transformed into a system data model before delivery to the target system.
- Use when retry and dead-letter handling are required for downstream delivery.

## Implementation
- The scheduler event triggers the process to request data from the Producer Interface.
- The Producer starts preparing data and once data is ready it sends it over the consumer gateway.
- An event on the consumer gateway is captured, transformed into a system data model, and sent to the System.
- If an error occurs while publishing to System, the message is pushed back to the internal queue for reprocessing.
- Physical implementation on AWS uses CloudWatch Scheduler, Lambda, SQS, API Gateway, and the Reconciliation API.
- Physical implementation on Azure uses Time Trigger Service, Azure Function, Service Bus Queue, API Management, and Azure Monitor.

## NFRS
- Observability: standard logging framework and correlation IDs for traceability.
- Reconciliation: no; communication is completed in the same transaction and producer and consumer remain connected.
- Reliability: retry is incorporated; failed messages after retry are saved to a dead letter queue for reprocessing.
- SLA: refer to guidelines to calculate SLA.
- Volumetric: interface usage expectations and compute concurrency determine sizing; stress-test is required.
- Operational limits: payload request 256 KB on AWS, 256 KB on Azure consumption tier, 100 MB on Azure Premium Tier; max supported runtime 15 mins on AWS and 10 mins on Azure.

## Anti-patterns or when not to use
- Not stated on the fetched page for this subsection.

## Source
- Title: Consumer Pattern 4
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx
- graph_site_id: liveuclac.sharepoint.com,333b8e95-f1ea-4007-a9a1-7181b5aeffaa,294849b5-8e5a-4992-8a50-d8274e79dae5
- graph_page_id: 1febd31e-eff5-4d46-8a3f-7cf8b055bb58

## References
- None stated on the fetched page.
