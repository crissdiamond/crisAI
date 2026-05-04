---
id: PATT-INT-003
title: Consumer Pattern 3 - Enterprise API to System: Synchronous
type: pattern
status: draft
owner: Architecture
related: []
---

## Source
- [Consumer Pattern 3](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx)

## Design overview
- Name: Enterprise API to System: Synchronous
- Version: 0.1
- Status: APPROVED
- Date: 30 March 2023
- Classification: Consumer pattern
- Source: Enterprise API
- Target: System (API/DB/File)
- Delivery: Synchronous
- Core pattern: Yes
- Description: Send events received on the Enterprise API to the target system synchronously.

## When to use
- Use when a scheduled event must synchronously fetch from a producer interface and deliver to the target system.
- Use when the flow remains within the same transaction between request and response.

## Implementation
- A scheduled event triggers the fetch from system molecule to synchronously send a request and receive a response payload.
- The payload is transformed into a System data model and sent to the System.
- If an error occurs while pushing the message to the System, the message is pushed back to the internal queue for reprocessing.
- Solution overview includes API Gateway event, processing and connector molecules.
- Physical implementation notes for AWS use CloudWatch scheduler, Lambda, SQS and CloudWatch logging; Azure uses Time Trigger service, Azure Function, Service Bus Queue and Azure Monitor.

## Anti-patterns or when not to use
- Not suitable where the consumer expects an asynchronous callback style interaction.

## References
- [Consumer Pattern 3](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-3.aspx)
