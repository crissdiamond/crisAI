---
id: PATT-INT-005
title: Consumer Pattern 4 - Enterprise API to System : Asynchronous
type: pattern
status: draft
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, enterprise-api, asynchronous
related: []
---

## Source
- Title: Consumer Pattern 4
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx

## Design overview
- Pattern name: Enterprise API to System : Asynchronous.
- Description: a scheduler event requests data from the Producer Interface and transforms it into the System Data Model.
- Classification: consumer pattern.
- Physical implementation includes API Gateway, API Management, asynchronous callbacks, and Dead Letter Queue.

## When to use
- Use when a scheduler-driven request to a producer interface must be handled asynchronously.

## Implementation
- A scheduler event requests data from the Producer Interface.
- The response is transformed into the System Data Model.
- Physical components mentioned: API Gateway, API Management, asynchronous callbacks, Dead Letter Queue.

## Anti-patterns or when not to use
- Not stated in the source.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx