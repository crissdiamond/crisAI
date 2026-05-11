# CRISAI-ADR-010: Add a narrow document formatting agent

- `Status`: accepted
- `Date`: 2026-05-11

## Context

crisAI generates architecture artefacts as Markdown/Mermaid source files under
task workspaces. Users also need native organisation documents such as Word HLDs
and PowerPoint packs. Mixing content drafting, design judgement, and native file
formatting in one agent would blur responsibilities and increase the risk of
content changes during export.

## Decision

Add a dedicated `document_formatter` agent for native document export. Its scope
is limited to taking an existing reviewed Markdown artefact, inspecting a
template manifest, and rendering a DOCX or PPTX output through the
`document_export` MCP server.

Template semantics live in workspace manifests, initially under
`workspace/knowledge/templates/ucl/`. The exporter writes only to
`workspace/tasks/<task>/exports/` or `workspace/outputs/` and returns a structured
export report with warnings such as missing required sections.

## Consequences

- Content ownership stays with design, summary, review, and publisher agents.
- Formatting ownership is isolated to one agent and one MCP server.
- Official organisation templates can be added without changing agent prompts or
  routing code, by adding binary template files beside template manifests.
- Initial export support is intentionally basic for PPTX layout and DOCX style
  fidelity until real binary templates are supplied.

## Related

- `registry/agents.yaml`
- `registry/servers.yaml`
- `prompts/document_formatter.md`
- `src/crisai/servers/document_export_server.py`
- `workspace/knowledge/templates/ucl/`
