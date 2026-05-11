# CRISAI-ADR-007: Markdown/Mermaid Is The Source Of Truth For Generated Artefacts

Status: accepted  
Date: 2026-05-11

## Context

crisAI can be asked to produce many architecture artefact types: HLDs, LLDs,
options papers, diagrams, presentations, emails, mappings, payloads, and native
Office documents. Producing native files directly makes validation, review, and
promotion harder.

## Decision

Generated task artefacts use Markdown and Mermaid as the authoritative source
format. Native Word, PowerPoint, Excel, email, JSON payload, mapping documents,
and diagram exports are follow-on generation tasks from reviewed Markdown and
organisation templates.

## Consequences

- Task artefacts are easy to diff, validate, edit, and promote.
- Native document generation can be added without changing the core task model.
- Templates for native outputs belong in curated knowledge or organisation
  template spaces.
- Web editing can focus on text-based artefacts first.

## Related

- `workspace/tasks/README.md`
- `workspace/knowledge/reference/template/hld_reporting.md`
- `src/crisai/apps/web.py`
