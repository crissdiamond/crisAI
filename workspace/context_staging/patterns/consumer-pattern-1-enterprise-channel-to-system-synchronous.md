---
id: PATT-INT-001
title: Consumer Pattern 1 - Enterprise Channel to System: Synchronous
type: pattern
status: draft
owner: Architecture
related: []
---

## Source
- [Consumer Pattern 1](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx)

## Design overview
- Name: Enterprise Channel to System: Synchronous
- Version: 0.1
- Status: APPROVED
- Date: 21 March 2023
- Classification: Consumer pattern
- Source: Enterprise Channel
- Target: System (API/DB/File)
- Delivery: Synchronous
- Core pattern: Yes
- Description: Send events received on the Enterprise Channel to the target system synchronously.

## When to use
- Use when an event on the Enterprise Channel must be transformed to a System data model and sent to the target system in the same flow.
- Use when the target system may be reached via API, database or file interface.

## Implementation
- The event arriving on the Enterprise Channel triggers the integration flow.
- The payload is transformed into a System-specific data model.
- The payload is passed to the System via API, DB or file.
- If an error occurs while pushing the message to the System, the message is pushed back to the Enterprise Channel queue for reprocessing.
- Solution overview includes a processing molecule to fetch event and convert to System data model, and a connector molecule to send to System.
- Physical implementation notes for AWS use SQS, Lambda, CloudWatch and a reconciliation API; Azure uses Service Bus, Azure Functions, Azure Monitor and a reconciliation API.

## Anti-patterns or when not to use
- Not suitable when asynchronous batch scheduling is required instead of immediate channel-to-system delivery.

## References
- [Consumer Pattern 1](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-1.aspx)
