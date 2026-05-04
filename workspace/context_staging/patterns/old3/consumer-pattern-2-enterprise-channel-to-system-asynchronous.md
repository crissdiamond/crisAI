---
id: PATT-INT-003
title: Consumer Pattern 2 - Enterprise Channel to System : Asynchronous
type: pattern
status: draft
owner: Design Author
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, channel, asynchronous
related: []
---

## Source
- Title: Consumer Pattern 2
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx

## Design overview
- Name: Enterprise Channel to System : Asynchronous.
- Description: send events received on the Enterprise Channel to the target system asynchronously.
- Classification: consumer pattern.

## When to use
- Use when events are received on the Enterprise Channel and the target system is to be called asynchronously.

## Implementation
- Input: events received on the Enterprise Channel.
- Action: send to the target system.
- Delivery mode: asynchronous.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx
