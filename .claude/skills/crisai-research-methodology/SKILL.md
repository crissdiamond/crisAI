---
name: crisai-research-methodology
description: The discipline that turns a hunch into an accepted result in crisAI. Load this when starting or reviewing an investigation, proposing a fix for a live failure, deciding whether a hypothesis is proven, designing an experiment or feature flag, judging when a root cause is "found", planning a multi-slice delivery, retiring or promoting an experimental flag, or wondering what TODO/ADR bookkeeping an investigation owes. Keywords - root cause, hypothesis, evidence bar, TestNNN, live eval session, experiment flag, CRISAI_MATERIALISE_SOURCES, ADR, slice PR, default flip, retirement, falsify.
---

# crisAI research methodology: hunch → accepted result

This skill encodes how ideas actually became accepted results in this repo — the
evidence bar, the prediction discipline, the idea lifecycle, and the bookkeeping
each investigation owes. It is a method skill: it tells you *how to know you are
right* and *what path a validated idea travels*, using this repo's own history as
worked precedent. All commit hashes and file:line references below were verified
against `main @ c39273b` on 2026-07-02.

Jargon used throughout, defined once:

- **TestNNN** — a numbered live evaluation session (`Test001`…`Test007`, plus
  lowercase `test003` and `NewTest-*`) run against real OneDrive/SharePoint
  content. Each leaves a task directory under `workspace/tasks/<name>/` with run
  snapshots in `.crisai/runs/*.json`. As of 2026-07-02 all of Test001–Test007
  exist on disk.
- **ADR** — an architecture decision record under `reference/decisions/`
  (`CRISAI-ADR-001`…`015`).
- **Materialisation** — fetching a confirmed source once into the per-task cache
  `workspace/tasks/<id>/sources/<source-id>/<revision>/` so later turns read a
  stable copy instead of live OneDrive (ADR-015).

---

## 1. The evidence bar

A root-cause claim is accepted here only when it clears both tests:

**Test 1 — one mechanism explains ALL observations, including the negatives.**
Not "explains the failure" — explains why the failure happened *and* why the
adjacent case succeeded. The exemplar is ADR-015's context section
(`reference/decisions/CRISAI-ADR-015-source-grounding-backbone.md`): two Test001
runs five minutes apart, turn 1 succeeded, turn 2 died at the policy gate. The
superficial culprit was an Office `~$` lock stub. The ADR explicitly rules it
out: *"The root cause is **not** the lock file"* — the authoritative v2 source
with a working handle was still in session memory. Only "resolved sources are
persisted but not durably bound on reference, so a follow-up re-resolves against
live mutable OneDrive state" explains both the turn-1 success (full title
restated → anchor bound) and the turn-2 failure ("v2" scored below threshold →
anchor dropped → live re-search → lock stub). A lock-file filter alone would
have left the mechanism intact; the ADR records that the user *"explicitly
rejected workarounds for this critical backbone"*.

The same discipline shows in commit 0cdd086 (#26): the *deeper* cause behind the
dropped anchor was GUID-duplicate candidates of the same deck starving the
resolution slots — a second layer of "why", found because the first explanation
did not cover every observation.

**Test 2 — the claim survives adversarial refutation.** Someone (or something)
whose job is to break the claim gets a real shot at it before acceptance. This
is not an imported ideal: it is the product's own architecture. Peer mode runs
author → challenger → refiner → judge; the challenger's standing mission is
*"Critique the author's draft rigorously … without rewriting"*
(`prompts/design_challenger.md`), a judge non-accept raises
`WorkflowValidationError` and kills the run before finalisation
(`src/crisai/cli/pipelines.py:2126-2129`), and the final deliverable is checked
against registry regexes by `enforce_peer_final_deliverable_verification`
(`src/crisai/orchestration/peer_verifier.py:388`, patterns in
`registry/semantic_catalog.yaml` under `peer_verifier:`). Apply the same
structure to your own hypotheses: before declaring a root cause, write down the
strongest alternative explanation and the observation that kills it.

**The cost of skipping the bar — the auth saga (2026-05-03).** When Azure
rejected auth with AADSTS7000218, three escalating, increasingly RFC-literate
code fixes shipped in one day without a mechanism that explained all
observations: 2fbd2e8 (switch to ConfidentialClientApplication), 5c5ec96
(hand-rolled device flow because MSAL 1.36.0's confidential client lacks
`initiate_device_flow`), c11eb8f (client_secret in both `/devicecode` and
`/token` per RFC 8628 §3.1). All three were dead ends. The revert da4f4bd
records the real mechanism: *"Device code flow for confidential clients … is
not supported by Azure AD in this tenant configuration regardless of whether
client_secret is included"* — the correct fix was a portal checkbox ("Allow
public client flows" on the app registration), zero lines of code. Each patch
had been consistent with the last error message but not with the whole
observation set. Fix-shaped guesses that survive one error message and die on
the next are the signature of a skipped evidence bar. (Full worked proof recipe:
see `crisai-proof-and-analysis-toolkit`.)

Checklist before you claim a root cause:

- [ ] Mechanism stated in one sentence, no "and also".
- [ ] Explains every failing observation AND every adjacent success/negative.
- [ ] Strongest rival explanation written down, plus the observation that falsifies it.
- [ ] Survives a challenger pass (peer run, reviewer, or your own written refutation attempt).
- [ ] Distinguishes symptom-bearer from cause (lock stub vs dropped anchor).

---

## 2. Hypothesis predicts numbers before running

Before any confirming run, write down the numbers the hypothesis predicts:
which trace events fire, how many, which gate outcome, which route. Then run
and count. A hypothesis that only predicts "it works better" is not testable
here; the trace layer exists precisely so hypotheses can predict integers.

The canonical example is Test007 (commit 841769e, #44). Hypothesis under test:
checkpoint-time materialisation (wired in slice 3b) covers the knowledge-
authoring workflow. Predicted number: ≥1 `SOURCE_MATERIALISED` trace event when
a peer run reads a source. Observed: *"Test007 read its source live and
authored a strong artefact, yet zero SOURCE_MATERIALISED events fired and no
cache was written"* (commit body, verbatim). The artefact quality was fine —
prose inspection would have passed it. The **zero** falsified the assumption:
slice 3b had wired `run_pipeline` only, and peer mode — the main authoring path
— was uncovered. One integer found a mode-parity gap that a qualitative read
missed.

Other verified instances of the same discipline:

| Session / commit | Predicted vs observed number | What it falsified |
|---|---|---|
| Test007 → 841769e (#44) | ≥1 vs **0** `SOURCE_MATERIALISED` events | "Materialisation covers authoring" — peer path unwired |
| Test004 → 0b63dbf (#39) | Planner output present vs **449 output tokens, output_length 0** | "Empty planner output means model failure" — it was a valid reasoning-model behaviour peer mode failed to tolerate |
| Test005 → b386a17 (#42) | Same result set for either query order vs disjoint sets — *"A live check confirmed the cause"* by running both queries | "Query wording is equivalent" — Graph search is word-order sensitive |

Where the numbers live (measurement mechanics are owned by
`crisai-diagnostics-and-tooling`; this section only defines the obligation):

- `logs/agent_trace.jsonl` — stage/policy/source events (`TRACE_FILE_NAME`,
  `src/crisai/tracing.py:9`). Grep and count, e.g.
  `grep -c '"SOURCE_MATERIALISED"' logs/agent_trace.jsonl`.
- `workspace/tasks/<session>/.crisai/runs/*.json` — per-run snapshots
  (decision, expected stages, events, error).
- Materialisation emits exactly three event names, from
  `src/crisai/cli/pipelines.py:284,299`: `SOURCE_MATERIALISED`,
  `SOURCE_CACHE_HIT`, `SOURCE_MATERIALISE_ERROR` — so cache reuse vs first
  fetch vs failure are each separately countable.

Prediction template (write it in the task notes or the eventual commit body):

```
Hypothesis: <one-sentence mechanism>
Run: <TestNNN or command>
Predicts: <event name> count = N; gate outcome = <pass|POLICY_VIOLATION|...>;
          route = <mode/agent>; negative control: <adjacent case> unchanged.
Falsified if: <specific number that must NOT appear>
```

---

## 3. The idea lifecycle as practised

Every accepted result in the June arc travelled the same seven stations. Use
them in order; skipping a station is how workarounds ship.

### 3.1 Live failure session (TestNNN)

Ideas start as a numbered live session against real sources, not as
speculation. Reproduce the failure in a fresh task session, give it the next
TestNNN name, and let the run snapshots under
`workspace/tasks/<name>/.crisai/runs/` become the diagnostic corpus.

### 3.2 Named defect

Decompose the session into separately named defects so each gets its own
mechanism, fix, and PR. The test003 assessment named **Defect A** (source-fit
gate lived only in `run_single`, bypassed by pipeline over-routing → a49593c
#29), **Defect B** (framing-only planner still had source-search servers and
the model ignored the prompt-level "do not retrieve" → structural tool
stripping, 9c9ee2e #30), **Defect C** (Office lock stubs impersonating real
documents → connector filter, 2455c1c #28). The Test006 audit graded findings
**Tier-1** (fails runs — fixed in 2f41bec #43) vs **Tier-2** (mis-classifies
but does not fail runs — deferred as a named follow-up in the same commit
body). Note: the assessment documents themselves are chat-era artefacts, not
repo files. Defects A and B are named in the commit bodies (a49593c, 9c9ee2e)
and durable there; the "Defect C" label for the lock-stub filter (2455c1c #28)
survives only in chat-era assessment notes — that commit body describes the
defect but never carries the name.

### 3.3 ADR if architecture-shaping

If the fix changes a load-bearing design (not just a bug), write the ADR
*first*, as its own docs PR (f4c873b #25 landed ADR-015 before any
implementation slice). `reference/TODO.md` codifies the trigger: *"When an item
becomes architecture-shaping, add or update an ADR in `reference/decisions/`
and link it from the item."* A defect that can be fixed inside existing
contracts needs no ADR — Defects A/B/C got none.

### 3.4 Slice-based delivery

Break implementation into phase/slice PRs, one reviewable change each, each
commit body ending with what the next slice is. The ADR-015 arc as shipped
(all 2026-06-14, each a squash-merged PR):

| Slice | Commit (PR) | Content |
|---|---|---|
| Phase 1 | 0cdd086 (#26) | One logical document = one anchor (GUID-dedup) |
| Phase 2 | 6443122 (#27) | Workspace evidence materialisation store |
| 2b slice 1 | add236f (#33) | `download_source_bytes_by_handle` + agent-excluded `tools.internal` class |
| 2b slice 2 | 35f6604 (#35) | Deterministic non-agent fetch path |
| 2b slice 3a | 14a90f5 (#37) | Materialisation orchestrator |
| 2b slice 3b | 2ed10bd (#38) | Wire into pipeline retrieval checkpoint |
| 2b slice 4a | 4f7b65c (#40) | Cache pointer on session candidate |
| 2b slice 4b | 1749a65 (#41) | Readable cache + anchor-first read-through |
| 2b peer parity | 841769e (#44) | Same wiring in `run_peer_pipeline` (Test007) |

Branch/PR/commit-body mechanics (post-mortem format, test-count ledger — suite
counts grew 821→828→837→842→851→853→856→857→863 across this arc — squash rules) are
owned by `crisai-change-control`; the method obligation here is only: **one
falsifiable change per slice, validated before the next starts.**

### 3.5 Experiment flag: default-off, best-effort, never aborts

New behaviour that touches live runs lands behind an opt-in switch. The live
worked example is `CRISAI_MATERIALISE_SOURCES`
(`_source_materialisation_enabled`, `src/crisai/cli/pipelines.py:212-221`):

- **Default off.** Unset/empty → disabled; enabled only by
  `{"1","true","yes","on"}` (or a `materialise_sources_enabled` settings
  override). `.env.example:84` ships `false`.
- **Best-effort.** `_materialise_confirmed_sources` (pipelines.py:235) skips
  workspace-local and handle-less sources instead of erroring.
- **Never aborts.** Per-source failures are caught, traced as
  `SOURCE_MATERIALISE_ERROR`, and the run continues
  (pipelines.py:282-286, comment: *"never break the run on materialisation"*).
- **Observable.** Every activation leaves countable trace events (§2), so the
  validation phase has numbers to check.

Follow this shape for any new experimental behaviour: an unset environment must
be behaviourally identical to the pre-change codebase, and the experiment must
be measurable from traces. (The full flag catalogue and add-a-flag checklist
belong to `crisai-config-and-flags`.)

### 3.6 Validation

Run the flag against live TestNNN sessions with §2 predictions written first.
Validate in **every execution mode** — mode parity is this repo's dominant
regression pattern (gate parity a49593c #29, fallback parity 0b63dbf #39,
materialisation parity 841769e #44 — three separate fixes for
pipeline-but-not-peer gaps). A result validated in one mode is one third of a
result.

### 3.7 Default flip OR documented retirement

An experiment ends in exactly one of two ways; both are healthy.

- **Default flip.** As of 2026-07-02 `CRISAI_MATERIALISE_SOURCES` has *not*
  flipped: `.env.example` says `false`, the local developer `.env:82` runs
  `true` (so local behaviour ≠ shipped behaviour — always state which you
  observed). The flip is gated on TODO-048/TODO-003 completing end-to-end
  ("neither item is complete while a confirmed follow-up can regress to mutable
  live retrieval", TODO.md Recommended Sequencing step 2). No dated flip
  decision exists in the repo — treat flip timing as an open owner decision.
- **Documented retirement.** Two precedents, both faster and cleaner than
  defending a wrong approach:
  - *The 7-minute revert* (2026-05-22): ceb38c9 (12:01) hacked a Gemini/
    Antigravity reviewer swap directly into the hcom start scripts; 01d3654
    reverted it at 12:08; 1fe2388 (12:09) immediately wrote a review-provider
    abstraction design doc, and a properly abstracted implementation followed
    the same day — kept explicitly experimental (2f538cd, 14:07). The revert
    signalled "wrong approach", not "broken build", and the redesign started
    within one minute of it.
  - *ADR-012* (Gemini-style prompt-toolkit CLI): whole subsystem retired with
    `Status: superseded` recorded in the ADR file itself, naming what replaced
    it (Ink Gem + React web over the shared runtime contract). Retirement is a
    status change plus a pointer, never a silent deletion.

---

## 4. Where good ideas historically come from

Not speculation — live sessions. Every June behaviour fix names the TestNNN
session that motivated it in its commit subject or body (all verified in
`git log`):

| Session | Commit (PR) | Result it produced |
|---|---|---|
| Test001 | f4c873b (#25) + 0cdd086 (#26) | ADR-015 itself + anchor dedup |
| Test001/test003 | 2455c1c (#28) | Lock-stub connector filter (Defect C) |
| test003 | a49593c (#29) | Mode-independent source-inventory gate (Defect A) |
| test003 | 9c9ee2e (#30) | Tool-less framing planner — structural, not prompt, enforcement (Defect B) |
| Test004 | 0b63dbf (#39) | Empty planner output non-fatal in peer mode |
| Test005 | b386a17 (#42) | Verbatim title-phrase search; word-order trap |
| Test006 | 2f41bec (#43) | Output destination excluded from input source scope |
| Test007 | 841769e (#44) | Peer-mode materialisation parity |

Corollaries:

- When you need a next improvement, **run a live session and read its trace**
  before browsing the backlog for something to build. The TestNNN corpus under
  `workspace/tasks/` is a de facto regression suite; extend it rather than
  inventing synthetic cases.
- Fixes derived from live defects also generated the follow-on backlog:
  TODO-055 (title-phrase extraction precision) and TODO-057 (peer planner tool
  scoping) are both residue of Test003–Test006 analysis, filed instead of being
  bundled into the fix PRs.
- Systematic eval (routing/groundedness/cost thresholds) is TODO-051 and has
  its own campaign skill — this section is about where *hypotheses* come from,
  not how the baseline campaign runs.

---

## 5. TODO/ADR bookkeeping obligations

The repo's own rules, from `reference/TODO.md` ("How To Maintain") and
`reference/decisions/README.md` ("Decision Format").

**When starting an investigation:**

- [ ] Ensure a TODO-NNN row exists in `reference/TODO.md` (Status one of:
  todo, planned, in-progress, blocked, done, dropped; Priority P0–P3 per the
  file's definitions). Set it `in-progress` when work starts.
- [ ] Split anything that cannot be *"completed and verified in one focused
  change"* (TODO.md rule) — this is what produced the slice arc in §3.4.
- [ ] If architecture-shaping, add/update an ADR (sections: Status / Date /
  Context / Decision / Consequences / Related; Status one of proposed,
  accepted, superseded, retired) and link it from the TODO row. ADR-015 ↔
  TODO-048 is the reference pairing.
- [ ] Treat TODO IDs as stable references, not priority order; execution order
  comes from the Priority column and the Recommended Sequencing section.

**When finishing (or retiring):**

- [ ] Move the TODO row to the Done table *with the merge commit or PR
  reference* (TODO.md rule; see the Done table's format).
- [ ] Spin residual findings into new TODO rows instead of leaving them in
  prose (precedent: 2f41bec's body defers Tier-2 registry tightening; TODO-055/
  057 filed from test-session analysis).
- [ ] On retirement, set the ADR file's `Status:` line to superseded/retired
  and name the replacement in the Decision section (ADR-012 pattern).
- [ ] Update the index table in `reference/decisions/README.md`. Known trap,
  verified 2026-07-02: that index still lists ADR-012 as `accepted` while the
  ADR file itself says `superseded` — the file's own Status line is
  authoritative; do not add to the index drift.
- [ ] The squash-merge commit body carries the post-mortem (symptom → TestNNN
  → mechanism → fix → alternatives rejected → suite count); format details in
  `crisai-change-control`.

---

## When NOT to use this skill

| If you need… | Use instead |
|---|---|
| To execute the TODO-051 eval-baseline campaign (phases, commands, gates) | `crisai-eval-baseline-campaign` |
| Concrete proof recipes (router golden set, TestNNN reproduction, trace-based proof, the auth saga as a worked example) | `crisai-proof-and-analysis-toolkit` |
| Branch/PR/squash mechanics, commit-body format, CI gating | `crisai-change-control` |
| Trace/log anatomy, `crisai spend`, measurement tooling | `crisai-diagnostics-and-tooling` |
| Test commands, markers, coverage mechanics | `crisai-validation-and-qa` |
| The full incident chronicle | `crisai-failure-archaeology` |
| External novelty positioning and open research problems | `crisai-research-frontier` |
| Symptom→triage for a failure happening right now | `crisai-debugging-playbook` |

## Provenance and maintenance

Verified 2026-07-02 against `main @ c39273b`. Re-verify with:

- Flag gate + event names: `grep -n 'CRISAI_MATERIALISE_SOURCES\|SOURCE_MATERIALISED\|SOURCE_MATERIALISE_ERROR' src/crisai/cli/pipelines.py`
- Shipped vs local flag default: `grep -n 'CRISAI_MATERIALISE_SOURCES' .env.example .env`
- ADR-015 root-cause text: `grep -n 'root cause is' reference/decisions/CRISAI-ADR-015-source-grounding-backbone.md`
- Test007 zero-events claim: `git show -s --format='%b' 841769e | head -5`
- Auth-saga mechanism: `git show -s --format='%b' da4f4bd | head -6`
- 7-minute revert timestamps: `git show -s --format='%h %ad %s' --date=format:'%H:%M' ceb38c9 01d3654 1fe2388`
- Slice arc + TestNNN fix commits: `git log --oneline --grep='ADR-015' main; git log --oneline --grep='Test00' main`
- Judge hard gate: `grep -n 'judge did not accept' src/crisai/cli/pipelines.py`
- Peer verifier: `grep -n 'def enforce_peer_final_deliverable_verification' src/crisai/orchestration/peer_verifier.py; grep -n '^peer_verifier:' registry/semantic_catalog.yaml`
- TODO lifecycle rules: `sed -n '12,25p' reference/TODO.md`
- ADR format + (stale) index: `sed -n '14,45p' reference/decisions/README.md; head -4 reference/decisions/CRISAI-ADR-012-gemini-style-cli.md`
- TestNNN corpus on disk: `ls workspace/tasks/ | grep -i test`
- Trace file name: `grep -n 'TRACE_FILE_NAME' src/crisai/tracing.py`
