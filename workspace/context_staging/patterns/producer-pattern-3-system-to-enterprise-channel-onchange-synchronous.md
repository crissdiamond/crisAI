---
id: PATT-INT-007
title: Producer Pattern 3 - System to Enterprise Channel: onChange Synchronous
type: pattern
status: draft
owner: Architecture
related: []
---

## Source
- [Producer Pattern 3](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx)

## Design overview
- Name: System to Enterprise Channel - onChange Synchronous
- Version: 0.1
- Status: APPROVED
- Date: 21 March 2023
- Classification: Producer pattern
- Source: System (API/DB/File/Event)
- Target: Enterprise Channel
- Invocation: onChange
- Delivery: Synchronous
- Core pattern: Yes
- Description: System events are received and sent over Enterprise Channel synchronously.

## When to use
- Use when a change in the source system must trigger a webhook and publication to the Enterprise Channel.
- Use when the source system can notify changes and the architecture should acknowledge the source before downstream publishing.

## Implementation
- A change in the System triggers an event via webhook to the producer gateway.
- The event is acknowledged and published to an internal queue.
- The event is read from the queue, modelled into an Enterprise Data Model and published to the configured Enterprise Channel.
- If an error occurs while publishing to the channel, the event is saved to Dead Letter for reprocessing.
- Solution overview includes API Gateway event, processing and publish molecules.
- Physical implementation notes for AWS use API Gateway, SQS, Lambda, SNS and reconciliation API; Azure uses API Management, Service Bus Queue, Azure Function and Event Grid.

## Anti-patterns or when not to use
- Not suitable when the source system cannot raise change notifications.

## References
- [Producer Pattern 3](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-3.aspx)
