---
id: PATT-INT-005
title: Enterprise endpoints
type: pattern
status: draft
owner: Enterprise Architecture
last_reviewed: 2026-05-03
applies_to: all
tags: integration, endpoints, api, distribution-channel, architecture
related: []
---

## Source
- Page title: Enterprise endpoints
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Enterprise-endpoints.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Enterprise-endpoints.aspx

## Summary
- The strategy addresses legacy integration technologies such as DB links and ETL tools.
- These legacy technologies lower operational efficiency and security, and increase technical debt.
- Heavy reliance on niche skillsets increases delivery risk for reliable services.
- Real-time processing is not fully supported, and near real-time patterns are labour intensive and complex.
- Overnight batch processing and synchronisation create disconnected user experiences across the UCL digital ecosystem.
- Two modern approaches are introduced: Enterprise APIs and Enterprise distribution channels.
- Enterprise APIs use the RESTful architecture.
- Enterprise APIs are synchronous and support instant feedback between applications.
- Enterprise APIs are the recommended integration approach for application integration.
- Enterprise APIs expose data conforming to the UCL EDM.
- Enterprise APIs use a standard approach to authentication and authorisation.
- Enterprise distribution channels are asynchronous and event-driven.
- Enterprise distribution channels are the recommended integration approach for system integration.
- Enterprise distribution channels expose data conforming to the UCL EDM.
- Enterprise distribution channels use a standard approach to authentication and authorisation.
- Having both synchronous and asynchronous endpoints supports all consumer patterns and use cases for application and system integrations.
- Product and platform teams are empowered to choose the best pattern for each use case.
- The approach focuses on agility and scalability.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Enterprise-endpoints.aspx
