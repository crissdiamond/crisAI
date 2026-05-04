---
id: PATT-INT-007
title: Producer Pattern 2 - System to Enterprise Channel: Batch Synchronous
type: pattern
status: reviewed
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, producer, batch, synchronous, enterprise-channel, system
related: []
---

## Design overview
- Name: System to Enterprise Channel - Batch Synchronous
- Description: Fetch data from System on scheduled basis and send over Enterprise Channel synchronously.
- Version / status / date: Version 0.1; Status APPROVED; Date 21 March 2023.
- Classification: Producer pattern; Source System (API/DB/File); Target Enterprise Channel; Invocation Batch; Delivery Synchronous; Core Pattern No.

## When to use
- Use when a scheduler is needed to fetch data from a system on a schedule and publish it to the Enterprise Channel.
- Use when the source system has no event-driven capability and near real-time behaviour is simulated through scheduled execution.
- Use when dead-letter handling is required for failed publication to the Enterprise Channel.

## Implementation
- A scheduled event triggers the data fetch from System.
- The response from System API is translated into Enterprise Data Model and published to channel.
- If an error occurs while publishing to the Enterprise Channel, the message is saved to Dead Letter for reprocessing.
- Physical implementation on AWS uses CloudWatch Scheduler, Lambda, Secrets Manager, SNS, Azure AD, and a Reconciliation API.
- Physical implementation on Azure uses Time Trigger service, Azure Function, Key Vault, Event Grid, Azure AD, and a Reconciliation API.

## NFRS
- Observability: standard logging framework and correlation IDs for traceability.
- Reconciliation: yes, to maintain the integrity of the systems involved because this pattern reads data from the Enterprise Channel.
- Reliability: retry is incorporated while sending to the System; failed messages after retry are saved to a dead letter queue attached to the main queue for reprocessing.
- SLA: refer to guidelines to calculate SLA.
- Volumetric: interface usage expectations and compute concurrency determine sizing; stress-test is required.
- Operational limits: payload request 256 KB on AWS, 256 KB on Azure standard tier, 100 MB on Azure Premium Tier; max supported runtime 15 mins on AWS and 10 mins on Azure.

## Anti-patterns or when not to use
- Not stated on the fetched page for this subsection.

## Source
- Title: Producer Pattern 2
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx
- graph_site_id: liveuclac.sharepoint.com,333b8e95-f1ea-4007-a9a1-7181b5aeffaa,294849b5-8e5a-4992-8a50-d8274e79dae5
- graph_page_id: 4cdc4bfb-b6e1-43ee-bb0f-54ee61aa7d5a

## References
- None stated on the fetched page.
