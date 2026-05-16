---
id: REF-TPL-HLD-GENERIC-001
title: Generic high-level design template
type: high_level_design
status: approved
owner: Enterprise Architecture
last_reviewed: 2026-05-10
applies_to: technology, data, applications, integrations
tags: hld, template, architecture, design, reusable
related:
  - knowledge/standards/architecture-standard.txt
  - knowledge/standards/governance-standard.txt
---

## Purpose

Use this template for a high-level design covering a technology, data, application, or integration solution. The document should explain the business outcome, the proposed architecture, major design decisions, delivery phases, and the controls needed for operational support.

Replace bracketed placeholders such as `[solution name]` and `[system]` with project-specific content. Keep the HLD focused on architecture and assurance; detailed build tasks, low-level specifications, and implementation plans belong in supporting documents.

## Document control

| Field | Value |
|---|---|
| Document title | `[solution name] HLD` |
| Version | `0.1` |
| Status | `Draft` |
| Owner | `[Business Owner / Product Owner / Architecture Owner]` |
| Authors | `[names / roles]` |
| Reviewers | `[architecture, security, data, platform, operations]` |
| Date | `[YYYY-MM-DD]` |

## Executive summary

Summarise the proposed solution in a few paragraphs:

- business problem and audience
- recommended approach
- main systems or interfaces involved
- target platform or capability
- key risks, constraints, and decisions
- expected operational state

## Context

Describe the business and technical background:

- current process or service
- users and consuming teams
- pain points or drivers for change
- source systems, target systems, files, or APIs
- frequency and criticality
- known constraints, deadlines, or dependencies

## Scope

### In scope

- `[capabilities / domains included]`
- `[systems, interfaces, reports, services, or datasets included]`
- `[environments and release scope]`
- `[operational support responsibilities]`

### Out of scope

- `[capabilities not changed by this design]`
- `[source-system remediation excluded from this phase]`
- `[systems, domains, or integrations not included]`

## Requirements

### Business requirements

- `[business question / outcome supported]`
- `[minimum functional outputs]`
- `[service levels or response times]`
- `[availability expectations]`
- `[access and sharing needs]`

### Non-functional requirements

- availability
- performance
- scalability
- security
- privacy
- accessibility
- auditability
- supportability
- maintainability

## Current state

Describe the as-is solution and flow:

- current systems and interfaces
- manual handling steps
- existing transformations or business rules
- known data or service quality issues
- current ownership and support model
- limitations or risks

## Target architecture

Describe the target architecture at a high level.

Recommended architecture flow:

1. A request, event, or data item is produced.
2. It is received by an agreed ingress mechanism or service.
3. Validation or control checks run before processing.
4. Data or messages are staged or processed in a controlled layer.
5. Business rules, transformations, or orchestration create the curated output.
6. The downstream system, report, or consumer accesses the curated layer.
7. The solution is secured, monitored, and supported.

Include a diagram where possible.

## Architecture views

### Logical view

Show the main logical components:

- source systems, users, or upstream services
- ingestion or interface layer
- staging or processing layer
- transformation or orchestration layer
- curated data, service, or output layer
- consumer layer
- metadata, lineage, monitoring, and support components

### Data flow or process view

Document the end-to-end flow:

| Step | From | To | Description | Owner |
|---|---|---|---|---|
| 1 | `[source]` | `[ingress]` | `[submission / event capture / extraction]` | `[role]` |
| 2 | `[ingress]` | `[validation]` | `[schema, control, or business-rule checks]` | `[role]` |
| 3 | `[validation]` | `[processing]` | `[accepted input persisted or queued]` | `[role]` |
| 4 | `[processing]` | `[curated]` | `[business rules, transformations, orchestration]` | `[role]` |
| 5 | `[curated]` | `[consumer]` | `[reporting, API, export, or downstream consumption]` | `[role]` |

### Deployment view

Describe environments, boundary controls, and release process:

- development, test, and production environments
- platform or tenant boundaries
- deployment pipeline
- approval gates
- rollback approach

## Source inputs

List all source inputs.

| Source | Type | Owner | Frequency | Critical fields or attributes | Known issues |
|---|---|---|---|---|---|
| `[source name]` | `[system / file / API / user input]` | `[role/team]` | `[cadence]` | `[fields / attributes]` | `[issues]` |

For file-based or manually supplied inputs, record:

- original file name or submission name
- received date
- source owner
- submission route
- expected schema or payload
- retention requirement

## Data model, business rules, or processing logic

Describe the curated model or processing logic at a level suitable for architecture assurance:

- main entities, messages, or outputs
- grain or processing unit
- key joins, relationships, or dependencies
- where transformation or orchestration logic runs
- reusable business definitions or rules
- ownership of business logic

Avoid hiding critical logic only inside implementation artefacts.

## Validation and quality controls

Define controls appropriate to the solution:

- schema checks
- mandatory fields
- referential checks
- duplicate checks
- range and format checks
- business-rule checks
- reconciliation checks
- exception handling
- issue triage and resolution

## Lineage and metadata

Explain how consumers and support teams can trace outputs back to input:

- source identity
- ingestion timestamp
- source owner
- processing steps
- curated version or release
- output version
- known limitations
- metadata catalogue registration

## Security, privacy, and access

Describe:

- authentication model
- authorisation groups or roles
- row-level or object-level security
- sensitive data classification
- privacy considerations
- external sharing restrictions
- audit logging
- break-glass or privileged access

## Governance and ownership

Define the minimum governance roles.

| Role | Accountability |
|---|---|
| Business Owner | Owns business meaning, approves scope, accepts risk, and authorises operational use. |
| Solution Owner | Owns solution intent, release planning, stakeholder feedback, and adoption. |
| Data or Service Steward | Maintains definitions, monitors quality, and coordinates corrections. |
| Technical Custodian | Operates the platform, access controls, deployment, storage, backup, and monitoring. |
| Support Owner | Owns incident handling, service requests, and operational communication. |

## Key decisions

Capture architecture decisions that materially shape the design.

| Decision | Rationale | Consequence | Status |
|---|---|---|---|
| `[decision]` | `[why]` | `[impact]` | `[proposed / approved]` |

## Options considered

Summarise the main options and why the preferred approach was selected.

| Option | Description | Benefits | Risks | Decision |
|---|---|---|---|---|
| `[option]` | `[summary]` | `[benefits]` | `[risks]` | `[selected / rejected]` |

## Risks, assumptions, issues, and dependencies

### Risks

| Risk | Impact | Mitigation | Owner |
|---|---|---|---|
| `[risk]` | `[impact]` | `[mitigation]` | `[role]` |

### Assumptions

- `[assumption]`

### Issues

- `[issue]`

### Dependencies

- `[dependency]`

## Delivery approach

Describe how the solution will be delivered:

- discovery and requirements confirmation
- governance role assignment
- build or configuration
- integration and validation
- testing and assurance
- production deployment
- handover to operations

## Testing and acceptance

Define acceptance criteria:

- functional test
- validation or rejection test
- integration test
- reconciliation or comparison test
- security and access test
- performance test
- user acceptance test
- operational readiness test

## Operations and support

Document:

- monitoring and alerting
- incident process
- support hours
- known failure modes
- restart or rerun process
- correction process
- backup and retention
- decommissioning criteria

## Open questions

| Question | Owner | Due date | Status |
|---|---|---|---|
| `[question]` | `[role]` | `[YYYY-MM-DD]` | `[open]` |

## Approvals

| Approver | Role | Decision | Date |
|---|---|---|---|
| `[name]` | `[role]` | `[approved / rejected / pending]` | `[YYYY-MM-DD]` |

## Source

This template was derived from `HLD%20Template.aspx` and generalised for reusable high-level design use across different technology and data projects.
