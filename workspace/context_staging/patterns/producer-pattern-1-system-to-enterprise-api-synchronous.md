---
id: PATT-INT-006
title: Producer Pattern 1 - System to Enterprise API : onDemand Synchronous
type: pattern
status: draft
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, producer, api, ondemand, synchronous
related: []
---

## Source
- Title: Producer Pattern 1
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx

## Design overview
- Pattern name: System to Enterprise API : onDemand Synchronous.
- Description: send requested data to a consumer over Enterprise API synchronously.
- Classification: producer pattern.
- Source: system.
- Target: consumer.
- Delivery: synchronous.
- Physical implementation mentions API Gateway, Lambda, Secrets Manager, and CloudWatch.

## When to use
- Use when a consumer requests data from a system over an Enterprise API and synchronous delivery is needed.

## Implementation
- A request from the consumer is received.
- The system sends the requested data over the Enterprise API.
- The request is handled synchronously.
- Physical components mentioned: API Gateway, Lambda, Secrets Manager, CloudWatch.

## Anti-patterns or when not to use
- Not stated in the source.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx