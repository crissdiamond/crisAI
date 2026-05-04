---
id: PATT-INT-006
title: Producer Pattern 2 - System to Enterprise Channel: Batch Synchronous
type: pattern
status: draft
owner: Architecture
related: []
---

## Source
- [Producer Pattern 2](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx)

## Design overview
- Name: System to Enterprise Channel - Batch Synchronous
- Version: 0.1
- Status: APPROVED
- Date: 21 March 2023
- Classification: Producer pattern
- Source: System (API/DB/File)
- Target: Enterprise Channel
- Invocation: Batch
- Delivery: Synchronous
- Core pattern: No
- Description: Fetch data from System on a scheduled basis and send over Enterprise Channel synchronously.

## When to use
- Use when a scheduled event must extract changes from a system that does not support event-driven publishing.
- Use when near real-time behaviour is simulated by batch scheduling.

## Implementation
- A scheduled event triggers the data fetch from the System.
- The response from the System API is translated into an Enterprise Data Model and then published to the channel.
- If an error occurs while publishing to the Enterprise Channel, the message is saved to Dead Letter for reprocessing.
- Solution overview includes scheduled trigger, processing, connector and publish molecules.
- Physical implementation notes for AWS use CloudWatch Scheduler, Lambda, SNS and reconciliation API; Azure uses Time Trigger Service, Azure Function, Event Grid and reconciliation API.

## Anti-patterns or when not to use
- Not suitable when the source system can emit events directly on change.

## References
- [Producer Pattern 2](https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-2.aspx)
