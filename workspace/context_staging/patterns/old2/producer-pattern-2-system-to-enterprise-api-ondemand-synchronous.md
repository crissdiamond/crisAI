---
id: PATT-INT-006
title: Producer Pattern 2 - System to Enterprise API: onDemand Synchronous
type: pattern
status: draft
owner: Publisher
last_reviewed: 2026-05-03
applies_to: crisAI architecture context
tags: integration, producer, enterprise-api, synchronous, draft
related: []
---

## Source
- Title: Ingestion Pattern 2
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-2.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-2.aspx

## Design overview
- Name: System to Enterprise API - onDemand Synchronous.
- Description: Send requested data to consumer over Enterprise API synchronously.
- Version / status / date: Version 0.1; APPROVED; 21 March 2023.
- Classification: Producer pattern; Source System (API/DB/File); Target Enterprise API; Invocation Synchronous; Core Pattern Yes.
- NFRs: Observability uses the standard logging framework and correlation IDs for traceability.
- NFRs: Reconciliation is not required because communication is completed in the same transaction and producer and consumer remain connected.
- NFRs: Reliability is supported by retry; failed messages are not saved to Dead Letter because the error response is communicated synchronously to the requestor.
- NFRs: SLA should refer to guidelines for calculation.
- NFRs: Volumetric expectations vary from a few records a day to thousands of records per minute; a thorough stress-test is required to finalise concurrency.
- NFRs: Operational limits include max invocation payload request of 10 MB on AWS and 1 GiB on Azure; max supported runtime of 30 secs on AWS and 30 secs on Azure.
- Security: For communication within AWS, use IAM permissions implemented using Terraform.
- Security: For cross-cloud and cross-account scenarios within the same cloud, the page marks both as open topics.
- Implementation: AWS uses API Gateway, Lambda, Secrets Manager, CloudWatch, and a downstream system.
- Implementation: Azure uses API Management, Azure Function, Key Vaults, Azure Monitor, and a downstream system.

## References
- [Ingestion Pattern 2](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-2.aspx)
