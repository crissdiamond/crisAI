# Architecture context (`workspace/context`)

Curated knowledge for **Higher Education (HE)** architecture work: colleges, universities, and federations with many systems, integrations, and strong alignment needs. This tree is what **retrieval agents** search under `context/…` when grounding answers in your organisation’s patterns, standards, and landscape.

**Audience:** Enterprise / solution architects maintaining the corpus.  
**Consumers:** crisAI agents (retrieval planner → context retrieval → synthesizer → design).

## Context staging (drafts)

**Agent-generated** context files (e.g. from intranet extraction or Copilot drafts awaiting review) belong under **`workspace/context_staging/`**, mirroring the folder layout you intend in `context/`. Humans **promote** approved files into **`workspace/context/`**; the approved tree is what retrieval searches by default. Rules: **`prompts/_shared/context-staging.md`** and **`workspace/context_staging/README.md`**.

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
| **`patterns/archive/`** | **Retired** snapshots kept for comparison or audit. | Superseded integration summaries; canonical catalogue remains under `patterns/*.md`. |
| **`designs/`** | Precedents and exemplar solution descriptions. | Prior dashboards, integration designs (anonymised). |
| **`decisions/`** | Lightweight **decision records** (ADR-style): context, decision, consequences. | Why we chose hub-and-spoke, why not direct DB access from reports, etc. |
| **`reference/landscape/`** | Platform capabilities, technology estate, hosting zones. | What the “data platform” does, regions, major products. |
| **`reference/domains/`** | Business / data domain background, not only IT. | Student lifecycle, finance, research data sensitivities. |
| **`reference/integrations/`** | System-to-system patterns, vendor touchpoints (no secrets). | “How we connect SIS to warehouse” at architecture level. |
| **`intake/`** | **Non-authoritative** workshop notes, raw discovery, “what we heard”. | Replace ad-hoc `notes/` over time for new material. |
| **`notes/`** | **Legacy / demo** informal notes (kept for existing crisAI tests). | Prefer **`intake/`** for new HE corpus material. |
| **`_templates/`** | Copy-paste starters. | `integration-pattern-artefact-template.txt` |

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

Copy from **`_templates/integration-pattern-artefact-template.txt`** when creating a new integration pattern file.

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

### Artefact structural validation

For automated checks beyond this README (required headings per `type`, integration-pattern slug dedup, and similar rules), configure profiles in **`registry/workspace_artifact_profiles.yaml`** and run **`crisai validate-artefacts`** from the repo root. Peer mode applies the same rules to changed Markdown under `context/` and `context_staging/`.

### Quality checklist before commit

- [ ] Metadata block present with `id`, `type`, `status`.
- [ ] Headings and bullets reflect the **original intent**, not only layout.
- [ ] No passwords, API keys, or personal data (use anonymised examples).
- [ ] `related` links point at real paths under `context/`.
- [ ] File name is readable: e.g. `governance-standard.txt` or `STD-GOV-001-governance.txt`.

---

## Using Microsoft 365 Copilot to transform existing architecture documents

Use **Microsoft 365 Copilot** (the institution’s **Microsoft 365 / Office 365** assistant—e.g. in **Word**, **PowerPoint**, **Outlook**, **Teams**, or **Copilot** in the browser where your tenant allows it). Paste the prompts below into the Copilot chat alongside your source, or paste the **output** into a new Word document and then **Save As** plain text / Markdown into **`workspace/context_staging/…`** first; after human review, promote into **`workspace/context/…`**.

The goal is a **single crisAI-ready artefact** per file: YAML front matter + short sections + bullets—aligned with this README and **`_templates/integration-pattern-artefact-template.txt`**.

**Before you start**

1. Keep this README and **`_templates/integration-pattern-artefact-template.txt`** open (in the repo, SharePoint, or pasted at the top of your Copilot prompt) so the model follows the same metadata rules.
2. Decide the target **folder** (`standards/`, `patterns/`, `decisions/`, etc.) and a **proposed filename** under staging (e.g. `context_staging/standards/integration/API-error-handling.txt`); move to `context/…` after approval.
3. Provide the **source text** in the Copilot conversation or attach a file **your tenant policy allows** (anonymise secrets and personal data first).
4. **Respect your organisation’s Copilot and data policies** (what may be uploaded, retention, and approval for `status: approved`).

**Base prompt (adapt the bracketed parts)**

```text
You are helping build the architecture context corpus for crisAI. Save drafts under workspace/context_staging (mirror of context/ layout); humans promote to workspace/context after review.

Source material is below between ---SOURCE--- markers.

Task:
1. Produce ONE artefact as UTF-8 plain text suitable for saving as [FILENAME under context_staging/…].
2. Start with a YAML front matter block exactly as described in workspace/context/README.md (fields: id, title, type, status, owner, last_reviewed, applies_to, tags, related). Use type=[principle|standard|pattern|design|decision|landscape|domain|integration|intake]. Set status=draft unless I say otherwise. Invent a sensible stable id prefix (e.g. STD-INT-001). Leave related: empty or list plausible context/ paths only if you are sure they exist.
3. Body: use ## headings and bullets; short paragraphs; line-oriented phrasing for search. Include explicit "Anti-pattern" or "When not to use" sections where relevant.
4. Remove boilerplate, version history tables, and duplicate slides. Do not invent organisation-specific facts not in the source.
5. End with no extra commentary outside the file content.

---SOURCE---
[paste source text here]
---SOURCE---
```

**Prompt: split a long policy pack into multiple files**

```text
The source is a long document mixing several topics. Split it into separate crisAI artefacts.

For EACH distinct topic, output:
- A suggested path under workspace/context_staging/ (folder + filename); final promotion to context/ is human-led.
- The full file content (YAML front matter + body) for that topic only.

Rules: one main topic per file; cross-link using related: paths between files you create in this batch; same metadata conventions as workspace/context/README.md.
```

**Prompt: turn a slide deck export into a landscape or pattern file**

```text
Source is bullet text from a PowerPoint deck (titles and bullets pasted below). Transform into one markdown or plain-text artefact for context_staging/reference/landscape/ OR context_staging/patterns/ (you choose based on content). Preserve slide structure only as ## headings, not as "Slide 3". Add YAML front matter; type=landscape or pattern; tags from HE architecture (integration, data platform, identity, etc.). Promote to context/… after review.
```

**Prompt: draft an ADR in `decisions/`**

```text
From the source narrative below, produce a lightweight ADR for workspace/context_staging/decisions/ (promote to context/decisions/ after review). YAML front matter with type=decision. Body sections: ## Context, ## Decision, ## Consequences, ## Alternatives considered (short). No solution design detail that belongs in patterns/; focus on why we decided.
```

**Prompt: raw workshop notes → `intake/`**

```text
Turn these messy workshop notes into a single intake file for context_staging/intake/. YAML: type=intake, status=draft. Body: ## Attendees (optional anonymised), ## Raw themes, ## Open questions, ## Suspected links to standards/patterns (hypotheses only). Keep informal tone; flag uncertainty. Promote to context/intake/ after review if appropriate.
```

**Prompt: add `related:` links after files already exist**

```text
Here is the body of an existing context file (below). List 3–8 other plausible paths under context/ that should be linked. Output ONLY an updated YAML front matter block with a filled related: list using paths that exist in this repo (infer from workspace/context tree if needed). Do not change the body.

---FILE---
[paste file content]
---FILE---
```

**Tips**

- **Iterate:** send the base prompt, then a follow-up in the same Copilot thread: e.g. “Shorten section X to 8 bullets” or “Add anti-patterns.”
- **In Word:** paste rough text, open **Copilot**, and ask it to rewrite the selection using the metadata and heading rules from the prompt you pasted; copy the result into a `.txt`/`.md` file in the repo.
- **Verification:** run through the **Quality checklist** above and have a human architect set `status: approved` after review.

---

## Retrieval behaviour (for authors)

- Agents work best when **no single file** contains the entire answer to a complex question; **cross-link** related artefacts.
- The **retrieval planner** benefits from explicit **paths** (e.g. `context/patterns/reporting-patterns.txt`) in user prompts or handoffs.
- **Short** search queries and scoping under `context/…` beat one long sentence in `search_workspace_text`.

---

## Synthetic corpus note

Some files under **`notes/`**, **`patterns/`**, **`standards/`**, **`designs/`**, and **`reference/`** were created as a **provisional test corpus** for crisAI. As you replace them with HE-specific content, keep filenames stable or update any lab prompts that refer to them. New informal material should go to **`intake/`**; new reference splits use **`reference/landscape/`**, **`reference/domains/`**, and **`reference/integrations/`** as appropriate.
