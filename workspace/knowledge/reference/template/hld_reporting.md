---
id: REF-TPL-HLD-REPORTING-001
title: Reporting high-level design template
type: high_level_design
status: approved
owner: Enterprise Architecture
last_reviewed: 2026-05-10
applies_to: reporting, analytics, business-intelligence
tags: hld, reporting, power-bi, data-platform, governance, lineage
related:
  - knowledge/standards/reporting-standard.txt
  - knowledge/standards/governance-standard.txt
  - knowledge/standards/naming-and-lineage.txt
  - knowledge/patterns/reporting-patterns.txt
---

## Purpose

Use this template for a high-level design covering a reporting, analytics, dashboard, or business-intelligence solution. The document should explain the business outcome, the proposed architecture, major design decisions, delivery phases, and the controls needed for operational reporting.

Replace bracketed placeholders such as `[report name]` and `[system]` with project-specific content. Keep the HLD focused on architecture and assurance; detailed field mappings, report layout specifications, and build tasks belong in supporting documents.

## Document control

| Field | Value |
|---|---|
| Document title | `[reporting solution / dashboard name] HLD` |
| Version | `0.1` |
| Status | `Draft` |
| Owner | `[Data Owner / Product Owner / Architecture Owner]` |
| Authors | `[names / roles]` |
| Reviewers | `[architecture, data, security, platform, operations]` |
| Date | `[YYYY-MM-DD]` |

## Executive summary

Summarise the proposed reporting solution in a few paragraphs:

- business problem and audience
- recommended approach
- main source systems or files
- target reporting platform
- key risks, constraints, and decisions
- expected operational state

## Context

Describe the business and technical background:

- current reporting process
- users and consuming teams
- pain points or drivers for change
- source systems, files, or manual inputs
- frequency and criticality of the report
- known constraints, deadlines, or dependencies

## Scope

### In scope

- `[source data / domains included]`
- `[reports, dashboards, datasets, semantic models]`
- `[refresh cadence and environments]`
- `[operational support responsibilities]`

### Out of scope

- `[manual processes not changed by this design]`
- `[source-system remediation excluded from this phase]`
- `[reports or data domains not included]`

## Requirements

### Business requirements

- `[business question / decision supported]`
- `[minimum reporting outputs]`
- `[refresh frequency]`
- `[latency expectations]`
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

Describe the as-is reporting and data flow:

- source locations and formats
- manual handling steps
- existing transformations
- known data quality issues
- current ownership and support model
- limitations or risks

## Target architecture

Describe the target reporting architecture at a high level.

Recommended reporting flow:

1. Source data is produced or submitted.
2. Data lands in a controlled ingestion location or service.
3. Validation checks run before data is promoted.
4. Data is staged in a controlled store.
5. Business transformations create a curated dataset or semantic model.
6. Power BI or the reporting tool connects to the curated layer.
7. Reports are published, secured, monitored, and supported.

Include a diagram where possible.

## Architecture views

### Logical view

Show the main logical components:

- source systems or files
- ingestion service
- staging layer
- transformation layer
- curated dataset or semantic model
- report layer
- metadata, lineage, monitoring, and support components

### Data flow view

Document the end-to-end data path:

| Step | From | To | Description | Owner |
|---|---|---|---|---|
| 1 | `[source]` | `[landing]` | `[submission / extraction]` | `[role]` |
| 2 | `[landing]` | `[validation]` | `[schema and business-rule checks]` | `[role]` |
| 3 | `[validation]` | `[staging]` | `[accepted data persisted]` | `[role]` |
| 4 | `[staging]` | `[curated]` | `[business transformations]` | `[role]` |
| 5 | `[curated]` | `[report]` | `[visualisation and consumption]` | `[role]` |

### Deployment view

Describe environments, tenant/workspace boundaries, deployment process, and release controls:

- development, test, and production workspaces
- data platform environments
- deployment pipeline
- approval gates
- rollback approach

## Source data

List all source inputs.

| Source | Type | Owner | Frequency | Critical fields | Known issues |
|---|---|---|---|---|---|
| `[source name]` | `[system / file / API]` | `[role/team]` | `[cadence]` | `[fields]` | `[issues]` |

For file-based sources, record:

- original file name
- received date
- source owner
- submission route
- expected schema
- retention requirement

## Data model and transformations

Describe the curated model at a level suitable for architecture assurance:

- main entities and measures
- grain of each dataset
- key joins and relationships
- where transformation logic runs
- reusable business definitions
- semantic model ownership

Avoid hiding critical transformation logic only inside the report file.

## Data quality and validation

Define validation controls:

- schema checks
- mandatory fields
- referential checks
- duplicate checks
- range and format checks
- business-rule checks
- reconciliation checks
- exception handling
- quality issue triage and resolution

## Lineage and metadata

Explain how consumers and support teams can trace report outputs back to source input:

- source system or file identity
- ingestion timestamp
- source owner
- transformation steps
- curated dataset version
- report version
- known limitations
- metadata catalogue registration

## Security, privacy, and access

Describe:

- authentication model
- authorisation groups or roles
- row-level security
- sensitive data classification
- privacy considerations
- external sharing restrictions
- audit logging
- break-glass or privileged access

## Governance and ownership

Define the minimum governance roles.

| Role | Accountability |
|---|---|
| Data Owner | Owns business meaning, approves definitions, accepts risk, and authorises operational use. |
| Data Steward | Maintains business definitions, monitors data quality, resolves content issues, and coordinates corrections. |
| Data Custodian | Operates the technical platform, access controls, refresh process, storage, backup, and monitoring. |
| Report Owner | Owns report usability, release planning, adoption, and stakeholder feedback. |
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

- discovery and source profiling
- governance role assignment
- ingestion and validation build
- curated dataset build
- report build
- testing and assurance
- production deployment
- handover to operations

## Testing and acceptance

Define acceptance criteria:

- source ingestion test
- validation and rejection test
- transformation test
- reconciliation test
- security and access test
- performance test
- user acceptance test
- operational readiness test

## Operations and support

Document:

- refresh schedule
- monitoring and alerting
- incident process
- support hours
- known failure modes
- restart or rerun process
- data correction process
- backup and retention
- decommissioning criteria

## Open questions

| Question | Owner | Due date | Status |
|---|---|---|---|
| `[question]` | `[role]` | `[YYYY-MM-DD]` | `[open]` |

## Source

This template is based on local crisAI reporting, governance, and lineage standards under `workspace/knowledge/standards/`, and reporting design precedent under `workspace/knowledge/designs/`.

## References

- `knowledge/standards/reporting-standard.txt`
- `knowledge/standards/governance-standard.txt`
- `knowledge/standards/naming-and-lineage.txt`
- `knowledge/patterns/reporting-patterns.txt`
