---
id: PATT-INT-002
title: Consumer Pattern 1 - Enterprise Channel to System: Synchronous
type: pattern
status: reviewed
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, synchronous, enterprise-channel, system
related: []
---

## Design overview
- Name: Enterprise Channel to System: Synchronous
- Description: Send events received on the Enterprise Channel to the target system synchronously.
- Version / status / date: Version 0.1; Status APPROVED; Date 21 March 2023.
- Classification: Consumer pattern; Source Enterprise Channel; Target System (API/DB/File); Delivery Synchronous; Core Pattern Yes.

## When to use
- Use when an event arrives on the Enterprise Channel and must be transformed and sent to the target system in the same flow.
- Use when the target system is reached via API, database, or file exchange.
- Use when retry, dead-letter handling, and reconciliation are required for channel-originated data.

## Implementation
- The event arriving on the Enterprise Channel triggers the integration flow.
- The payload from the channel is transformed into a system-specific data model.
- The payload is passed to the System via API/DB/File.
- If an error occurs while pushing the message to the System, the message is pushed back to the Enterprise Channel queue for reprocessing.
- Physical implementation on AWS uses SQS, Lambda, CloudWatch, and a Reconciliation API.
- Physical implementation on Azure uses Service Bus Queue, Azure Function, Azure Monitor, and a Reconciliation API.

## NFRS
- Observability: standard logging framework and correlation IDs for traceability.
- Reconciliation: yes, to maintain integrity because this pattern reads data from the Enterprise Channel.
- Reliability: retry is incorporated; failed messages after retry are saved to a dead letter queue for reprocessing.
- SLA: refer to guidelines to calculate SLA.
- Volumetric: interface usage expectations and concurrency on compute services determine sizing; stress-test is required.
- Operational limits: payload request 256 KB on AWS, 256 KB on Azure consumption tier, 100 MB on Azure Premium Tier; max supported runtime 15 mins on AWS and 10 mins on Azure.

## Anti-patterns or when not to use
- Not stated on the fetched page for this subsection.

## Source
- Title: Consumer Pattern 1
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx
- graph_site_id: liveuclac.sharepoint.com,333b8e95-f1ea-4007-a9a1-7181b5aeffaa,294849b5-8e5a-4992-8a50-d8274e79dae5
- graph_page_id: d9871155-48d8-41a1-a571-ea058b82e014

## References
- None stated on the fetched page.
