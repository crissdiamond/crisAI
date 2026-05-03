---
id: PATT-INT-007
title: Consumer Pattern 2 - Enterprise Channel to System: Asynchronous
type: pattern
status: draft
owner: Enterprise Architecture
last_reviewed: 2026-05-03
applies_to: all
tags: integration, consumer-pattern, enterprise-channel, asynchronous, system-integration
related: []
---

## Source
- Page title: Consumer Pattern 2
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx

## Summary
- The pattern is approved and dated 30 March 2023.
- Source is Enterprise Channel and target is System (API/DB/File).
- Delivery is asynchronous.
- The event arriving on the Enterprise Channel is transformed into a System Data Model and saved to a queue.
- Messages are consumed on a scheduled basis and sent to the target System after processing.
- Errors while communicating with the target System push the message back to the queue for reprocessing.
- Observability uses the standard logging framework and correlation IDs.
- Reconciliation is required because the pattern reads data from the Enterprise Channel in asynchronous mode of information exchange.
- Reliability includes retry and a dead letter queue for reprocessing.
- Operational limits include payload size and supported runtime thresholds.
- Security within AWS uses IAM permissions implemented using Terraform.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx
