---
id: PATT-INT-004
title: Consumer Pattern 4 - Enterprise API to System: Asynchronous
type: pattern
status: draft
owner: Architecture
related: []
---

## Source
- [Consumer Pattern 4](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx)

## Design overview
- Name: Enterprise API to System: Asynchronous
- Version: 0.1
- Status: APPROVED
- Date: 30 March 2023
- Classification: Consumer pattern
- Source: Enterprise API
- Target: System (API/DB/File)
- Delivery: Asynchronous
- Core pattern: Yes
- Description: Send events received on the Enterprise API to the target system asynchronously.

## When to use
- Use when the consumer requests data from a producer interface and waits for the data to be returned later for transformation and delivery.
- Use when the response is callback-based rather than completed in the same call.

## Implementation
- A scheduler event triggers the process to request data from the producer interface.
- The producer prepares data and sends it over the consumer gateway.
- The consumer gateway captures the event, transforms it into a System data model and sends it to the System.
- If an error occurs while publishing to the System, the message is pushed back to the internal queue for reprocessing.
- Solution overview includes request, processing and connector molecules.
- Physical implementation notes for AWS use CloudWatch Scheduler, Lambda, API Gateway and SQS; Azure uses Time Trigger Service, Azure Function, API Management and Service Bus Queue.

## Anti-patterns or when not to use
- Not suitable where the target system must be updated synchronously in the originating transaction.

## References
- [Consumer Pattern 4](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Consumer-Pattern-4.aspx)
