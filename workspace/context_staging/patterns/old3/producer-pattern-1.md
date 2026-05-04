---
id: PATT-INT-006
title: Producer Pattern 1 - System to Enterprise API : onDemand Synchronous
type: pattern
status: draft
owner: crisAI
last_reviewed: 2026-05-04
applies_to: all
tags: integration, producer, enterprise-api, synchronous
related: []
---

## Source
- Title: Producer Pattern 1
- web_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx
- open_url: https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx

## Design overview
- Pattern name: System to Enterprise API - onDemand Synchronous
- Description: Send requested data to consumer over Enterprise API synchronously.
- Version: 0.1
- Status: APPROVED
- Date: 21 March 2023
- Classification: Producer pattern
- Source: System (API/DB/File)
- Target: Enterprise API
- Invocation: Synchronous
- Core pattern: Yes
- NFRs: observability with standard logging and correlation IDs; reconciliation no; reliability yes with retry and no dead letter queue because the response is synchronous; SLA guidance required; volumetric capacity depends on interface usage and concurrency; operational limits include payload and runtime thresholds.
- Security constraints: for communication within AWS, use IAM permissions implemented using Terraform; cross-cloud and cross-account topics are open.

## When to use
- Use for application integration with an end user session.
- Use for enrichment where the consumer needs additional information from the student API or similar system.

## Implementation
- The pattern takes a request from the consumer, models it into system data model and invokes the system API.
- The response from the system is translated into Enterprise Data Model and sent to the Enterprise API.
- If an error occurs during the process, it is modelled and sent into a standard error response.
- Physical implementation on AWS: API Gateway receives the request; JWT token validation is performed; Lambda validates and processes the request; Secrets Manager provides system credentials; Lambda connects to the downstream system; the system responds synchronously; the outcome is logged in CloudWatch; the response is returned back through API Gateway.
- Physical implementation on Azure: API Management receives the request; JWT token validation and request validation are performed; Azure Function processes the request; Key Vault provides system credentials; Azure Function connects to the downstream system; the system responds synchronously; the outcome is logged in Azure Monitor; the response is returned back through API Management.

## References
- https://liveuclac.sharepoint.com/sites/it-architecture/SitePages/Producer-Pattern-1.aspx
