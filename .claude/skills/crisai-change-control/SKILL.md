---
name: crisai-change-control
description: Load before making ANY change to the crisAI repo — code, registry YAML, prompts, docs, or ADRs — and before committing, opening a PR, squash-merging, or reacting to a red CI run. Answers: is this a registry edit or a code change, does it need an ADR, what goes in the commit body, what trailer conventions apply, what must be checked before squashing a PR, and why the CI security gate can never be suppressed. Also covers the no-push rule and hcom-era git authority.
---

# crisAI change control

How changes are classified, gated, committed, and merged in this repository —
and the historical incidents (with commit hashes) that made each rule
non-negotiable. Every rule below was paid for at least once.

The current flow as of 2026-07-02 (practised since ~2026-06-13, PRs #21–#46):

> feature branch → Conventional Commit(s) whose body doubles as a post-mortem
> and test-count ledger → PR → CI fully green (security job is a hard merge
> blocker) → **pre-squash tip check** → squash merge onto `main` as a single
> commit titled `type(scope): subject (#N)` → `gh run list --branch main --limit 3`.

The hcom multi-agent dev-team apparatus is dormant but live (owner intends to
revive it); its git-authority rules are recorded near the end of this file.

## When NOT to use this skill

| You need | Use instead |
|---|---|
| Starting/stopping/resuming the hcom dev team, roster, tmux, review providers | `crisai-devteam-operations` |
| Exact test commands, markers, coverage mechanics, the pytest argv trap | `crisai-validation-and-qa` |
| Doc house style, ADR/TODO templates in depth, staleness inventory, CLAUDE/AGENTS/GEMINI sync mechanics | `crisai-docs-and-writing` |
| What the architecture decisions actually say (ADR content) | `crisai-architecture-contract` |
| Catalog vs graph schema detail, matching semantics, how to add an intent | `crisai-semantic-registry-reference` |

## Step 1 — classify the change

Before touching anything, read `reference/VISION.md` (CLAUDE.md makes this a
precondition for planning) and decide which class the change is. Work on **one
improvement at a time** — one class, one branch, one PR.

| Class | Definition | Where it lands | Gate |
|---|---|---|---|
| **Registry edit** | Any change to routing behaviour, intent vocabulary, verifier regexes, contract markers, lexicon terms, retrieval constraints/expansion, agent↔model assignment, server/tool exposure | `registry/*.yaml` only — no Python | Tests still green; `crisai doctor` validates registries in CI |
| **Code change** | Mechanics only: loading, enforcement, orchestration, adapters | `src/crisai/` + `tests/` | Full CI; docs update if behaviour changes |
| **Prompt edit** | Standing instructions of a runtime agent | `prompts/*.md` | Only if generally applicable to ALL future uses of that agent (see rule 3) |
| **Docs change** | README, DOCUMENTATION*, TESTING, runbooks, reference/ | The affected doc + TODO.md status | Accuracy against code, not against memory |
| **ADR-worthy** | Architecture-shaping: agent boundaries, runtime behaviour model, workspace structure, retrieval contracts, configuration policy, UX conventions (`reference/decisions/README.md`) | New/updated `reference/decisions/CRISAI-ADR-NNN-*.md`, landed FIRST as its own `docs(adr)` PR | Then implementation follows in slice PRs referencing the ADR |

**Registry edit vs code change — the litmus test.** If the change adjusts
*what the system means* (a term, a pattern, a threshold of vocabulary), it is a
registry edit. If it adjusts *how the system executes*, it is a code change.
VISION.md ("Technology decisions"): "Behaviour changes are registry edits, not
code changes." CLAUDE.md hardens this: ALL semantic vocabulary lives in
`registry/semantic_catalog.yaml` or `registry/semantic_graph.yaml`, never in
Python. Ownership split between the two files → `crisai-semantic-registry-reference`.

**Incident behind the registry rule.** Hardcoded vocabulary repeatedly leaked
into Python and had to be evicted in a whole enforcement wave: `ef7ff0c`
(2026-05-11, removed a `_DEFAULT_CONFIG` that duplicated workflow-policy marker
vocabulary and silently supplied hardcoded markers when `registry_dir` was
None), plus `04adbfb`, `10b360e`, `96c5b56`, `60f34ac` (same day, four more
modules), and `da29d33` (2026-05-17, session memory markers). The CLAUDE.md
rule exists so this class of leak is rejected at review, not re-fixed monthly.

**What needs an ADR.** `reference/TODO.md` ("How To Maintain" preamble): when a
backlog item becomes architecture-shaping, add or update an ADR in
`reference/decisions/` and link it from the item. ADR format (Status / Date /
Context / Decision / Consequences / Related) and the index table live in
`reference/decisions/README.md`; add a row there for every new ADR. The
practised delivery pattern is **ADR-first**: ADR-015 landed as its own PR
(`f4c873b`, #25, 2026-06-14) before any of the ~19 implementation slice PRs
(#26–#44) that reference it. Do not bundle an ADR with its implementation.

## Step 2 — the non-negotiables (rule → rationale → incident)

1. **Semantics in registry, never hardcoded.** Rationale: routing must be
   auditable, tunable configuration. Incidents: `ef7ff0c`, `da29d33`,
   `04adbfb`/`10b360e`/`96c5b56`/`60f34ac` (see above).

2. **Machine-critical handoffs are schema-backed JSON contracts, never prose.**
   Reviewers must reject prose-only handoffs for routing decisions, source
   identities, evidence, gates, retries, inter-stage state. Rationale:
   downstream behaviour must not depend on parsing prose. Incidents: the
   2026-05-10 evidence-transport bug tail — `0a6c0fe` (validated evidence
   handoffs), `574eeba` (evidence JSON leaking into rendered output),
   `17ac929` (suppress machine JSON, tolerate evidence fences) — evidence
   travelling inside prose broke both machines and humans; ADR-003 codified
   the separation.

3. **`prompts/` files change only for generally applicable improvements** —
   never to satisfy one user request or the current conversation (those belong
   in the user's message). Rationale: prompt text is not trusted as a contract
   here anyway. Incident: `9c9ee2e` (#30, 2026-06-14, test003 defect B) — the
   retrieval planner's prompt said "Do not retrieve or read source documents in
   this stage" and the model **ignored it**, running a competing wrong OneDrive
   search. The fix was structural (strip source-search MCP servers from the
   planner spec), not more prompt text. Doctrine: enforce behaviour via tool
   stripping, gates, and registry; prompts set tone and shape, not guarantees.

4. **Update README.md and DOCUMENTATION.md** whenever a change affects usage,
   architecture, setup, or behaviour (CLAUDE.md). Move completed TODO items to
   the Done table **with the merge commit or PR reference** (TODO.md rule; see
   the existing Done rows for the format). Warning: doc updates that are
   skipped rot fast — TESTING.md still documented four pip-audit suppressions
   after `a010c8f` removed them from CI (staleness inventory →
   `crisai-docs-and-writing`).

5. **Add/update tests under `tests/` for changed behaviour and run the
   relevant tests** (CLAUDE.md). Exact commands and the known pytest argv trap
   → `crisai-validation-and-qa`.

6. **Do not push unless specifically asked** (CLAUDE.md). Commits are local
   until the user says otherwise. Rationale: single-owner repo where the human
   controls what reaches origin; the hcom era formalised the same principle as
   a single-git-writer model (below).

7. **CI security gate is never suppressed** — see Step 5. The gate comment in
   `.github/workflows/ci.yml` is the policy: "Any new vulnerability must fail
   the gate, not be added to an ignore list."

8. **Commit trailer conventions.** Conventional Commits throughout (observed
   scopes include gate, retrieval, peer, pipeline, routing, sources,
   sharepoint, intranet, auth, models, web, gem, cli, dev, registry, session,
   docs, ci). End AI-assisted commits with a `Co-authored-by:` trailer naming
   the actual AI tool/model that did the work — observed values in history:
   `Cursor <cursoragent@cursor.com>`, `Claude Sonnet 4.6 <noreply@anthropic.com>`,
   `Claude Opus 4.8 (1M context) <noreply@anthropic.com>`; both
   `Co-authored-by` and `Co-Authored-By` capitalisations occur. **Never add a
   `Made-with: Cursor` trailer** (explicit CLAUDE.md rule; 40 such trailers
   from the 2026-05-01 Cursor era remain in history — the rule stops the
   pattern going forward).

9. **After each commit on main, check CI**: `gh run list --branch main --limit 3`
   and report failures before continuing (CLAUDE.md).

## Step 3 — write the commit body as a post-mortem

The PR-era convention (observed in every fix PR #26–#44): the squash commit
body is the primary record of the change and doubles as documentation. Include:

- **Symptom**, naming the live test session that exposed it when there is one
  (Test001…Test007 appear in `2455c1c`, `a49593c`, `9c9ee2e`, `0b63dbf`,
  `b386a17`, `2f41bec`, `841769e`);
- **Root cause**, stated mechanically, not vaguely;
- **Fix rationale** and **alternatives rejected** (e.g. `b386a17`: "Per the
  user's call, the inventory gate keeps its hard failure…");
- **Scope honesty** — say which modes/paths the fix covers and which it does
  not (`9c9ee2e` explicitly scoped itself to `run_pipeline` and flagged peer
  mode as follow-up, which became TODO-057);
- **Test-count ledger closing line**: `Full suite green (N passed; ruff + mypy
  clean)` — N is the full suite size and grows monotonically (821→…→863 across
  the June PRs; `a010c8f` reports 885). This line is how suite growth is
  audited without an external tracker;
- The `Co-authored-by:` trailer (rule 8).

Slice-based delivery: for multi-PR arcs, title commits `phase N` / `slice Na`
against the ADR (e.g. "ADR-015 2b slice 4a") and end the body with
"Next: slice …" so the arc is reconstructable from `git log` alone.

## Step 4 — pre-squash check (mandatory; the 955dcda trap)

**Incident.** On 2026-06-14, commit `955dcda` ("docs(todo): prioritize source
trust follow-ups") was pushed to the PR #31 branch **after** the working
agent's last push. The squash merge of #31 (`bbd3c00`) silently did not include
it; the commit was left dangling and its content had to be excavated from
unreachable objects and restored byte-for-byte by `7abad51` (#32). A squash
merge takes whatever the merge UI saw — anything pushed to the branch after
your last review is dropped without any error.

**Mandatory checklist before every squash merge:**

```bash
# 1. Refresh remote state — never squash from a stale view.
git fetch origin

# 2. List exactly what the squash will contain; confirm the newest commit
#    matches the last change you actually reviewed (subject AND hash).
git log --oneline origin/<branch> --not origin/main

# 3. If anyone (human or agent) may have pushed since you last looked,
#    re-review the tip before merging.
```

**And after the squash lands:**

```bash
# Confirm the squash carried the FULL branch content. Do NOT use
# `git cherry` here: it compares per-commit patch-ids, so after a squash
# merge of a multi-commit branch EVERY branch commit shows '+' whether or
# not its content merged (verified 2026-07-02 on the fully merged
# feat/local-openai-compatible-provider — all three commits show '+').
# It only gives a meaningful '-' for single-commit branches.
# Instead, diff the squash commit's patch against the whole-branch diff;
# any non-empty output means content was dropped — recover it immediately
# (see 7abad51 for the pattern).
diff <(git show <squash-sha> --format= --patch) \
     <(git diff $(git merge-base main~1 origin/<branch>) origin/<branch>)
```

Related history notes (observed, not policy): origin keeps stale post-squash
branches — 8 as of 2026-07-02 — so an existing remote branch does NOT mean live
work; and one superseded local-main commit was preserved as an annotated tag
`archive/a3ddee0-gemini-reviewers` (single occurrence — treat
`archive/<sha>-<topic>` as a candidate convention, not an established one).

## Step 5 — CI is the merge gate; the security job is a hard blocker

`.github/workflows/ci.yml` (as of 2026-07-02) runs three jobs on every PR and
push to main:

| Job | Steps | Notes |
|---|---|---|
| `security` | Bandit (medium severity) → `uv export --locked` → **pip-audit with NO suppressions** → gitleaks (action pinned by SHA, version 8.30.1) | Hard blocker |
| `test` | matrix Python 3.10–3.14: ruff → mypy → `crisai doctor` (registry validation) → `uv run pytest -q` | Suite is network-free |
| `ui` | `npm --prefix ui ci` → typecheck → `build:web` → `build:gem` | UI **unit tests are NOT run in CI** (TODO-027) — a green UI job proves builds only |

**The PR #45 story — why the security gate is never suppressed.** The
local-OpenAI-provider work was authored 2026-06-19 (branch commits `4d62977`,
`b7b6c22`, `294d0e9`, author dates Jun 19) but did not merge until 2026-07-01
(`c39273b`) — blocked ~12 days. The unblocking commit `a010c8f` (#46) states
the cause: "Resolve all 18 pip-audit findings that were blocking the security
gate." The response was NOT to widen the ignore list. It was a dependency and
SDK migration — openai-agents 0.2.11→0.4.2, openai 1.109→2.44, litellm→1.90.2,
plus six in-place bumps — after which the four pre-existing narrow
`--ignore-vuln` entries (which the pre-#46 ci.yml did carry) were **removed**,
making the gate fully strict. #45 was then rebased and merged five minutes
after #46 landed (07:39 → 07:44 on 2026-07-01).

Rules this story encodes:

- A red security gate blocks EVERY open PR, including unrelated feature work.
  Budget for it; do not try to route around it.
- Fix the dependency set (bump, migrate, replace); never add an
  `--ignore-vuln`. The in-file comment makes this policy explicit.
- If a feature branch sat blocked, **rebase onto main before merging** so the
  squash is evaluated against the gate-fixing state.
- Never weaken existing auth, path-safety, approval, or rate-limiting controls,
  and never add unauthenticated paths to LLM-spend or workspace-write endpoints
  (CLAUDE.md secure-by-design rule) — the gate is the automated backstop for
  the same principle.

## hcom-era git authority (dormant apparatus, may be revived)

When the hcom multi-agent dev team is running (operation →
`crisai-devteam-operations`), git authority follows the single-writer model in
`reference/development/operating_model.md` ("Git Authority" section):

- The **orchestrator is the only role** allowed to run git commands that write
  repository metadata: `add`, `commit`, `fetch`, `pull`, `push`, branch
  switching, merge, rebase, tag.
- Area agents get read-only git (`status`, `diff`, `log`, `show`) and hand off
  a suggested Conventional Commit message instead of committing.
- Review-required work (runtime behaviour, security/auth, routing/retrieval,
  shared UI contracts) must pass a reviewer agent **before commit**; if the
  reviewer cannot launch, the task pauses before commit.
- One recorded breach exists (an area agent committed directly; tolerated
  because CI was green, per `reference/development/newtest-04-restart-handoff.md`)
  — treat it as a warning, not a precedent.

These rules coexist with, and are stricter than, the solo-flow rules above;
nothing in hcom mode relaxes any rule in this file.

## Quick pre-merge checklist

- [ ] One improvement only; VISION.md checked for conflicts before planning
- [ ] Change classified (registry / code / prompt / docs / ADR) and landed in the right place
- [ ] No semantic vocabulary in Python; no prose carrying machine-critical state
- [ ] `prompts/` untouched unless the improvement is generally applicable
- [ ] Tests added/updated and run (→ `crisai-validation-and-qa` for commands)
- [ ] README/DOCUMENTATION updated if usage/architecture/setup/behaviour changed; TODO.md row moved to Done with commit/PR ref
- [ ] Commit body = post-mortem + `Full suite green (N passed; ruff + mypy clean)` + correct `Co-authored-by:` trailer; no `Made-with: Cursor`
- [ ] CI fully green including the security job — no new ignore entries anywhere
- [ ] Pre-squash tip check done (`git fetch` + `git log origin/<branch> --not origin/main`); post-squash the squash-vs-branch diff is empty (not `git cherry` — see Step 4)
- [ ] Not pushed unless the user asked
- [ ] `gh run list --branch main --limit 3` checked after the merge commit

## Provenance and maintenance

Verified against the repo on 2026-07-02. Re-verify with:

- CI jobs and the no-suppressions audit policy: `grep -n "ignore-vuln\|No suppressions\|gitleaks\|bandit" .github/workflows/ci.yml`
- Squash-trap incident: `git show --no-patch --format='%s%n%b' 7abad51 | head -8` and `git cat-file -t 955dcda`
- PR #45 blocked-12-days story: `git log --format='%h %ad %s' --date=iso origin/feat/local-openai-compatible-provider -3` (author dates Jun 19) and `git show --no-patch --format='%b' a010c8f | head -3`
- Registry-vocab incidents: `git show --no-patch --format='%ad %s' --date=short ef7ff0c da29d33 04adbfb 10b360e 96c5b56 60f34ac`
- Prompt-ignored-by-model incident: `git show --no-patch --format='%b' 9c9ee2e | head -12`
- Evidence-in-prose incidents: `git show --no-patch --format='%h %ad %s' --date=short 0a6c0fe 574eeba 17ac929`
- Trailer conventions: `git log --format='%(trailers:key=Co-authored-by,valueonly)' | sort | uniq -c | sort -rn | head`
- `Made-with: Cursor` count (should stay at 40, all historical): `git log --format='%b' | grep -c 'Made-with: Cursor'`
- Test-count ledger convention: `git log --grep='Full suite green' --format='%h %s' | head`
- ADR scope and format: `sed -n '1,25p' reference/decisions/README.md`
- TODO maintenance rules: `sed -n '12,25p' reference/TODO.md`
- hcom git authority: `sed -n '202,216p' reference/development/operating_model.md`
- Squash-era subject style and merge-commit era boundary: `git log --oneline main | head -25` and `git log --merges --format='%h %ad %s' --date=short main | head -5`
- Standing rules themselves: `CLAUDE.md` (gitignored, byte-identical to AGENTS.md/GEMINI.md; sync obligation → `crisai-docs-and-writing`)
