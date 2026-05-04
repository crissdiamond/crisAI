---
id: PATT-INT-007
title: Producer Pattern 2 - System to Enterprise Channel : Batch Synchronous
type: pattern
status: draft
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, producer, channel, batch, synchronous
related: []
---

## Source
- Title: Producer Pattern 2
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx

## Design overview
- Pattern name: System to Enterprise Channel : Batch Synchronous.
- Description: fetch data from the system on a scheduled basis and send it over the Enterprise Channel synchronously.
- Classification: producer pattern.
- Physical implementation mentions a scheduled event, SNS or Event Grid, and a Dead Letter Queue.

## When to use
- Use when batch-oriented data extraction from a system is required and synchronous delivery over the Enterprise Channel is acceptable.

## Implementation
- A scheduled event initiates the flow.
- Data is fetched from the system.
- The data is sent over the Enterprise Channel synchronously.
- Physical components mentioned: scheduled event, SNS or Event Grid, Dead Letter Queue.

## Anti-patterns or when not to use
- Not stated in the source.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx