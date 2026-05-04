---
id: PATT-INT-005
title: Producer Pattern 1 - Application Database to Ingestion API
type: pattern
status: draft
owner: Publisher
last_reviewed: 2026-05-03
applies_to: crisAI architecture context
tags: integration, producer, ingestion, api, draft
related: []
---

## Source
- Title: Ingestion Pattern 1
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx

## Design overview
- Name: Database to Ingestion API.
- Description: Send application Delta Files using POST method to Data Lake.
- Version / status / date: Version 0.1; Draft; 07 Aug 2025.
- Classification: Producer pattern; Source Database (API/DB/File); Target Ingestion API; Invocation Synchronous; Core Pattern Yes.
- NFRs: Observability uses the standard logging framework and correlation IDs for traceability.
- NFRs: Reconciliation is not required.
- NFRs: Reliability is supported by retry; failed messages are not saved to Dead Letter because the error response is communicated synchronously to the requestor.
- NFRs: SLA should refer to guidelines for calculation.
- NFRs: Volumetric expectations vary from a few records a day to thousands of records per minute; a thorough stress-test is required to finalise concurrency.
- NFRs: Operational limits include max invocation payload request of 10 MB on AWS and 1 GiB on Azure; max supported runtime of 30 secs on AWS and 30 secs on Azure.
- Security: For communication within AWS, use IAM permissions implemented using Terraform.
- Security: For cross-cloud and cross-account scenarios within the same cloud, the page marks both as open topics.
- Implementation: AWS physical implementation is N/A.
- Implementation: Azure physical implementation is blank on the fetched page.

## References
- [Ingestion Pattern 1](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Ingestion-Pattern-1.aspx)
