# Knowledge Authoring Prompt Catalogue

Copy-paste prompts for turning a **source** (a file, a deck, an intranet page, or
a set of them) into an accurate, detailed, UCL-aligned knowledge artefact that
crisAI's agents can ground on.

Each prompt is built to produce a Markdown file that **passes the validation
profile** for its type (`registry/workspace_artifact_profiles.yaml`) and follows
the staging rules, so the output is review-ready, not throwaway.

Companion docs: the programme (`reference/knowledge-base-programme.md`) and the
how-to (`DOCUMENTATION.md` §12.1).

---

## How to use this catalogue

1. **Get the source into crisAI.** Upload the file in the web Workspace
   (→ *Knowledge intake* or *Task inputs*), or reference it where it lives:
   a SharePoint document, an intranet page, or a OneDrive deck. crisAI reads all
   of these through its source adapters.
2. **Pick the prompt** for the artefact type you want and paste it into crisAI.
3. **Fill the two placeholders:** `<SOURCE>` (the exact file/page/deck, or a list
   of them) and `<TOPIC>` (the subject).
4. **Run it.** The artefact is written to `workspace/knowledge_staging/…` with
   `status: draft`.
5. **Validate:** `crisai validate-artefacts` (checks front matter + required
   sections).
6. **Review (mandatory):** open the draft in the Workspace editor, check it
   against the source, fix, set `status: approved`, `owner`, `last_reviewed`.
7. **Promote:** move it into the matching folder in the knowledge repo and open a
   PR (see §12.1).

> Drafts in `knowledge_staging/` are **not** used in production retrieval, so a
> work-in-progress never pollutes a grounded answer until a human promotes it.

---

## Standing rules (assumed by every prompt below)

Every prompt embeds a short `Rules:` line; the full meaning is here so you can
read or strengthen it once:

- **Ground strictly in the named source(s).** Use only what the source states.
  Quote distinctive wording. **Never invent, infer beyond, or "fill in"** content
  the source does not contain.
- **Be comprehensive and precise.** Capture *all* material content — every
  requirement, every parameter, every exception — not a summary. This file is the
  exact knowledge an agent will rely on; under-capturing it weakens every future
  answer.
- **Flag gaps, don't guess.** Where a required section has no support in the
  source, write `Gap: not stated in <source>` rather than fabricating.
- **Record provenance.** Put the origin in `source_url` (a URL, SharePoint/OneDrive
  reference, or workspace path) and name it in a `## Source` section.
- **Stage as draft.** Write to `workspace/knowledge_staging/<folder>/<slug>.md`
  with `status: draft`. Mirror the final `knowledge/` folder. Do not write to
  `workspace/knowledge/` directly.
- **UCL-aligned.** Use UCL's own terms, system names, roles, and context as the
  source presents them; do not substitute generic vendor language.
- **High-stakes types use peer mode.** For principles, standards, and strategies,
  end the prompt with "Use peer mode" so the challenger/judge catch unsupported
  claims.

**Front matter on every artefact:** `id`, `title`, `type`, `status: draft`
(required), plus `owner`, `last_reviewed`, `source_url` (strongly recommended)
and `applies_to`, `tags`, `related` where known.

---

## The prompts

### Foundations

#### Principle  → `knowledge/principles/`  (profile: `principle`)

```
Author a knowledge artefact of type "principle" from the source below.

Source: <SOURCE>
Subject: <TOPIC>

Read the source in full, then write one Markdown file to
workspace/knowledge_staging/principles/<kebab-slug>.md.

Front matter: id (PRIN-<short>), title, type: principle, status: draft,
owner: <team/role>, last_reviewed: <today>, applies_to (optional), tags (optional),
source_url: <SOURCE>.

Required H2 sections, in order:
## Scope        — what the principle governs and where it applies at UCL.
## Statement    — the principle itself, in the source's own wording where possible.
## Implications — what it requires teams/architectures to do or avoid.
Also add: ## Rationale (why it exists) and ## Source (exact origin) when supported.

If the source states several principles, create one file per principle (preferred)
or one file with a "## Statement" group per principle if they are a tight set.

Rules: ground every line strictly in the source; quote key wording; capture every
principle stated; write "Gap: not stated in <SOURCE>" where Scope/Implications are
absent; UCL terminology. Use peer mode.
```

#### Standard  → `knowledge/standards/{data,security,integration}/`  (profile: `standard`)

```
Author a knowledge artefact of type "standard" from the source below.

Source: <SOURCE>
Subject: <TOPIC>

Write one Markdown file to workspace/knowledge_staging/standards/<area>/<kebab-slug>.md
(area = data | security | integration | … to match the source's domain).

Front matter: id (STD-<short>), title, type: standard, status: draft,
owner, last_reviewed, applies_to, source_url: <SOURCE>.

Required H2 section:
## Requirements — the mandatory rules as a numbered/bulleted list, each one
   testable ("MUST/SHOULD" as the source phrases it), preserving thresholds,
   versions, exceptions, and scope conditions exactly.
Also add when supported: ## Scope, ## Conformance and exceptions,
## References, ## Source.

Rules: capture every requirement verbatim in intent — do not soften, merge, or drop
conditions; quote exact thresholds and versions; flag gaps; UCL terminology.
Use peer mode.
```

#### Guideline (process / ways of working)  → `knowledge/reference/` or `standards/`  (profile: `guideline`)

```
Author a knowledge artefact of type "guideline" from the source below — use this
for a process, way-of-working, or how-to (e.g. how UCL runs design review).

Source: <SOURCE>
Subject: <TOPIC>

Write one Markdown file to workspace/knowledge_staging/reference/process/<kebab-slug>.md.

Front matter: id (GDL-<short>), title, type: guideline, status: draft, owner,
last_reviewed, source_url: <SOURCE>.

Required H2 sections:
## Audience  — who follows this process and when.
## Guidance  — the steps/roles/gates/inputs/outputs, in order, with any RACI,
   decision points, and hand-offs the source defines.
Also add when supported: ## Triggers, ## Artefacts and templates used, ## Source.

Rules: preserve the exact sequence, roles, and gate criteria; do not streamline or
reorder; flag gaps; UCL terminology.
```

### Institution context

#### Landscape (platform / estate / capability)  → `knowledge/reference/landscape/`  (profile: `landscape`)

```
Author a knowledge artefact of type "landscape" from the source below — the
platform, system estate, hosting zones, or capability the source describes.

Source: <SOURCE>
Subject: <TOPIC>

Write one Markdown file to workspace/knowledge_staging/reference/landscape/<kebab-slug>.md.

Front matter: id (LAND-<short>), title, type: landscape, status: draft, owner,
last_reviewed, source_url: <SOURCE>.

Required H2 section:
## Summary — what this platform/estate/capability is and its role at UCL.
Also add (strongly preferred — this is reference detail agents will lean on):
## Capabilities, ## Systems and components, ## Owners and support,
## Interfaces and dependencies, ## Constraints and lifecycle, ## Source.
Use a markdown table for inventories (system | owner | purpose | status).

Rules: capture every named system/capability/owner from the source; preserve
versions, environments, and ownership exactly; flag gaps; UCL system names.
```

#### Domain (business / data domain)  → `knowledge/reference/domains/`  (profile: `domain`)

```
Author a knowledge artefact of type "domain" from the source below.

Source: <SOURCE>
Subject: <TOPIC>  (e.g. Student, Research, Finance, Estates)

Write one Markdown file to workspace/knowledge_staging/reference/domains/<kebab-slug>.md.

Front matter: id (DOM-<short>), title, type: domain, status: draft, owner,
last_reviewed, source_url: <SOURCE>.

Required H2 section:
## Overview — what the domain covers and why it matters at UCL.
Also add when supported: ## Key concepts and terms, ## Core data and entities,
## Owning functions and stakeholders, ## Systems of record,
## Key processes, ## Source.

Rules: capture domain vocabulary and systems of record precisely (agents use these
to disambiguate); flag gaps; UCL terminology.
```

#### Integration (system-to-system / vendor touchpoint)  → `knowledge/reference/integrations/`  (profile: `integration`)

```
Author a knowledge artefact of type "integration" from the source below — a
concrete system-to-system interface or vendor touchpoint.

Source: <SOURCE>
Subject: <TOPIC>

Write one Markdown file to workspace/knowledge_staging/reference/integrations/<kebab-slug>.md.

Front matter: id (INT-<short>), title, type: integration, status: draft, owner,
last_reviewed, source_url: <SOURCE>.

Required H2 section:
## Overview — the systems involved and what flows between them.
Also add when supported: ## Endpoints and protocols, ## Data exchanged,
## Frequency and triggers, ## Auth and security, ## Owners and SLAs,
## Error handling, ## Source.

Rules: preserve exact endpoints, formats, protocols, and frequencies; do not
generalise an interface into a pattern; flag gaps; UCL system names.
```

#### Strategy / goals  → `knowledge/strategies/`  (type: `strategy`, default profile)

```
Author a knowledge artefact of type "strategy" from the source below — an
institutional or domain strategy, set of goals, or roadmap.

Source: <SOURCE>  (e.g. the deck "UCL Integration Strategy v2.pptx")
Subject: <TOPIC>

Write one Markdown file to workspace/knowledge_staging/strategies/<kebab-slug>.md.

Front matter: id (STRAT-<short>), title, type: strategy, status: draft, owner,
last_reviewed, applies_to, source_url: <SOURCE>.

H2 sections (include all the source supports):
## Summary, ## Goals and outcomes, ## Principles and drivers,
## Target state, ## Roadmap and milestones, ## Scope and constraints,
## Owners and governance, ## Source.

Rules: capture every stated goal, target date, and measure exactly; keep the
source's priority ordering; do not invent targets or dates; flag gaps; UCL terms.
Use peer mode.
```

### Solutions, patterns, and designs

#### Integration pattern (leaf)  → `knowledge/patterns/`  (profile: `integration_pattern_leaf`)

```
Author a knowledge artefact of type "pattern" from the source below — one
reusable integration pattern (not a catalogue index).

Source: <SOURCE>
Subject: <TOPIC>

Write one Markdown file to workspace/knowledge_staging/patterns/<kebab-slug>.md.

Front matter (ALL required): id (PATT-<short>, unique slug), title, type: pattern,
status: draft, owner. Add last_reviewed, applies_to, tags, source_url: <SOURCE>.

Required H2 sections, in order (ALL required by validation):
## Design overview
## When to use
## Implementation
## NFRS                              (performance, scalability, security, resilience)
## Anti-patterns or when not to use
## Source                            (the exact origin)
## References

Rules: make Implementation concrete enough to apply (steps, components, protocols);
capture the source's constraints and NFRs exactly; give a unique id/slug; flag
gaps; UCL system names. If the source is a catalogue index page, FIRST list its
child links and read each leaf page before writing — do not restate the index.
```

#### Pattern catalogue index  → `knowledge/patterns/*index*.md`  (profile: `integration_patterns_index`)

```
Author the pattern catalogue index of type "pattern" from the source below.

Source: <SOURCE>  (the catalogue/landing page)
Subject: <TOPIC>

First enumerate the catalogue's child links and confirm each leaf pattern exists
or is being authored. Write workspace/knowledge_staging/patterns/integration-patterns-index.md.

Front matter: id, title, type: pattern, status: draft, owner, source_url: <SOURCE>.

Required H2 sections: ## Design overview, ## When to use, ## Implementation,
## Source. Include a markdown table listing each pattern (name | when to use |
link to its leaf file).

Rules: the index must point to real leaf files, not summarise them; flag any
catalogue entry not yet authored as a gap.
```

#### Design precedent (high-level design)  → `knowledge/designs/`  (profile: `high_level_design`)

```
Author a knowledge artefact of type "high_level_design" from the source below — an
exemplar/precedent HLD worth reusing.

Source: <SOURCE>
Subject: <TOPIC>

Write one Markdown file to workspace/knowledge_staging/designs/<kebab-slug>.md.

Front matter: id (HLD-<short>), title, type: high_level_design, status: draft,
owner, last_reviewed, source_url: <SOURCE>.

Required H2 sections, in order:
## Context             — problem, drivers, constraints.
## Target architecture — components, integrations, data flows (use a Mermaid
   diagram when the source shows one).
## Key decisions       — the choices made and why.
Also add when supported: ## NFRs, ## Risks and assumptions, ## Source.

Rules: capture the architecture faithfully (preserve component and interface
names); reproduce diagrams as Mermaid; flag gaps; UCL system names.
```

#### Low-level design  → `knowledge/designs/`  (profile: `low_level_design`)

```
Author a knowledge artefact of type "low_level_design" from the source below.

Source: <SOURCE>
Subject: <TOPIC>

Write one Markdown file to workspace/knowledge_staging/designs/<kebab-slug>.md.

Front matter: id (LLD-<short>), title, type: low_level_design, status: draft,
owner, last_reviewed, source_url: <SOURCE>.

Required H2 sections, in order:
## Design overview
## Components and interfaces        (names, contracts, message/data formats)
## Deployment and operations        (environments, scaling, monitoring, runbooks)
Also add when supported: ## Data model, ## Security, ## Source.

Rules: preserve exact interface contracts, formats, and config values; flag gaps.
```

#### Option paper (precedent)  → `knowledge/designs/`  (profile: `option_paper`)

```
Author a knowledge artefact of type "option_paper" from the source below — a
reusable options analysis / decision precedent.

Source: <SOURCE>
Subject: <TOPIC>

Write one Markdown file to workspace/knowledge_staging/designs/<kebab-slug>.md.

Front matter: id (OPT-<short>), title, type: option_paper, status: draft, owner,
last_reviewed, source_url: <SOURCE>.

Required H2 sections, in order:
## Problem
## Options          (each option with pros/cons/cost/risk as the source gives them)
## Recommendation   (the chosen option and the reasoning)
Also add when supported: ## Evaluation criteria, ## Source.

Rules: keep every option and its trade-offs; preserve the recommendation and
rationale exactly; flag gaps.
```

### Data

#### Data model  → `knowledge/reference/`  (profile: `data_model`)

```
Author a knowledge artefact of type "data_model" from the source below.

Source: <SOURCE>
Subject: <TOPIC>

Write one Markdown file to workspace/knowledge_staging/reference/data/<kebab-slug>.md.

Front matter: id (DM-<short>), title, type: data_model, status: draft, owner,
last_reviewed, source_url: <SOURCE>.

Required H2 section:
## Entities and relationships — entities, key attributes, and relationships
   (use a Mermaid ER diagram and/or a table; keep cardinalities and keys).
Also add when supported: ## Definitions, ## Ownership and source of truth,
## Source.

Rules: preserve entity/attribute names and cardinalities exactly; flag gaps.
```

#### Enterprise data model  → `knowledge/reference/`  (profile: `enterprise_data_model`)

```
Author a knowledge artefact of type "enterprise_data_model" from the source below.

Source: <SOURCE>
Subject: <TOPIC>

Write one Markdown file to workspace/knowledge_staging/reference/data/<kebab-slug>.md.

Front matter: id (EDM-<short>), title, type: enterprise_data_model, status: draft,
owner, last_reviewed, source_url: <SOURCE>.

Required H2 sections:
## Scope          — the subject areas covered.
## Core entities  — the principal entities and their meaning across UCL.
Also add when supported: ## Subject areas, ## Ownership, ## Source.

Rules: capture the canonical entity set and definitions exactly; flag gaps.
```

#### Mapping  → `knowledge/reference/`  (profile: `mapping`)

```
Author a knowledge artefact of type "mapping" from the source below — a data or
field mapping between a source and a target.

Source: <SOURCE>
Subject: <TOPIC>

Write one Markdown file to workspace/knowledge_staging/reference/data/<kebab-slug>.md.

Front matter: id (MAP-<short>), title, type: mapping, status: draft, owner,
last_reviewed, source_url: <SOURCE>.

Required H2 section:
## Source and target — a table: source field | target field | transform | notes,
   one row per mapped element, preserving every rule and exception.
Also add when supported: ## Systems involved, ## Source.

Rules: capture every mapped field and transform exactly; do not drop edge cases;
flag gaps.
```

### Governance

#### Decision (ADR)  → `knowledge/decisions/`  (profile: `decision`)

```
Author a knowledge artefact of type "decision" from the source below — an
architecture decision record.

Source: <SOURCE>
Subject: <TOPIC>

Write one Markdown file to workspace/knowledge_staging/decisions/<kebab-slug>.md.

Front matter: id (ADR-<short>), title, type: decision, status: draft, owner,
last_reviewed, source_url: <SOURCE>.

Required H2 sections, in order:
## Context    — the forces and constraints behind the decision.
## Decision   — what was decided, unambiguously.
Also add when supported: ## Consequences, ## Alternatives considered,
## Status and date, ## Source.

Rules: state the decision exactly as recorded; keep alternatives and consequences;
flag gaps.
```

### Reusable artefact templates

#### Artefact template (e.g. HLD / option-paper skeleton)  → `knowledge/reference/template/`

```
Author a reusable artefact template from the source below — a skeleton crisAI will
fill on future runs (e.g. UCL's standard HLD or option-paper structure).

Source: <SOURCE>  (UCL's house template/standard for this artefact)
Subject: <TOPIC>  (e.g. UCL High-Level Design template)

Write one Markdown file to workspace/knowledge_staging/reference/template/<kebab-slug>.md.

Front matter: id (TMPL-<short>), title, type: high_level_design (or the matching
artefact type), status: draft, template_id, owner, last_reviewed, source_url: <SOURCE>.

Reproduce the template's section structure exactly as H2/H3 headings, with a short
guidance note and a `<placeholder>` under each section showing what belongs there.
For an HLD template include at least ## Context, ## Target architecture,
## Key decisions so it validates against the high_level_design profile.

Rules: mirror UCL's official section order and naming precisely; placeholders only,
no invented content; flag any section the source leaves undefined.
```

### Raw capture

#### Intake (quick discovery capture)  → `knowledge/intake/`  (profile: `intake`)

```
Capture raw discovery notes of type "intake" from the source below. This is
non-authoritative input for later curation — speed over polish, but still grounded.

Source: <SOURCE>
Subject: <TOPIC>

Write one Markdown file to workspace/knowledge_staging/intake/<kebab-slug>.md.

Front matter: id (INTK-<short>), title, type: intake, status: draft, owner,
last_reviewed, source_url: <SOURCE>.

At least one H2 section; suggested: ## Notes, ## Open questions, ## Follow-ups,
## Source. Capture facts and quotes from the source; mark anything uncertain.

Rules: do not promote intake to a curated type without re-authoring it with the
matching prompt above; flag gaps and questions explicitly.
```

---

## Reference — type → folder → required front matter → required sections

| Type | Folder (`knowledge/…`) | Extra required front matter | Required H2 sections |
|---|---|---|---|
| principle | `principles/` | — | Scope · Statement · Implications |
| standard | `standards/{area}/` | — | Requirements |
| guideline | `reference/process/` | — | Audience · Guidance |
| landscape | `reference/landscape/` | — | Summary |
| domain | `reference/domains/` | — | Overview |
| integration | `reference/integrations/` | — | Overview |
| strategy | `strategies/` | — | (≥1 H2; use Summary · Goals …) |
| pattern (leaf) | `patterns/` | `owner` | Design overview · When to use · Implementation · NFRS · Anti-patterns or when not to use · Source · References |
| pattern (index) | `patterns/*index*.md` | — | Design overview · When to use · Implementation · Source |
| high_level_design | `designs/` | — | Context · Target architecture · Key decisions |
| low_level_design | `designs/` | — | Design overview · Components and interfaces · Deployment and operations |
| option_paper | `designs/` | — | Problem · Options · Recommendation |
| data_model | `reference/data/` | — | Entities and relationships |
| enterprise_data_model | `reference/data/` | — | Scope · Core entities |
| mapping | `reference/data/` | — | Source and target |
| decision | `decisions/` | — | Context · Decision |
| intake | `intake/` | — | (≥1 H2) |

All artefacts also require `id`, `title`, `type`, `status` and should carry
`owner`, `last_reviewed`, and `source_url`. Profiles are defined in
`registry/workspace_artifact_profiles.yaml`; the `strategy`, `guideline` folder
placement, and any new categories can be tuned there as a registry edit.
