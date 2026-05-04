---
id: PATT-INT-004
title: Consumer Pattern 3 - Enterprise API to System: Synchronous
type: pattern
status: draft
owner: Architecture
last_reviewed: 2026-05-04
applies_to: all
tags: integration, consumer, enterprise-api, synchronous
related: []
---

## Source
- Page title: Consumer Pattern 3
- Web URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx
- Open URL: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx

## Design overview
- Name: Enterprise API to System: Synchronous
- Description: Send events received on the Enterprise API to the target system synchronously.
- Version / status / date: Version 0.1; APPROVED; 30 March 2023.
- Classification: Consumer pattern; Source: Enterprise API; Target: System (API/DB/File); Delivery: Synchronous; Core Pattern: Yes.
- NFRs: Observability yes, with standard logging and correlation IDs. Reconciliation no, because communication is completed in the same transaction. Reliability yes, with retry and dead letter queue. SLA and volumetric guidance are referenced. Operational limits are stated.
- Security: For communication within AWS, use IAM permissions implemented using Terraform. Cross-cloud and cross-account topics are marked open.

## When to use
- For synchronous request/response integration from Enterprise API into a target System.

## Implementation
- The Producer delivers requested data to the Consumer endpoint, which is transformed and sent to the System synchronously.
- The scheduled event triggers a fetch-from-System step to synchronously send a request and receive a response payload.
- The payload is transformed into a System Data Model and sent to the System.
- If an error occurs while pushing to the System, the message is pushed back to an internal queue for reprocessing.
- AWS implementation: CloudWatch scheduler triggers Lambda, the API call returns in the same session, the response is logged, and Lambda sends onward to the System.
- Azure implementation: Time Trigger starts Azure Function, the API call returns in the same session, the response is logged, and Azure Function sends onward to the System.

## References
- [Integration patterns](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/integration-patterns.aspx)
- [Consumer Pattern 3](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx)
