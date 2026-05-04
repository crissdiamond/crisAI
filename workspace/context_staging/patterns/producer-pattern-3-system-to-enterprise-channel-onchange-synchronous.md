---
id: PATT-INT-008
title: Producer Pattern 3 - System to Enterprise Channel : onChange Synchronous
type: pattern
status: draft
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, producer, channel, onchange, synchronous
related: []
---

## Source
- Title: Producer Pattern 3
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx

## Design overview
- Pattern name: System to Enterprise Channel : onChange Synchronous.
- Description: system events are received and sent over the Enterprise Channel synchronously when an object state changes.
- Classification: producer pattern.
- Physical implementation mentions webhook, API Gateway, queue, publish to Enterprise Channel, and Dead Letter Queue.

## When to use
- Use when change events from a system should be published to the Enterprise Channel as they occur.

## Implementation
- A system event is received.
- The event is sent over the Enterprise Channel synchronously.
- The flow is based on a change in object state.
- Physical components mentioned: webhook, API Gateway, queue, publish to Enterprise Channel, Dead Letter Queue.

## Anti-patterns or when not to use
- Not stated in the source.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx