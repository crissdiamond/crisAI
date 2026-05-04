---
id: PATT-INT-004
title: Consumer Pattern 3 - Enterprise API to System : Synchronous
type: pattern
status: draft
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, enterprise-api, synchronous
related: []
---

## Source
- Title: Consumer Pattern 3
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx

## Design overview
- Pattern name: Enterprise API to System : Synchronous.
- Description: a scheduled event triggers a fetch-from-system flow and transforms the result into the System Data Model.
- Classification: consumer pattern.
- Physical implementation includes CloudWatch scheduler, Lambda, System Lambda, and Dead Letter Queue.

## When to use
- Use when a scheduled event needs to fetch data from a system and process it synchronously.

## Implementation
- A scheduler event triggers the flow.
- The flow fetches data from the system.
- The data is transformed into the System Data Model.
- Physical components mentioned: CloudWatch scheduler, Lambda, System Lambda, Dead Letter Queue.

## Anti-patterns or when not to use
- Not stated in the source.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx