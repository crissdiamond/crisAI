---
id: PATT-INT-002
title: Consumer Pattern 2 - Enterprise Channel to System: Asynchronous
type: pattern
status: draft
owner: Architecture
related: []
---

## Source
- [Consumer Pattern 2](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx)

## Design overview
- Name: Enterprise Channel to System: Asynchronous
- Version: 0.1
- Status: APPROVED
- Date: 30 March 2023
- Classification: Consumer pattern
- Source: Enterprise Channel
- Target: System (API/DB/File)
- Delivery: Asynchronous
- Core pattern: Yes
- Description: Send events received on the Enterprise Channel to the target System asynchronously.

## When to use
- Use when the Enterprise Channel payload should be stored and later consumed on a scheduled basis.
- Use when the target system is reached after queueing and batch-style processing.

## Implementation
- The event on the Enterprise Channel triggers the flow.
- The payload is transformed into a System data model and saved to a queue.
- A separate scheduler triggers subsequent processing at configured frequency intervals.
- Saved messages are read and sent to the target system via API, DB or file.
- If an error occurs while communicating with the target System, the message is pushed back to the queue for reprocessing.
- Solution overview includes a scheduled event trigger, a processing molecule and a connector molecule.
- Physical implementation notes for AWS use SQS, Lambda, CloudWatch and a reconciliation API; Azure uses Service Bus, Azure Functions, Azure Monitor and a reconciliation API.

## Anti-patterns or when not to use
- Not suitable where immediate synchronous delivery from the channel is required.

## References
- [Consumer Pattern 2](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-2.aspx)
