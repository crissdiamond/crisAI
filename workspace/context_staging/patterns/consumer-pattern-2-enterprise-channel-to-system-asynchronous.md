---
id: PATT-INT-004
title: Consumer Pattern 2 - Enterprise Channel to System: Asynchronous
type: pattern
status: draft
owner: Publisher
last_reviewed: 2026-05-03
applies_to: crisAI architecture context
tags: integration, consumer, enterprise-channel, asynchronous, reconciliation
related: []
---

## Source
- Title: Consumer Pattern 2
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx

## Design overview
- Name: Enterprise Channel to System : Asynchronous
- Description: Send events received on the Enterprise Channel to the target System asynchronously.
- Version / status / date: Version 0.1; APPROVED; 30 March 2023.
- Classification: Consumer pattern; Source Enterprise Channel; Target System (API/DB/File); Delivery Asynchronous; Core Pattern Yes.
- NFRs: Observability uses the standard logging framework and correlation ID in logs for tracing.
- NFRs: Reconciliation is required to maintain the integrity of the systems involved because the pattern reads data from the Enterprise Channel in asynchronous mode of information exchange.
- NFRs: Reliability is supported by retry; failed messages after retry are saved to a dead letter queue attached to the main queue for reprocessing.
- NFRs: SLA should refer to guidelines for calculation.
- NFRs: Volumetric expectations vary from a few records a day to thousands of records per minute; a thorough stress-test is required to conclude on concurrency configuration.
- NFRs: Operational limits include max invocation payload request of 256 KB on AWS, 256 KB on Azure consumption tier, and 100 MB on Azure Premium Tier; max supported runtime of 15 mins on AWS and 10 mins on Azure.
- Security: For communication within AWS, use IAM permissions implemented using Terraform.
- Security: For cross-cloud and cross-account scenarios within the same cloud, the page marks both as open topics.
- Implementation: AWS uses SQS, Lambda, CloudWatch, and a Reconciliation API.
- Implementation: Azure uses Service Bus, Azure Function, Azure Monitor, Time Trigger service, and a Reconciliation API.

## References
- [Consumer Pattern 2](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx)
