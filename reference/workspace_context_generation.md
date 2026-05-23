# Workspace Context Generation Guideline

This guideline describes how crisAI users and team members should collaborate to
create and maintain a trusted workspace knowledge base from existing
documentation.

The goal is to make crisAI useful quickly without allowing unreviewed summaries,
partial extraction, or stale documents to become trusted context. crisAI can
automate discovery, extraction, classification, and draft preparation, but human
review is required before content is promoted into the validated knowledge base.

## Principles

- Treat original documents as source evidence, not automatically trusted
  knowledge.
- Keep generated context traceable to source documents, pages, owners, and
  versions.
- Separate draft context from validated knowledge.
- Prefer smaller, focused knowledge entries over large copied document dumps.
- Capture uncertainty explicitly: missing sections, unsupported formats,
  extraction errors, and conflicting sources must remain visible.
- Promote knowledge only after an accountable person has reviewed it.
- Keep sensitive information, credentials, and auth caches out of the workspace.

## Knowledge States

Workspace context should move through three states.

| State | Meaning | Typical Location |
|---|---|---|
| Raw source | Original documents, pages, or files used as evidence. | External source system, uploaded input area, or source document folder |
| Extracted evidence | Machine-readable extraction from the raw source, with provenance and confidence metadata. | `workspace/knowledge_staging/` |
| Validated knowledge | Reviewed, approved, reusable context for crisAI agents. | `workspace/knowledge/` |

Agents may use raw source and extracted evidence for a specific task, but
reusable organisational context should come from validated knowledge wherever
possible.

## Recommended Workflow

### 1. Select Source Material

Start with a bounded source set. Examples:

- architecture standards;
- HLD, LLD, and options paper templates;
- approved designs;
- enterprise architecture principles;
- integration and data patterns;
- governance process documents;
- data ownership and stewardship documents;
- enterprise data models;
- system-specific conceptual, logical, and physical data models;
- canonical data models, interface schemas, mappings, payload definitions, and
  reporting semantic models;
- glossary, data catalogue, lineage, and reporting documentation;
- role and contact directories;
- intranet pages or SharePoint pages that describe process or standards.

Avoid starting with a broad unfiltered document repository. A smaller, reviewed
source batch produces a better knowledge base than a noisy bulk import.

### 2. Inventory The Sources

For each source, capture enough metadata to make it auditable:

- title;
- source system;
- location or URL;
- owner or accountable team if known;
- created and modified dates;
- version, ETag, hash, or equivalent revision marker;
- document type;
- access restrictions;
- intended audience;
- extraction status.

If ownership or version is unclear, flag the source for review instead of
promoting it silently.

### 3. Extract Structured Evidence

Use crisAI source adapters to read the documents and produce structured
extraction. The extraction should preserve:

- headings and section hierarchy;
- slide titles and speaker notes where available;
- tables;
- links and references;
- diagrams or diagram captions where available;
- document metadata;
- extraction warnings;
- unsupported content notices;
- source references for each extracted section.

The extraction output is not yet validated knowledge. It is evidence for review.

### 4. Classify The Source

Classify each source using agreed categories. Useful initial categories include:

- architecture standard;
- architecture principle;
- architecture pattern;
- HLD template;
- options paper template;
- architecture decision;
- approved design;
- data architecture guidance;
- enterprise data model;
- system-specific data model;
- canonical data model;
- reporting semantic model;
- interface schema or payload model;
- data glossary;
- lineage or data-flow reference;
- governance process;
- review and sign-off process;
- role and contact directory;
- intranet or operational reference;
- unknown.

Unknown or ambiguous sources should be kept in staging until clarified.

## Data Model Context

Enterprise and system-specific data models are first-class context for crisAI.
They should be curated with the same staging, review, and promotion process as
architecture standards and templates.

The configured workspace categories support data model knowledge under:

- `workspace/knowledge_staging/data-models/` for draft candidates;
- `workspace/knowledge/data-models/` for reviewed and approved models.

Use this area for:

- enterprise conceptual and logical data models;
- domain data models;
- canonical data models;
- system-specific logical or physical data models;
- source-to-target mapping documents;
- interface payload schemas;
- reporting semantic models;
- data product models;
- glossary-to-entity mappings;
- model ownership, stewardship, and custodianship notes;
- model version history and supersession notes.

Data model context should make scope explicit. A system-specific model is not an
enterprise model. A reporting semantic model is not necessarily the system of
record model. A physical warehouse model is not necessarily the canonical
business model. Capturing those distinctions avoids agents using the wrong model
at design time.

Recommended front matter for data model candidates:

```yaml
---
title: Example Customer Domain Logical Data Model
knowledge_type: data_model
model_scope: domain
model_level: logical
domain: Customer
system: ""
system_of_record: ""
source_system: SharePoint
source_uri: https://example.invalid/source
source_version: example-etag-or-hash
source_modified: 2026-05-23
owner: Example Data Owner
data_steward: Example Data Steward
data_custodian: Example Platform Team
status: draft
reviewer: ""
created_by: crisAI
created_on: 2026-05-23
confidence: medium
---
```

Useful `model_scope` values:

- `enterprise`;
- `domain`;
- `system`;
- `interface`;
- `reporting`;
- `data_product`;
- `unknown`.

Useful `model_level` values:

- `conceptual`;
- `logical`;
- `physical`;
- `semantic`;
- `schema`;
- `mapping`;
- `unknown`.

Each promoted data model entry should explain:

- business purpose and scope;
- authoritative source and ownership;
- key entities, attributes, and relationships;
- identifiers and keys;
- system of record and consuming systems;
- critical business definitions;
- data classifications and sensitivity where known;
- quality constraints and known issues;
- lineage or source-to-target relationships;
- version and supersession status;
- gaps and assumptions.

Do not collapse all model types into one generic summary. If the source material
contains both enterprise and system-specific models, create separate candidates
and link them through references.

### 5. Generate Draft Knowledge Candidates

Create concise draft entries from the extracted evidence. A good knowledge entry
should be reusable by agents and understandable by people.

Each candidate should include YAML front matter similar to:

```yaml
---
title: Example Architecture Standard
knowledge_type: architecture_standard
status: draft
source_system: SharePoint
source_uri: https://example.invalid/source
source_version: example-etag-or-hash
source_modified: 2026-05-23
owner: Example Team
reviewer: ""
created_by: crisAI
created_on: 2026-05-23
confidence: medium
---
```

The body should contain the reusable knowledge, not a blind copy of the source.
Prefer sections such as:

- purpose;
- scope;
- key rules or principles;
- required artefact sections;
- decision criteria;
- roles and responsibilities;
- examples;
- exceptions;
- source references;
- open questions.

For data model candidates, prefer sections such as:

- model purpose;
- model scope and level;
- domain or system boundary;
- authoritative source;
- ownership and stewardship;
- entities and definitions;
- relationships;
- keys and identifiers;
- mappings and lineage;
- quality rules;
- classifications and sensitivity;
- model gaps;
- source references;
- review questions.

### 6. Detect Duplicates, Conflicts, And Stale Sources

Before review, check for:

- duplicate files with different names;
- old versions of templates or standards;
- conflicting guidance across sources;
- missing owner or approval status;
- sources with low extraction confidence;
- overlapping knowledge entries;
- enterprise models confused with system-specific or reporting models;
- physical schemas promoted as canonical business definitions without review;
- business-sensitive content that should not become general context.

Conflict notes should stay with the candidate until resolved.

### 7. Human Review And Approval

A nominated reviewer should decide whether the candidate is:

- approved for promotion;
- approved with edits;
- rejected;
- merged into another entry;
- deferred pending owner confirmation.

The reviewer should verify:

- the source is authoritative;
- the generated text preserves the intended meaning;
- the scope is clear;
- the content is current;
- ownership is recorded;
- sensitive material is handled appropriately;
- the entry is useful as reusable context.

### 8. Promote To Validated Knowledge

Only approved candidates should move into `workspace/knowledge/`.

When promoting, update the front matter:

```yaml
status: approved
reviewer: reviewer@example.org
reviewed_on: 2026-05-23
```

The promoted file should remain linked to its original source and version. If
the source changes later, the entry should be reviewed again before being treated
as current.

## Roles And Responsibilities

| Role | Responsibility |
|---|---|
| Source Owner | Confirms whether the original source is authoritative and current. |
| Knowledge Curator | Prepares, edits, deduplicates, and maintains knowledge entries. |
| Reviewer | Approves or rejects candidates before promotion. |
| Architect User | Uses validated knowledge in crisAI tasks and reports gaps or stale content. |
| crisAI | Automates inventory, extraction, classification, candidate drafting, and review-pack preparation. |

One person may hold multiple roles in a small team, but approval should still be
explicit.

## Quality Checklist

Before promoting a knowledge entry, confirm:

- the source document or page was actually read;
- the source identity and version are recorded;
- the owner or accountable team is known, or the gap is explicit;
- generated wording has been reviewed by a person;
- conflicts with existing knowledge have been checked;
- the content is concise and reusable;
- sensitive or restricted content is not exposed inappropriately;
- the entry has a clear knowledge type;
- data model entries have explicit model scope, model level, owner, and source
  version;
- the entry has `status: approved`;
- there is a plan to refresh or retire it when the source changes.

## What Not To Promote

Do not promote:

- raw OCR text without review;
- generated summaries with no source reference;
- unsupported slide or diagram interpretations;
- personal notes unless the owner approves them as reusable knowledge;
- outdated versions of templates or standards;
- documents with unclear confidentiality;
- duplicate entries created only because filenames differ;
- inferred entities, relationships, or definitions that are not present in the
  source evidence;
- database schemas or payload fields treated as enterprise definitions without
  data owner review;
- agent guesses, caveats, or reasoning traces.

## Suggested First Bootstrap

For a first team setup, use a small seed pack:

1. Current HLD template.
2. Current options paper template.
3. Architecture principles.
4. Governance and sign-off process.
5. Data ownership and stewardship guidance.
6. Enterprise or domain data model documentation.
7. One or two important system-specific data models or reporting semantic
   models.
8. Integration or data architecture standards.
9. Two or three recently approved artefacts.
10. Role and contact directory for architecture review.

After the seed pack is validated, expand gradually by domain or source system.

## Suggested crisAI Prompts

The prompts below are intended for team members bootstrapping or maintaining the
workspace knowledge base. Adjust source names, folders, document titles, and
domains as needed.

### Discover Candidate Sources

```text
Search the available workspace and connected document repositories for current
architecture standards, templates, governance process documents, data ownership
guidance, enterprise data models, system-specific data models, reporting
semantic models, lineage documents, and approved architecture artefacts that
could be used to bootstrap crisAI workspace knowledge.

Do not create or update files yet.

Return a source inventory with title, source location, document type, likely
knowledge category, owner if available, modified date if available, read status,
and any gaps or duplicate candidates.
```

### Read And Extract A Source Batch

```text
Use the source inventory below as the candidate source set.

Read each source that has a valid handle or path. Extract structured evidence
for workspace context generation. Preserve source references, headings, slide
titles, tables, model names, entity names, key definitions, owner information,
version information, and extraction warnings.

Do not promote anything to validated knowledge.

For each source, classify it as one of: architecture standard, architecture
principle, architecture pattern, template, approved design, enterprise data
model, system-specific data model, canonical data model, reporting semantic
model, data glossary, lineage reference, governance process, role directory, or
unknown.
```

### Generate Staged Knowledge Candidates

```text
Using only the extracted evidence from this run, create draft knowledge
candidates under workspace/knowledge_staging/.

Use the appropriate subfolder:
- standards for architecture or data standards;
- templates for artefact templates;
- patterns for reusable patterns;
- data-models for enterprise, domain, canonical, system, interface, reporting,
  or data product models;
- organisation for roles, ownership, stewardship, and review bodies;
- reference for general reference material.

Each file must include YAML front matter with title, knowledge_type, status:
draft, source_system, source_uri or source path, source_version or hash if
available, source_modified if available, owner if known, reviewer blank,
created_by: crisAI, created_on, and confidence.

For data model candidates, also include model_scope, model_level, domain, system,
system_of_record, data_steward, and data_custodian where known.

Do not write to workspace/knowledge/.
```

### Review Staged Candidates

```text
Review the staged knowledge candidates under workspace/knowledge_staging/.

Check each candidate for source traceability, clear scope, correct knowledge
type, duplicate or stale sources, conflicts with existing approved knowledge,
missing owners, missing reviewers, data model scope and level, and sensitive
content risks.

Return a review table with candidate path, recommendation, required edits,
missing information, source confidence, and whether it is ready for human
approval.

Do not promote anything yet.
```

### Prepare A Human Review Pack

```text
Prepare a human review pack for the staged knowledge candidates related to
<domain or source batch>.

Group candidates by category. For each candidate, summarise the source evidence,
proposed reusable knowledge, unresolved gaps, conflicts, and explicit approval
question for the reviewer.

Highlight any enterprise data model or system data model where scope,
ownership, system of record, lineage, or version is unclear.
```

### Promote Approved Knowledge

```text
Promote only the following approved staged candidates to validated knowledge:

- <workspace/knowledge_staging/.../candidate-1.md>
- <workspace/knowledge_staging/.../candidate-2.md>

Before promotion, update the front matter to status: approved and add reviewer
and reviewed_on.

Move or copy the approved entries to the matching location under
workspace/knowledge/. Preserve source references and version metadata.

Do not promote any other staged files.
```

### Refresh Existing Knowledge From Updated Sources

```text
Check whether the approved knowledge entries under workspace/knowledge/<area>
are still aligned with their recorded source documents.

Compare source version, modified date, or hash where available. Identify entries
that are current, stale, source-missing, or unclear.

For stale entries, create updated draft candidates under
workspace/knowledge_staging/ and explain the differences. Do not overwrite
approved knowledge without explicit approval.
```

## Maintenance

Workspace knowledge is not a one-off import. Review it regularly:

- when the source document changes;
- when a template is superseded;
- when governance roles change;
- when a project identifies a missing or stale standard;
- before using the workspace for a new architecture domain;
- after major changes to source connectors or extraction tooling.

Validated knowledge should be treated as a managed asset, not as a cache of
everything crisAI has ever read.
