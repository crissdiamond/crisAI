---
id: PATT-INT-003
title: Producer and consumer flows
type: pattern
status: draft
owner: Enterprise Architecture
last_reviewed: 2026-05-03
applies_to: all
tags: integration, producer, consumer, flows, architecture
related: []
---

## Source
- Page title: Producer and consumer flows
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/producer-and-consumer-flows.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/producer-and-consumer-flows.aspx

## Summary
- The historical approach to integrations at UCL was point-to-point.
- Point-to-point integrations created lack of clear ownership, poor maintainability, and duplication of effort.
- The strategy separates integrations into two distinct flows: producers and consumers.
- Producers own the complete producer flow, including design, development, testing, deployment, support, improvement, maintenance, and data transformations.
- Consumers own the complete consumer flow, including design, development, testing, deployment, support, improvement, maintenance, and data transformations.
- Producer flows are technology agnostic and use the enterprise data model.
- Producer flows end in an enterprise API or enterprise distribution channel.
- Consumer flows start from an enterprise API or enterprise distribution channel.
- For consumers, APIs are preferred for application integrations.
- For consumers, distribution channels are preferred for system integrations.
- Consumers should encapsulate consumer-specific business and transformation logic within the consumer flow.
- Consumers should only use integration platform capabilities when the consumer system does not support them.
- Consumers should follow the published guidelines and standards to minimise load, impact, and costs on producers.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/producer-and-consumer-flows.aspx
