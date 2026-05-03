# Architecture context (`workspace/context`)

Curated knowledge for **Higher Education (HE)** architecture work: colleges, universities, and federations with many systems, integrations, and strong alignment needs. This tree is what **retrieval agents** search under `context/…` when grounding answers in your organisation’s patterns, standards, and landscape.

**Audience:** Enterprise / solution architects maintaining the corpus.  
**Consumers:** crisAI agents (retrieval planner → context retrieval → synthesizer → design).

---

## Folder structure

| Path | Purpose | Typical content |
|------|---------|-----------------|
| **`principles/`** | Durable “why we exist” statements; low churn. | Integration principles, “cloud first”, data as a product at headline level. |
| **`standards/`** | **Mandatory** or conformance expectations. | Governance, reporting rules, naming, security baselines. |
| **`standards/data/`** | Data-specific standards (catalogue, quality, retention). | *(Populate as you grow.)* |
| **`standards/security/`** | Security and identity-related standards. | *(Populate.)* |
| **`standards/integration/`** | APIs, events, integration contracts, error handling. | *(Populate.)* |
| **`patterns/`** | Reusable solution patterns and **anti-patterns**. | Reporting, ingestion, ownership models. |
| **`designs/`** | Precedents and exemplar solution descriptions. | Prior dashboards, integration designs (anonymised). |
| **`decisions/`** | Lightweight **decision records** (ADR-style): context, decision, consequences. | Why we chose hub-and-spoke, why not direct DB access from reports, etc. |
| **`reference/landscape/`** | Platform capabilities, technology estate, hosting zones. | What the “data platform” does, regions, major products. |
| **`reference/domains/`** | Business / data domain background, not only IT. | Student lifecycle, finance, research data sensitivities. |
| **`reference/integrations/`** | System-to-system patterns, vendor touchpoints (no secrets). | “How we connect SIS to warehouse” at architecture level. |
| **`intake/`** | **Non-authoritative** workshop notes, raw discovery, “what we heard”. | Replace ad-hoc `notes/` over time for new material. |
| **`notes/`** | **Legacy / demo** informal notes (kept for existing crisAI tests). | Prefer **`intake/`** for new HE corpus material. |
| **`_templates/`** | Copy-paste starters. | `artefact-template.txt` |

**Rule of thumb:** If it is **approved policy**, put it under **`standards/`** or **`principles/`**. If it is **how we usually build**, use **`patterns/`**. If it is **what we decided and why**, use **`decisions/`**. If it is **background or inventory**, use **`reference/`**. If it is **raw or unapproved**, use **`intake/`**.

---

## File format

- Prefer **UTF-8** plain text **`.txt`** or **`.md`** (both work with `read_workspace_file`).
- Use **short sections** and **`##` headings** so `search_workspace_text` (line-oriented) can find distinctive phrases.
- One main topic per file; split large Word/PDF exports into several artefacts with clear names.

---

## Metadata block (recommended)

Put a **YAML front matter** block at the very top of each file so humans and future automation share the same facts. crisAI agents still read the body; the header is for consistency and citation.

```yaml
---
id: STD-GOV-001
title: Governance requirements for reporting datasets
type: standard
status: approved
owner: Enterprise Architecture
last_reviewed: 2026-05-03
applies_to: all
tags: governance, reporting, ownership, lineage
related:
  - context/patterns/access-and-ownership.txt
  - context/standards/naming-and-lineage.txt
---
```

### Field reference

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Stable ID (do not rename when the title changes). |
| `title` | Yes | Short title. |
| `type` | Yes | One of: `principle`, `standard`, `pattern`, `design`, `decision`, `landscape`, `domain`, `integration`, `intake`. |
| `status` | Yes | `draft` \| `approved` \| `retired`. |
| `owner` | Recommended | Team or role accountable for the content. |
| `last_reviewed` | Recommended | ISO date `YYYY-MM-DD`. |
| `applies_to` | Optional | Scope: `all`, portfolio names, or environment (e.g. `production-only`). |
| `tags` | Optional | Comma-separated keywords for humans / future catalogues. |
| `related` | Optional | Repo-relative paths to linked artefacts under `context/`. |

Copy from **`_templates/artefact-template.txt`** when creating a new file.

---

## Turning Word, PDF, and PowerPoint into context files

Goal: **structured, searchable text** under `context/…`, not a dump of the original binary.

### Microsoft Word (`.docx`)

1. **Save As** → **Plain Text (.txt)** or **Markdown (.md)** if you use a Markdown add-in.
2. Or use **Pandoc** (recommended for repeatable conversions):
   ```bash
   pandoc "Policy.docx" -t markdown -o "context/standards/new-standard.md"
   ```
3. **Clean up:** remove corporate boilerplate pages, split into multiple artefacts if the doc mixes unrelated topics.
4. **Add** the metadata YAML block at the top; set `type` and `status` honestly (`draft` until reviewed).

### PDF

1. **Copy-paste** from the PDF viewer into a text editor if the PDF is text-based (not scanned).
2. For **scanned** PDFs, run **OCR** first (Adobe, `ocrmypdf`, or enterprise tooling), then export text.
3. **Pandoc** does not reliably read arbitrary PDFs; prefer OCR + text export or `pdftotext` where layout is simple:
   ```bash
   pdftotext -layout "guidance.pdf" "context/patterns/guidance.txt"
   ```
4. **Fix line breaks:** PDFs often break lines mid-sentence; reflow paragraphs and add `##` headings from the original outline.
5. **Do not** paste tables as misaligned text if critical—summarise the rule in bullets or a small markdown table.

### PowerPoint (`.pptx`)

1. **Outline view** in PowerPoint: copy slide titles and bullet lists into a `.txt` / `.md` file.
2. Or **Pandoc**:
   ```bash
   pandoc "Architecture-Overview.pptx" -t markdown -o "context/reference/landscape/overview.md"
   ```
3. One deck often maps to **one** `reference/` or `patterns/` file per major theme; split if slides cover unrelated decisions.
4. Speaker notes can hold nuance—include them under a `## Speaker notes` section only if approved for the corpus.

### Quality checklist before commit

- [ ] Metadata block present with `id`, `type`, `status`.
- [ ] Headings and bullets reflect the **original intent**, not only layout.
- [ ] No passwords, API keys, or personal data (use anonymised examples).
- [ ] `related` links point at real paths under `context/`.
- [ ] File name is readable: e.g. `governance-standard.txt` or `STD-GOV-001-governance.txt`.

---

## Retrieval behaviour (for authors)

- Agents work best when **no single file** contains the entire answer to a complex question; **cross-link** related artefacts.
- The **retrieval planner** benefits from explicit **paths** (e.g. `context/patterns/reporting-patterns.txt`) in user prompts or handoffs.
- **Short** search queries and scoping under `context/…` beat one long sentence in `search_workspace_text`.

---

## Synthetic corpus note

Some files under **`notes/`**, **`patterns/`**, **`standards/`**, **`designs/`**, and **`reference/`** were created as a **provisional test corpus** for crisAI. As you replace them with HE-specific content, keep filenames stable or update any lab prompts that refer to them. New informal material should go to **`intake/`**; new reference splits use **`reference/landscape/`**, **`reference/domains/`**, and **`reference/integrations/`** as appropriate.
