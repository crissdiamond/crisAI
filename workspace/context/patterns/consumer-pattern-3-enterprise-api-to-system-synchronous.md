---
id: PATT-INT-004
title: Consumer Pattern 3 - Enterprise API to System: Synchronous
type: pattern
status: reviewed
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, synchronous, enterprise-api, system
related: []
---

## Design overview
- Name: Enterprise API to System: Synchronous
- Description: Send events received on the Enterprise API to the target system synchronously.
- Version / status / date: Version 0.1; Status APPROVED; Date 30 March 2023.
- Classification: Consumer pattern; Source Enterprise API; Target System (API/DB/File); Delivery Synchronous; Core Pattern Yes.

## When to use
- Use when data is received from the Enterprise API and must be sent to the target system in the same transaction.
- Use when the request is initiated on a scheduled trigger and the response must be handled synchronously.
- Use when retry and dead-letter handling are required for the downstream system call.

## Implementation
- The scheduled event triggers the Fetch from System molecule to synchronously send a request and receive a response payload.
- The payload from API is transformed into a system data model and sent to the System.
- If an error occurs while pushing the message to the System, the message is pushed back to the internal queue for reprocessing.
- Physical implementation on AWS uses CloudWatch Scheduler, Lambda, SQS, API Gateway, and the Reconciliation API.
- Physical implementation on Azure uses Time Trigger service, Azure Function, Service Bus Queue, API Management, and Azure Monitor.

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
- Title: Consumer Pattern 3
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx
- graph_site_id: liveuclac.sharepoint.com,333b8e95-f1ea-4007-a9a1-7181b5aeffaa,294849b5-8e5a-4992-8a50-d8274e79dae5
- graph_page_id: 7a89407d-a36b-4bdb-a63b-361bc8a5a632

## References
- None stated on the fetched page.
