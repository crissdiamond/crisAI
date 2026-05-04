---
id: PATT-INT-006
title: Producer Pattern 1 - System to Enterprise API: onDemand Synchronous
type: pattern
status: reviewed
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, producer, synchronous, enterprise-api, system
related: []
---

## Design overview
- Name: System to Enterprise API - onDemand Synchronous
- Description: Send requested data to consumer over Enterprise API synchronously.
- Version / status / date: Version 0.1; Status APPROVED; Date 21 March 2023.
- Classification: Producer pattern; Source System (API/DB/File); Target Enterprise API; Invocation Synchronous; Core Pattern Yes.

## When to use
- Use when a consumer sends a request to the producer gateway using enterprise standard authentication and needs an enterprise-modelled response in the same call.
- Use for application integration where there is an end user session.
- Use for enrichment scenarios that require the producer system to provide additional information in response to a request.

## Implementation
- The pattern takes a request from the consumer, models it into system data model, and invokes the system API.
- The response from System is translated into Enterprise Data Model and sent to Enterprise API.
- If an error occurs during the process, it is modelled and sent into a standard error response.
- Physical implementation on AWS uses API Gateway, Lambda, Secrets Manager, CloudWatch, and the downstream system.
- Physical implementation on Azure uses API Management, Azure Function, Key Vault, Azure Monitor, and the downstream system.

## NFRS
- Observability: standard logging framework and correlation IDs for traceability.
- Reconciliation: no; communication is completed in the same transaction and producer and consumer remain connected.
- Reliability: retry is incorporated while sending to the System; failed messages are not saved to dead letter because error response is communicated synchronously to the requestor.
- SLA: refer to guidelines to calculate SLA.
- Volumetric: interface usage expectations and compute concurrency determine sizing; stress-test is required.
- Operational limits: payload request 10 MB on AWS and 1 GiB on Azure; max supported runtime 30 secs on both AWS and Azure.

## Anti-patterns or when not to use
- Not stated on the fetched page for this subsection.

## Source
- Title: Producer Pattern 1
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx
- graph_site_id: liveuclac.sharepoint.com,333b8e95-f1ea-4007-a9a1-7181b5aeffaa,294849b5-8e5a-4992-8a50-d8274e79dae5
- graph_page_id: c0f9b712-4102-4da9-b552-7f8d6687ae98

## References
- None stated on the fetched page.
