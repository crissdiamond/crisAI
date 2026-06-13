# Knowledge Base Programme

How to use crisAI to build the institutional knowledge base — the principles,
standards, patterns, templates, processes, strategies, goals, and landscape that
ground every architecture answer — with **mandatory human review** and a
**team-wide contribution model**.

This is a strategy document, not a tool change. It is grounded in what crisAI
has today (`workspace/knowledge` ↔ `workspace/knowledge_staging`, artefact
validation, peer mode, the Microsoft 365 / intranet adapters) and is explicit
about what is planned but not yet built.

For the ready-to-use, copy-paste authoring prompts (one per artefact type) that
team members run against their source files, see
`reference/knowledge-authoring-prompts.md`.

---

## 1. Operating principle: knowledge-as-code

The knowledge base already *is* a tree of diffable Markdown under
`workspace/knowledge/` with required YAML front matter and a validator
(`crisai validate-artefacts`). So we run it like the codebase:

> **crisAI drafts → a human reviews → a PR promotes → CI validates → everyone pulls.**

Automation does the reading and structuring; the human owns the judgment and the
approval. This maps directly onto crisAI's product philosophy:

- *User control at costly decisions* — knowledge promotion is explicit and
  inspectable (VISION Principle 3).
- *Markdown as source* — diffable, reviewable, easy to validate (Principle 6).
- *No autonomous promotion* — "a hidden autonomous actor that writes or promotes
  knowledge without user confirmation" is an explicit non-goal.

The mandatory human gate is **structural, not just policy**: agents can write
only to `knowledge_staging/` (`access: read_write`), never to `knowledge/`
(`access: read`); and staging is excluded from production retrieval
(`retrieval_priority: 50`). A draft therefore never influences a grounded answer
until a human promotes it. (See `registry/workspace_spaces.yaml`.)

---

## 2. Recommendation: where the shared knowledge base lives

**Recommendation: a dedicated knowledge git repository**, wired into each
member's crisAI as `workspace/knowledge` (a git submodule is the cleanest
binding; a configured clone path is the lighter-weight alternative).

### Why a separate repo

- **Least privilege / different communities.** Architects and SMEs who curate
  knowledge should not need write access to the crisAI tool code, and tool
  maintainers should not gate knowledge edits. Separate repos = separate access
  control and separate review communities.
- **Independent lifecycle.** Knowledge changes daily; tool code changes on its
  own rhythm. Separate history keeps both clean and makes "what changed in the
  knowledge base this week" answerable without tool-code noise.
- **The tool stays generic.** crisAI is meant to be tuned per organisation
  without code changes (a stated success criterion). Keeping an organisation's
  content out of the tool repo means one tool, many knowledge repos (per team or
  per org), and clean open-sourcing/sharing of the tool itself.
- **`workspace/` is local runtime data.** Curated knowledge is a deliberate
  artefact set, not scratch workspace state; it deserves its own versioned home.

### Trade-offs (and the lighter alternative)

- A separate repo adds a clone/submodule step and a one-time wiring of the
  workspace path. This is configuration, not code: workspace roots are already
  configurable (`registry/workspace_spaces.yaml`, `CRISAI_WORKSPACE_DIR`).
- Submodules have some UX friction (`git submodule update --remote` to pull
  latest). If the team finds that heavy, the alternative is a plain clone of the
  knowledge repo into `workspace/knowledge` with that path git-ignored by the
  tool repo — same contribution flow, slightly more manual sync.
- **When a single repo is acceptable:** a one- or two-person pilot can start with
  knowledge as a folder in the crisAI repo to avoid setup, then split it out
  before onboarding the wider team. Do not let a pilot's single-repo convenience
  become the team default — the access-control reasons above still apply.

### Wiring summary

```
knowledge repo (curated Markdown, CI-validated)
        │ git submodule / clone
        ▼
crisAI workspace/knowledge   ← retrieval grounds here (priority 10, read-only to agents)
crisAI workspace/knowledge_staging ← agents draft here (read-write, not retrieved)
```

---

## 3. Part A — Automating creation, with a mandatory human gate

### The repeatable loop (one artefact at a time)

```
SOURCE ──▶ 1.HARVEST ──▶ 2.DRAFT ──▶ 3.VALIDATE ──▶ 4.HUMAN REVIEW ──▶ 5.PROMOTE
(intranet,   (retrieval    (author into   (crisai          (mandatory)        (git PR →
 SharePoint,  agents read   knowledge_     validate-                           knowledge/)
 docs, decks) the source)   staging/,      artefacts)
                            status:draft)
```

| Step | Who / what | crisAI mechanism |
|---|---|---|
| 1. Harvest | retrieval agents | `intranet_*` tools (the `it-architecture` and wiki sites are configured in `registry/intranet.yaml`), `sharepoint_docs`, `search_my_onedrive`, `documents` for local decks/PDFs |
| 2. Draft | authoring agents | write to `workspace/knowledge_staging/<category>/`, `status: draft`, full front matter, required sections, and a `source_url` / provenance line (enforced by `prompts/_shared/knowledge-staging.md`) |
| 3. Validate | automated | `crisai validate-artefacts` checks front matter + required H2 sections per profile (`registry/workspace_artifact_profiles.yaml`) — catches structural gaps before a human looks |
| 4. Review | **human (mandatory)** | open the staged file in the web workspace editor, check it against the cited source, fix, set `status: approved`, `owner`, `last_reviewed` |
| 5. Promote | human via git | move `knowledge_staging/… → knowledge/…` and open a PR against the knowledge repo |

### Choosing the authoring mode

- **Durable, high-stakes knowledge (principles, standards, strategies)** → run in
  **peer mode** (author → challenger → refiner → judge). The challenger and judge
  catch unsupported claims, which matters most for the knowledge everything else
  grounds on. Trigger with "peer mode" / "challenge and refine"
  (`registry/semantic_catalog.yaml`).
- **High-volume, well-structured knowledge (patterns, landscape entries)** →
  single or pipeline mode. **For catalogues this is critical:** the staging rules
  require drilling into leaf pages (`intranet_list_page_links_by_id` →
  `intranet_fetch_page`) before writing — never let a run merely restate an
  index page.

### Sequence by leverage (stability × grounding value)

Build the durable, high-grounding layers first so later drafts stand on them:

1. **Principles** — `knowledge/principles/` (profile: Scope / Statement / Implications).
2. **Standards** — `knowledge/standards/{data,security,integration}/` (profile: Requirements).
3. **Institution context** — `reference/landscape/` (platforms, estate),
   `reference/domains/` (business/data domains), `reference/integrations/`
   (system touchpoints), `organisation/` (roles, structure).
4. **Patterns** — `knowledge/patterns/` (profile `integration_pattern_leaf`:
   7 required sections + slug-dedup check); drill-down heavy.
5. **Templates** — `reference/template/` (HLD, options paper, ADR, …). Doubles as
   knowledge and as the scaffolds future runs reuse (relates to the template
   library, TODO-006).
6. **Strategies / goals / programmes** — `strategies/`, `programmes/`. Highest
   churn; build last and review most often.

---

## 4. Part B — Team collaboration & sharing

crisAI is local-first, so the sharing layer is **git**, not the tool itself.

- **One shared knowledge repository** (per §2). Markdown is the lingua franca —
  diffable, reviewable, no document-management system needed.
- **Contribution = PR flow.** A contributor uses their local crisAI to
  harvest + draft into staging, reviews, promotes into their clone's
  `knowledge/`, and opens a PR. Peers review the **diff** — a content review,
  the same shape as a code review.
- **`crisai validate-artefacts` as a CI gate** on the knowledge repo: every PR
  must pass front-matter + structure validation before merge, making
  "well-formed knowledge" a machine-enforced invariant.
- **Ownership & freshness via front matter.** `owner` drives CODEOWNERS-style
  review routing; `last_reviewed` enables a scheduled "review overdue" report.
- **Everyone benefits automatically.** Each member pulls the shared repo and
  their retrieval agents ground every answer in the team's collective curated
  corpus (priority-10 approved knowledge). One person's curation becomes
  everyone's grounding.

In short: **author locally, review as a diff, validate in CI, share by pull.**
The mandatory-review requirement and the no-autonomous-promotion non-goal are
satisfied by the PR gate itself.

---

## 5. Roles & cadence

- **Contributors** (any architect): run the harvest→draft loop; self-review; open PRs.
- **Domain owners** (named in front-matter `owner`): accountable reviewers for
  their category; approve promotion PRs.
- **Knowledge maintainer** (rotating): watches CI, taxonomy drift, and the
  `last_reviewed` staleness report; curates the template library.
- **Cadence:** principles/standards reviewed quarterly; landscape/patterns
  monthly or on change; strategies/programmes whenever the source changes.
  Anything past its `last_reviewed` window gets flagged, not silently trusted.

---

## 6. Honest gaps to plan around

- **Promotion is manual today** (file move + git PR). The planned `/promote`
  workflow — provenance fields, staged/approved status, front-matter validation
  (TODO-007) — would turn step 5 into a governed in-tool action. The programme
  works now with the manual + PR flow; TODO-007 is the natural first tool
  improvement *after* the loop is proven.
- **Some categories lack validation profiles.** `strategies`, `programmes`, and
  `organisation` are enumerated in `workspace_spaces.yaml` but currently fall
  back to `defaults`. Adding profiles is a registry edit, low effort.
- **No retrieval cache yet** (TODO-003). Bulk harvesting re-reads sources; fine
  for a curation programme, but watch token spend.

---

## 7. Phasing

- **Phase 0 — Pilot (1 category, 1 source).** Stand up the knowledge repo + CI
  validation; run the full loop end-to-end on ~5 *principles* harvested from the
  intranet. Prove the harvest→review→promote loop and the team PR flow.
- **Phase 1 — Foundations.** Principles + standards + core landscape/domains.
  Establish owners and the review cadence.
- **Phase 2 — Scale.** Patterns (with drill-down), the template library, then
  strategies/programmes. Add validation profiles for the new categories.
- **Phase 3 — Tool-assist.** Build TODO-007 promotion tooling and a
  "stale knowledge" report once the manual loop is well understood.

---

## Appendix — category → folder → profile → typical source

| Knowledge type | Folder (`workspace/knowledge/…`) | Validation profile | Typical source |
|---|---|---|---|
| Principle | `principles/` | `principle` | Architecture principles pages, strategy docs |
| Standard | `standards/{data,security,integration}/` | `standard` | Governance & standards docs |
| Pattern | `patterns/` | `integration_pattern_leaf` | Intranet pattern catalogue (leaf pages) |
| Design precedent | `designs/` | `high_level_design_template_or_knowledge` | Past HLDs / exemplar solutions |
| Decision | `decisions/` | `decision` | ADRs, governance minutes |
| Landscape | `reference/landscape/` | `defaults` | Estate inventories, platform docs |
| Domain | `reference/domains/` | `defaults` | Business/data domain material |
| Integration | `reference/integrations/` | `defaults` | System-to-system / vendor docs |
| Template | `reference/template/` | `high_level_design_template_or_knowledge` | Curated artefact skeletons |
| Strategy / programme | `strategies/`, `programmes/` | `defaults` (profiles TBD) | Strategy decks, programme plans |

Profiles and roots are defined in `registry/workspace_artifact_profiles.yaml`
and `registry/workspace_spaces.yaml`; adjusting them is a registry edit, not a
code change.
