---
id: PATT-INT-008
title: Consumer Pattern 3 - Enterprise API to System: Synchronous
type: pattern
status: draft
owner: Enterprise Architecture
last_reviewed: 2026-05-03
applies_to: all
tags: integration, consumer-pattern, enterprise-api, synchronous, system-integration
related: []
---

## Source
- Page title: Consumer Pattern 3
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx

## Summary
- The pattern is approved and dated 30 March 2023.
- Source is Enterprise API and target is System (API/DB/File).
- Delivery is synchronous.
- The producer delivers the requested data to the consumer endpoint, which is transformed and sent to the System synchronously.
- A scheduled event triggers the fetch from System molecule to synchronously send the request and receive a response payload.
- The payload is transformed into a System Data Model and sent to the System.
- If an error occurs while pushing the message to the System, the message is pushed back to the internal queue for reprocessing.
- Observability uses the standard logging framework and correlation IDs.
- Reconciliation is not required because communication is completed in the same transaction.
- Reliability includes retry and a dead letter queue for reprocessing.
- Operational limits include payload size and supported runtime thresholds.
- Security within AWS uses IAM permissions implemented using Terraform.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx
