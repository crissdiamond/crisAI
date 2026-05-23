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
| Extracted evidence | Machine-readable extraction from the raw source, with provenance and confidence metadata. | `workspace/staging/` |
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
- data glossary;
- lineage or data-flow reference;
- governance process;
- review and sign-off process;
- role and contact directory;
- intranet or operational reference;
- unknown.

Unknown or ambiguous sources should be kept in staging until clarified.

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

### 6. Detect Duplicates, Conflicts, And Stale Sources

Before review, check for:

- duplicate files with different names;
- old versions of templates or standards;
- conflicting guidance across sources;
- missing owner or approval status;
- sources with low extraction confidence;
- overlapping knowledge entries;
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
- agent guesses, caveats, or reasoning traces.

## Suggested First Bootstrap

For a first team setup, use a small seed pack:

1. Current HLD template.
2. Current options paper template.
3. Architecture principles.
4. Governance and sign-off process.
5. Data ownership and stewardship guidance.
6. Integration or data architecture standards.
7. Two or three recently approved artefacts.
8. Role and contact directory for architecture review.

After the seed pack is validated, expand gradually by domain or source system.

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
