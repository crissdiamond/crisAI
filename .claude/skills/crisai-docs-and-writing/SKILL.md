---
name: crisai-docs-and-writing
description: Use when writing or updating any crisAI documentation or repo prose — README.md, DOCUMENTATION.md, TESTING.md, reference/TODO.md rows, a new or amended ADR under reference/decisions/, a commit message body, or the CLAUDE.md/AGENTS.md/GEMINI.md instruction files. Also load when two docs contradict each other and you need to know which one wins, when checking whether a doc statement is known-stale, or when matching the house style (British spelling, post-mortem commit bodies, TODO/ADR templates).
---

# crisAI docs and writing

Runbook for authoring and maintaining this repository's documentation: which document owns which facts, which wins on conflict, the mandatory update obligations, the house templates (ADR, TODO row, commit body), the house style, and the known-stale statements you must not trust or propagate. All file references verified against the repo on 2026-07-02.

## 1. Docs of record — what each doc owns

| Doc | Owns | Notes |
|---|---|---|
| `README.md` | Quick start, feature summary, repository map | Self-declares (line 7): "This README is the quick start. The full operator manual is DOCUMENTATION.md." |
| `DOCUMENTATION.md` | The operator manual: runtime behaviour, modes, agents, router, retrieval discipline, workspace model, SharePoint/Graph, model/provider assignment, prompting patterns, smoke tests, logs (§1–§19) | Explicitly excludes the repo development process (§3.1 → `reference/development/README.md`) and defers deterministic-retrieval detail (line 1167) to the dedicated doc |
| `DOCUMENTATION_DETERMINISTIC_RETRIEVAL.md` | Deterministic retrieval context, semantic-graph lifecycle, advisory MCP lookup, precedence and fail-open rules | |
| `TESTING.md` | Test-suite layout, run commands, CI mirror commands, troubleshooting | **Known stale in two places** — see §7 before trusting it |
| `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` | Process rules for AI contributors (one copy per assistant brand) | Byte-identical, **gitignored** (`.gitignore:42-44`), absent from fresh clones — see §4 |
| `reference/VISION.md` | Product principles, non-goals, technology decisions, near-term direction | Mandatory read before planning any improvement (CLAUDE.md rule) |
| `reference/TODO.md` | The backlog: item IDs, priorities, statuses, Definition of Done, sequencing, Done log | Maintenance rules live in its own "How To Maintain" section — see §5.2 |
| `reference/decisions/CRISAI-ADR-001..015` + `README.md` index | Durable architecture decisions about crisAI itself (not customer knowledge, not task artefacts) | House format in §5.1 |
| `runbooks/01-setup.md` … `05-security.md` | Operational notes: setup, registry/servers, agents/policies, observability, security | Currency against current behaviour is **unverified** as of 2026-07-02 — re-check before quoting |
| `reference/development/` | The hcom multi-agent development-team process | Operating it → sibling `crisai-devteam-operations` |
| `reference/knowledge-base-programme.md`, `knowledge-authoring-prompts.md`, `workspace_context_generation.md` | Knowledge-as-code programme and authoring guidance | |
| `src/crisai/apps/.style.md` | UCL Design System spec for UI surfaces | Dot-prefixed — easy to miss with plain `ls`; it **does** exist |

One home per fact: when a behaviour is documented in `DOCUMENTATION.md`, other docs should link to it, not restate it.

## 2. Authority map — which doc wins on conflict

Resolution ladder, strongest first:

1. **Running code and CI configuration** (`.github/workflows/ci.yml`, `pyproject.toml`, the source itself) beat every prose doc. The repo's own rule: never assume code behaviour — inspect it.
2. **`DOCUMENTATION.md`** beats `README.md` and `TESTING.md` on behaviour detail (README defers to it by design; TESTING.md has a slower update cadence in practice).
3. **An ADR file's own `Status:` line** beats the index table in `reference/decisions/README.md` (the index is known to lag — ADR-012 is `superseded` in-file but still listed `accepted` in the index as of 2026-07-02).
4. **`reference/TODO.md` Done rows and merged-commit bodies** beat ADR narrative on *implementation status*. The ADR stays authoritative on the *decision and rationale*; the Done log says how far the build actually got (worked example: ADR-013 vs TODO-017 in §7).
5. **`CLAUDE.md`** governs process rules, except its "Web and mobile UI" section, which is owner-confirmed stale (§7).

**Worked example — the pip-audit conflict.** `TESTING.md:220-239` documents a local pip-audit command with four `--ignore-vuln` suppressions (CVE-2026-35029, CVE-2026-35030, GHSA-69x8-hrgq-fjj8, CVE-2026-42271) plus a paragraph saying the ignores last until the OpenAI 2.x SDK migration. That migration shipped: commit `a010c8f` (PR #46, 2026-07-01) moved to the OpenAI 2.x line, removed all suppressions from CI, and its body states "DOCUMENTATION.md updated to match" — TESTING.md was not updated (last touched 2026-06-12). Today `ci.yml:48-53` runs pip-audit with an explicit "No suppressions" comment and `DOCUMENTATION.md` (~line 385) states the same. **DOCUMENTATION.md + CI win; TESTING.md loses.** If you find such a conflict, fix the losing doc in the same commit as your change or file a TODO row — do not copy the stale command forward.

## 3. Update obligations (non-negotiable, from CLAUDE.md)

| Trigger | Obligation |
|---|---|
| Any change affecting usage, architecture, setup, or behaviour | Update **both** `README.md` and `DOCUMENTATION.md` in the same improvement (CLAUDE.md:19) |
| Changing, adding, or removing tested behaviour | Add/update tests under `tests/`, and keep `TESTING.md` §2/§5 in step (its file inventory is already 19 files behind — do not widen the gap) |
| Completing a TODO item | Move it to the `Done` table in `reference/TODO.md` with the merge commit or PR reference |
| A backlog item becomes architecture-shaping | Add or update an ADR in `reference/decisions/` and link it from the TODO row |
| Adding or superseding an ADR | Update the ADR file's `Status:` line **and** the index table in `reference/decisions/README.md` (the index drifted once already — ADR-012) |
| Editing AI-contributor rules | Keep `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` byte-identical (§4) |
| Each improvement | One Conventional Commit at the end; then `gh run list --branch main --limit 3` and report failures. No `Made-with: Cursor` trailer. Do not push unless asked. |

Work on **one improvement at a time**; the doc update rides the same commit as the change it documents, never a separate "docs catch-up" pile.

## 4. The CLAUDE.md / AGENTS.md / GEMINI.md triplet

Verified 2026-07-02:

- All three are **byte-identical** (`cmp` clean on both pairs) and **gitignored** (`.gitignore:42-44`, under the comment "Coding assistant instructions (local to each developer's toolchain)"). `git ls-files` returns none of them — a fresh clone has **no** contributor rules until they are restored locally.
- **Sync obligation**: any edit to one must be copied verbatim to the other two in the same session. Verify with:
  `cmp CLAUDE.md AGENTS.md && cmp CLAUDE.md GEMINI.md && echo in-sync`
- No canonical upstream copy is recorded in the repo; if the three ever drift, escalate to the owner rather than guessing which is the source. (Open question on record; unresolved as of 2026-07-02.)
- Because they are untracked, changes to them never show in `git diff` — do not rely on git to catch drift.

## 5. Templates

### 5.1 ADR house format

Files live at `reference/decisions/CRISAI-ADR-0NN-kebab-slug.md`; add a row to the index table in `reference/decisions/README.md`. The index README specifies the elements (`Status`, `Date`, `Context`, `Decision`, `Consequences`, `Related`); current practice (ADR-014, ADR-015 — the freshest exemplars) renders them as:

```markdown
# CRISAI-ADR-0NN: Title In Title Case

Status: accepted
Date: 2026-MM-DD

## Context

Why the decision was needed. House habits from ADR-015:
- Name the concrete, reproducible motivating failure (session id, date,
  the user's exact phrasing, what failed and where — e.g. "session Test001,
  2026-06-14 ... failed at the policy gate").
- State the root cause explicitly AND what it is NOT ("The root cause is
  **not** the lock file ...").
- Record rejected workarounds and who rejected them ("The user explicitly
  rejected workarounds for this critical backbone").
- Cross-reference the prior ADRs this builds on, inline by id.

## Decision

What was chosen. Use `### numbered subsections` for multi-part decisions
(ADR-015: "### 1. Durable source anchors", "### 2. Workspace evidence
materialisation", "### Control and safety"). Bold the load-bearing clauses.

## Consequences

Trade-offs and implementation implications, as bullets. Name the TODO item
that tracks implementation ("Implementation is tracked under TODO-048").

## Residual risk        <- optional; ADR-015 adds it: risk → mitigation pairs
```

- `Status` vocabulary: `proposed`, `accepted`, `superseded`, or `retired`.
- ADRs are for durable decisions about crisAI itself — not customer/domain knowledge (→ `workspace/knowledge/`), not generated task artefacts (→ `workspace/tasks/<task>/artefacts/`).
- `Related` links are woven inline in Context/Consequences in current practice rather than given their own heading; either is acceptable, inline is the observed norm.
- The ADR records the principle; implementation state lives in TODO/commits (authority rule §2.4). Do not retro-edit an ADR every time a slice lands, but do fix statements that have become actively misleading (see ADR-013 in §7).

### 5.2 TODO row format and maintenance

`reference/TODO.md` structure: `How To Maintain` → `Current Codebase Review` → `Backlog` (line ~94) → `Recommended Sequencing` (~141) → `Done` (~176).

Backlog table columns (verified at TODO.md:96):

```markdown
| ID | Priority | Status | Item | Rationale | Definition of Done |
```

- **ID**: `TODO-NNN`, stable forever — IDs are references, **not** priority order after insertions. Execution order comes from the `Priority` column plus the `Recommended Sequencing` section.
- **Status** vocabulary: `todo`, `planned`, `in-progress`, `blocked`, `done`, `dropped`.
- **Priority** vocabulary: `P0` blocks the supported local team-adoption target; `P1` next reliability/security/core-product track; `P2` medium-term capability or maintainability; `P3` optional polish or a conditional future surface.
- **Rationale** = why it matters now; **Definition of Done** = a concrete, verifiable completion statement (read TODO-051 at line 99 for the register: exhaustive, testable, one cell).
- Split any item that cannot be completed and verified in one focused change.
- Keep semantics in registry files unless the item is explicitly infrastructure.
- One ownerless backlog; no assignee column until the team adopts issue tracking.

**Done-table migration rule**: completed items move (not copy) to the `Done` table with the merge commit or PR reference:

```markdown
| ID | Item | Reference |
| TODO-042 | Rate limiting on execution endpoints | `8badc2e feat(web): add per-minute rate limit on execution endpoints`, ... |
```

Supersessions are recorded as prose in the Done row rather than deleted (see TODO-019 "Superseded by …" and TODO-040B, whose row explains the modal that replaced the original sticky-banner idea). Phase completions also live in the Done row (TODO-017's row records that ADR-013's Phase 2 shipped) — which is why Done rows outrank ADR text on implementation status.

### 5.3 Commit-body post-mortem template

Since PR #21 (2026-06-13) changes land as **squash merges**: one commit on main titled `type(scope): imperative subject (#N)`. The body is a full post-mortem and doubles as the test-count ledger. Template, distilled from merged exemplars `2f41bec`, `b386a17`, `1749a65`, `a010c8f` (read them with `git log --format=%B -1 <hash>`):

```text
type(scope): imperative subject (#N)

<Symptom + named reproduction>: which live session or eval surfaced it
(Test006 root cause ...; "a live check confirmed the cause: ...") and the
observable failure.

<Root cause>: one mechanism that explains all observations — state it
plainly, including what it is NOT.

<Fix>: what changed and WHY structurally ("Structural fix (separation of
concerns): ..."). Name rejected alternatives and deliberate calls
("Per the user's call, the inventory gate keeps its hard failure ...").

<Side changes>: registry/docs updated in the same commit
("DOCUMENTATION.md updated to match", "registry source_scope_markers ...").

<Tests>: what the new tests cover.

Full suite green (N passed; ruff + mypy clean).

<Deferred follow-ups>: explicitly named, with where they are tracked
("Remaining audit Tier-2 (...) is a separate registry-tightening follow-up").

Co-authored-by: <AI tool name> <noreply@anthropic.com>
```

- The ledger line is a house convention: `Full suite green (N passed; ruff + mypy clean)` with N growing monotonically across commits (…860 → 862 → 863…). A fuller variant appears when relevant: `Full unit suite (885 passed, 11 skipped, 85% coverage)` (a010c8f). Include it in every code commit; it is the only place suite size is tracked. Obtain N from the actual run — never estimate it.
- Multi-slice campaigns name their position and successor: "Phase 2b complete (slices 1, 2, 3a, 3b, 4a, 4b)", "Next: slice …".
- No `Made-with: Cursor` trailer, ever (CLAUDE.md:22).
- Branch/PR/squash mechanics, gating, and the squash-drops-late-commits trap are owned by sibling `crisai-change-control` — this section only owns the prose format.

## 6. House style

- **British spelling in prose**: materialise, artefact, behaviour, honour(s), authorisation, catalogue, prioritise. Verified dominant across DOCUMENTATION.md, TODO.md, VISION.md, CLAUDE.md, ADRs, and commit bodies.
- **Exception — identifiers keep their existing spelling.** `registry/workspace_artifact_profiles.yaml`, `produce_artifacts`, `publish_artifact`, `artifact_package` are American and correct as-is: never "fix" the spelling of a code/config identifier, and never invent a British-spelled identifier alias. Known prose lapse: `DOCUMENTATION_DETERMINISTIC_RETRIEVAL.md` intro uses "behavior"; follow the British norm in new text regardless.
- **Imperative, declarative voice**: "Run validation manually:", "Use it to find source material…". Rules are stated as obligations, not suggestions.
- **One improvement at a time** (CLAUDE.md:9): a doc PR covers one coherent change; do not batch unrelated doc fixes.
- **Always respond in English**, even when the user writes Italian (CLAUDE.md:11).
- Structure conventions observed in the docs of record: a one-line bold blockquote summary under the H1 (`> **Guide to the current test suite…**`); numbered `## N.` sections in the manuals; **bold** for load-bearing terms and file names on first mention; backticks for every path, flag, env var, and identifier; tables for anything enumerable.
- Name the evidence: docs and commit bodies cite session ids (Test001…), commit hashes, ADR ids, and TODO ids rather than saying "recently" or "a previous fix".
- Google-style code comments, only where needed for clarity (CLAUDE.md rule).

## 7. Known staleness inventory — as of 2026-07-02

Statements currently on disk that are wrong or lagging. Do not propagate them; fix them only as their own focused improvement (or alongside a change that touches the same area).

| # | Location | Stale statement | Reality (verified 2026-07-02) |
|---|---|---|---|
| 1 | `TESTING.md:220-239` | Local pip-audit command with four `--ignore-vuln` suppressions + rationale paragraph ("remove when … OpenAI 1.x to 2.x") | Migration shipped in `a010c8f` (#46, 2026-07-01); CI (`ci.yml:48-53`) and DOCUMENTATION.md (~385) run/state **no suppressions**. TESTING.md last touched 2026-06-12. |
| 2 | `TESTING.md` §2 test layout | Lists 53 files under `tests/unit/` | 72 exist on disk — 19 missing, including `test_source_cache.py`, `test_source_materialisation.py`, `test_request_contract.py`, `test_session_anchors.py`, and `test_usage_cost.py` (which TESTING.md itself invokes at line 269) |
| 3 | `CLAUDE.md:29-37` "Web and mobile UI" section (and its AGENTS/GEMINI twins) | Front end at `src/crisai/apps/ui/` with separate vanilla HTML/CSS/JS files, FastAPI-served statics, no build step | **Owner-confirmed stale.** `src/crisai/apps/ui/` does not exist; real surfaces are the Vite-built React app `ui/apps/web/` and the Ink terminal app `ui/apps/gem/`. The UCL Design System spec (`src/crisai/apps/.style.md` — exists), design tokens, semantic HTML, and WCAG 2.1 AA obligations still apply to the React client; the location/no-build/separate-files rules are legacy. Details → sibling `crisai-ui-surfaces`. |
| 4 | `reference/decisions/CRISAI-ADR-013…md` (Decision/Consequences) | "This ADR covers **Phase 0–1**"; "Until the Phase-2 migration lands, prompt guidance remains hardcoded" | Phase 2 shipped — TODO-017's Done row records `render_source_tool_guidance` generating retrieval guidance from the contract, hardcoded intranet/SharePoint tool lists removed. The Done row outranks the ADR narrative (§2.4). |
| 5 | `reference/decisions/README.md` index | Lists ADR-012 as `accepted` | The ADR file itself says `Status: superseded` (prompt-toolkit CLI replaced by Ink Gem + React web) |
| 6 | `src/crisai/workspace/source_cache.py` module docstring (also lines ~71, ~92) and `src/crisai/orchestration/source_materialisation.py` docstring | Cache lives under the task's `.crisai/sources/…`; "Wiring the live fetch at the retrieval checkpoint and the read-through into the retrieval loop is a **separate slice**" | Slice 4b (`1749a65`, #41) relocated the cache to the visible `workspace/tasks/<id>/sources/…` — the call site (`pipelines.py:259`) passes the task **root** from `session_store.task_dir()` as `task_state_dir` — and the wiring shipped (`pipelines.py:1373` pipeline, `:1778` peer). Parameter name `task_state_dir` is itself now misleading. |
| 7 | `README.md` Repository Map (~line 106) | Seven top-level dirs listed | Omits tracked top-level dirs `development-team/`, `gem/`, `runtime/`, `web/` (hcom context folders, not source roots) and `reference/` — minor, but a zero-context reader misses the backlog and ADRs |
| 8 | `TESTING.md:203` | "CI runs the same suite with `pytest-timeout` enabled so hung async or web tests fail within the configured per-test timeout" | No `--timeout` is configured anywhere (`pytest-timeout` is only a dependency in `pyproject.toml`); only smoke tests carry `timeout` marks and they skip in CI. Job-level `timeout-minutes` in `ci.yml` is the only hang protection. |

When you fix one of these, also delete the corresponding row here (or update this table's date) — this inventory is itself volatile.

## 8. When NOT to use this skill

| If you need… | Use sibling |
|---|---|
| Change classification, branch/PR/squash discipline, CI gating, the non-negotiable rules with their incident history | `crisai-change-control` |
| Test commands, markers, coverage, how to add tests, what counts as evidence | `crisai-validation-and-qa` |
| UI architecture, UCL Design System / WCAG obligations as they apply today, the React/Ink workspace | `crisai-ui-surfaces` |
| ADR *content* — the load-bearing design decisions and invariants themselves | `crisai-architecture-contract` |
| Registry/semantic-vocabulary editing (`semantic_catalog.yaml` / `semantic_graph.yaml`) | `crisai-semantic-registry-reference` |
| Incident/investigation history behind the rules | `crisai-failure-archaeology` |
| Operating the hcom development team documented under `reference/development/` | `crisai-devteam-operations` |

This skill owns the *format, ownership, authority, and freshness* of documents; siblings own their subject matter.

## Provenance and maintenance

Re-verify volatile claims with these one-liners (all read-only, from repo root):

- Triplet in sync + still gitignored: `cmp CLAUDE.md AGENTS.md && cmp CLAUDE.md GEMINI.md && git check-ignore CLAUDE.md AGENTS.md GEMINI.md`
- Staleness #1 (pip-audit): `grep -n 'ignore-vuln' TESTING.md .github/workflows/ci.yml` (stale while TESTING.md hits and ci.yml does not)
- Staleness #2 (file inventory): `awk '/^  unit\//,/^\x60\x60\x60/' TESTING.md | grep -c 'test_.*\.py'; ls tests/unit/test_*.py | wc -l`
- Staleness #3 (CLAUDE.md UI section): `ls -d src/crisai/apps/ui 2>&1; ls ui/apps/`
- Staleness #4 (ADR-013 phase text): `grep -n 'Phase 0–1\|Phase-2 migration lands' reference/decisions/CRISAI-ADR-013-source-capability-contract.md`
- Staleness #5 (index vs ADR-012): `grep -n 'ADR-012' reference/decisions/README.md; grep -n 'Status' reference/decisions/CRISAI-ADR-012-gemini-style-cli.md`
- Staleness #6 (source_cache docstring): `grep -n 'crisai/sources\|separate slice' src/crisai/workspace/source_cache.py src/crisai/orchestration/source_materialisation.py`
- Staleness #8 (pytest-timeout): `grep -n 'pytest-timeout' TESTING.md pyproject.toml; grep -rn -- '--timeout' pyproject.toml .github/workflows/ci.yml` (stale while TESTING.md claims it and no `--timeout` is configured)
- TODO vocab/format: `sed -n '12,25p;96,97p;176,182p' reference/TODO.md`
- ADR house format exemplars: `grep -n '^Status:\|^Date:\|^## ' reference/decisions/CRISAI-ADR-01[45]*.md`
- Ledger-line convention: `git log --format=%B -3 | grep -n 'Full suite green\|Full unit suite'`
- Authority worked example: `git log -1 --format='%ci' -- TESTING.md; git show a010c8f --stat | head -20`
