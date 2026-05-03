---
id: PATT-INT-006
title: Consumer Pattern 1 - Enterprise Channel to System: Synchronous
type: pattern
status: draft
owner: Enterprise Architecture
last_reviewed: 2026-05-03
applies_to: all
tags: integration, consumer-pattern, enterprise-channel, synchronous, system-integration
related: []
---

## Source
- Page title: Consumer Pattern 1
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx

## Summary
### Design overview
- Name: Enterprise Channel to System: Synchronous.
- Description: send events received on the Enterprise Channel to the target system synchronously.
- Version: 0.1; status: APPROVED; date: 21 March 2023.

### Tagging
- Classification: consumer pattern; source: Enterprise Channel; target: System (API/DB/File).
- Delivery: synchronous (this is the pattern’s delivery classification to the target System).

### Description
- The event arriving on the Enterprise Channel is transformed to a System Data Model and sent to the target System.
- The flow is triggered by an event arriving on the Enterprise Channel.
- The payload from the channel is transformed into a System-specific data model.
- The payload is passed to the System via API, DB, File, or similar.
- If an error occurs while pushing the message to the System, the message is pushed back to the Enterprise Channel queue for reprocessing.

### Non-functional requirements (from source)
- Observability: standard logging framework; use correlation IDs for traceability.
- Reconciliation: yes — to maintain integrity of the systems involved; the page states this is because the pattern reads data from the Enterprise Channel, i.e. asynchronous mode of information exchange (NFR rationale is about the channel interaction, not the **Delivery** tagging above).
- Reliability: retry when sending to the System; failed messages after retry go to a dead letter queue for reprocessing.
- Operational limits: payload and runtime caps apply (e.g. max invocation payload and max supported runtime as stated on the page for AWS/Azure).

### Security (from source)
- For communication within AWS, use IAM permissions implemented using Terraform.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx
