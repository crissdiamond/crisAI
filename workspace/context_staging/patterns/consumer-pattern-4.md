---
id: PATT-INT-009
title: Consumer Pattern 4 - Enterprise API to System: Asynchronous
type: pattern
status: draft
owner: Enterprise Architecture
last_reviewed: 2026-05-03
applies_to: all
tags: integration, consumer-pattern, enterprise-api, asynchronous, system-integration
related: []
---

## Source
- Page title: Consumer Pattern 4
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx

## Summary
- The pattern is approved and dated 30 March 2023.
- Source is Enterprise API and target is System (API/DB/File).
- Delivery is asynchronous.
- The consumer requests data from the producer and waits for the producer to send requested data over a gateway.
- The event on the consumer gateway is captured, transformed into a System Data Model, and sent to the System.
- If an error occurs while publishing to the System, the message is pushed back to the internal queue for reprocessing.
- Observability uses the standard logging framework and correlation IDs.
- Reconciliation is not required because communication is completed in the same transaction.
- Reliability includes retry and a dead letter queue for reprocessing.
- Operational limits include payload size and supported runtime thresholds.
- Security within AWS uses IAM permissions implemented using Terraform.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx
