---
name: crisai-research-frontier
description: Use when positioning crisAI externally or assessing what is genuinely novel — writing a paper, talk, blog post, README pitch, grant/funding text, demo script, or comparison against state of the art; when someone asks "what is new here?", "is this just RAG?", "can we claim X?", or "what would we have to prove?"; and when planning research work on any of the four pillars (grounding discipline, registry-owned semantics, governed agent workflows, measured LLM quality). Defines the claim discipline, the honest known-art boundaries, per-pillar proof obligations routed through the TODO-051 evaluation baseline, and falsifiable milestones.
---

# crisAI research frontier — what is novel, what is known art, what must be proven

This skill is the honest external-positioning map for crisAI (a local, registry-driven
AI workstation for enterprise/solution/data architects). It exists so that nobody —
human or model — makes an external claim this repo cannot back, and so that research
effort lands on the four pillars the owner has designated as the frontier
(decision recorded 2026-07-02): all four together, not any one alone.

**The single hard rule: no external claim without measured evidence.** As of
2026-07-02 the product-quality evaluation baseline (TODO-051, `reference/TODO.md`
line 99) has status `todo` — no eval harness, no thresholds, no baseline numbers
exist anywhere in the repo. Therefore **today there is no externally publishable
quantitative claim**. Everything below distinguishes *shipped mechanism* (verifiable
in code, citable as engineering) from *open/unproven* (must stay labelled candidate
until TODO-051 measures it).

## When NOT to use this skill

| You actually want | Go to sibling skill |
|---|---|
| The hunch→accepted-result method, evidence bar, idea lifecycle | `crisai-research-methodology` |
| Executing the TODO-051 eval-baseline campaign step by step | `crisai-eval-baseline-campaign` |
| Proof recipes (router golden set, TestNNN reproduction mechanics, trace-based proof) | `crisai-proof-and-analysis-toolkit` |
| Past incidents and root causes in full | `crisai-failure-archaeology` |
| The design decisions and enforced invariants themselves | `crisai-architecture-contract` |
| Registry file schemas and routing-tuning mechanics | `crisai-semantic-registry-reference` |

## The claim discipline

1. **The claim is never an ingredient; it is the combination and the discipline.**
   RAG, guardrails, LLM-as-judge, multi-agent debate, config-driven routing, and
   eval harnesses are all known art with mature open-source implementations.
   Claiming any of them as novel will be — correctly — rejected. What is defensible
   is the *specific composition*: identity-anchored + human-confirmed + materialised
   + fail-closed grounding; a *complete* routing vocabulary as auditable, validated,
   regression-tested configuration; governance gates that structurally cannot be
   prompted around; and release thresholds over all of it. Even that composition
   claim needs measured evidence before it goes outside.
2. **Route every claim through the TODO-051 baseline.** A claim is publishable only
   when a versioned evaluation set produces the number that supports it, with the
   configuration pinned (see Reproducibility standard below).
3. **Label everything unproven as open/candidate.** In any external draft, shipped
   mechanisms may be described as engineering ("crisAI does X, see code"); benefits
   ("X reduces wrong-source continuation") stay hypotheses until measured.

## Positioning caveats — state these before reviewers do

| Caveat | Fact (verified 2026-07-02, main @ c39273b) | Consequence for external material |
|---|---|---|
| Name is temporary | TODO-026 (P1): "crisAI was the prototype name"; repo/package/CLI/MCP rename planned pre-rollout | Avoid deep crisAI branding in papers, slides, URLs, identifiers. Describe the system generically ("the workstation") with the name as a footnote. |
| Org-specific content in a nominally org-neutral tool | UCL-branded content exists: `workspace/knowledge/templates/ucl/`, `registry/ui.yaml` `ucl_dark` theme, `src/crisai/apps/.style.md` ("UCL Design System"), ~23 UCL mentions in `reference/knowledge-authoring-prompts.md` | Say "deployed for one organisation (a UK university)"; do not present it as proven multi-org. Provider-neutrality (VISION Principle 5) is a design intent, demonstrated for M365 only. |
| Single-author, young codebase | Whole history 2026-04-18 → 2026-07-01 (~2.5 months, 629 commits, one author: `git shortlog -sn HEAD`) | Reviewers will check. State it plainly; frame results as a case study, not a community project. No external users, no pilot data. |
| Security defaults are opt-in locally | API auth is a no-op unless `CRISAI_API_KEY` is set; rate limit default 0/disabled (`src/crisai/apps/web.py:133,195`) | Do not claim "secure by default"; claim secure-by-design *architecture* with documented local single-user defaults. |
| Approval policy overstates | `registry/policies.yaml` `approvals.enabled: true` has no central enforcement (TODO-032); real protection is workspace-server path/write restrictions | Never describe an approval gate that does not exist. |
| Flagship mechanism is off by default | `CRISAI_MATERIALISE_SOURCES` opt-in (`src/crisai/cli/pipelines.py:221`, `.env.example:84` = false) | "Shipped behind a flag, not yet default" — say so. |
| Known parity gap in the mechanism itself | Peer mode still runs the retrieval planner with full source-search servers (`pipelines.py:1676`) while pipeline mode strips them (`pipelines.py:1207`, `_PLANNER_FRAMING_DENIED_SERVERS:620`) — TODO-057 | The structural-enforcement story has a documented open hole; disclose it or fix it before claiming completeness. |

---

## Pillar 1 — Grounding discipline

Durable source anchors + confirmed materialisation + hard gates against
wrong-source continuation.

### Known art, and where it stops

Retrieval-augmented generation, citation-carrying answers, groundedness/
faithfulness scoring (RAGAS-style metrics, LLM-as-judge checks), and vector-store
grounding are all established. The gap in common practice: RAG systems typically
**re-retrieve per turn against a live, mutable index**, identify sources by
title/similarity rather than stable provider identity, and treat grounding checks
as advisory scores rather than run-blocking gates. crisAI's reproduced failure
class — *wrong-source continuation* — is exactly what that known art does not
prevent: session `Test001` (2026-06-14, ADR-015 Context) resolved the right deck in
turn 1, then in turn 2 dropped the anchor, live-re-searched OneDrive, and matched an
unreadable `~$` Office lock stub instead. A second repo-documented finding: **prompt
instructions are not enforcement** — commit `9c9ee2e` (#30) records the model
ignoring a literal "do not retrieve" instruction; the fix was structural tool
stripping, not better prompting.

### crisAI's shipped mechanism (the citable asset)

| Mechanism | Evidence (file / commit) |
|---|---|
| Design: anchors keyed by stable provider identity (sourcedoc GUID/driveItem id), never title; resolved-on-reference before any live search; revision lifecycle canonical/superseded/stale | `reference/decisions/CRISAI-ADR-015-source-grounding-backbone.md` (accepted 2026-06-14) |
| One logical document = one anchor | commit `0cdd086` (#26) |
| Per-task, revision-keyed evidence store (raw file + extracted sidecar) | `src/crisai/workspace/source_cache.py`; commit `6443122` (#27). Cache written under the **visible** task dir (`session_store.task_dir()` → `workspace/tasks/<task>/sources/<id>/<revision>/`, `pipelines.py:259`) so agents can read it — note `source_cache.py:4` docstring still says `.crisai/sources/`, stale relative to the wiring |
| Agent-invisible fetch: `tools.internal` class; `download_source_bytes_by_handle` reachable only by the deterministic path | `registry/servers.yaml:266-267`, `src/crisai/orchestration/source_fetch.py:27`; commits `add236f` (#33), `35f6604` (#35) |
| Checkpoint-time materialisation wired in **both** retrieval-capable modes | `_materialise_confirmed_sources` called at `pipelines.py:1373` (pipeline) and `:1778` (peer); commits `2ed10bd` (#38), `841769e` (#44) |
| Anchor-first read-through of the cached copy | commits `4f7b65c` (#40), `1749a65` (#41) |
| Hard gates (fail-closed, not advisory): evidence bundle must validate as `evidence_bundle_v1` or the run dies after one repair retry (`WorkflowValidationError`) | `src/crisai/orchestration/evidence_contract.py:221`; `pipelines.py:1288-1295` |
| Human retrieval checkpoint (continue/redirect/stop) before costly continuation | `src/crisai/orchestration/retrieval_checkpoint.py:7` |
| Trace-visible cache behaviour: `SOURCE_MATERIALISED` / `SOURCE_CACHE_HIT` events | `pipelines.py:299` |
| Junk filtering at the connector (`~$` lock stubs impersonating real decks) | commit `2455c1c` (#28) |

### Open / unproven (label as such)

- `CRISAI_MATERIALISE_SOURCES` is off by default; TODO-048 and TODO-003 remain
  `in-progress` (checkpoint pin/retire, revision invalidation completeness,
  the multi-turn regression test are named-open in the TODO-048 row).
- TODO-057: peer-mode planner still exposed to source-search tools.
- **No measurement exists** that the discipline reduces wrong-source continuation,
  cost, or failure rate versus plain per-turn retrieval. The Test001 narrative is a
  reproduction, not a statistic.

### What must be proven before claiming externally

Via the TODO-051 baseline: a versioned eval set containing Test001-class multi-turn
reference cases, run flag-off vs flag-on, measuring (a) wrong-source-continuation
rate, (b) gate-kill rate, (c) retrieval cost/latency delta. Reproducibility
standard: each case is a named TestNNN-style reproduction; the eval set is
versioned; results pin model ids and env non-defaults (see Reproducibility
standard).

### First three concrete steps in this repo

1. Codify the reproduced failures as replayable eval cases: Test001 (multi-turn
   "v2" reference), Test003 defects A/B (commits `a49593c`, `9c9ee2e`), Test006
   (output path became input source scope, commit `2f41bec`). Raw material exists:
   task dirs `workspace/tasks/Test001..Test007` and run JSONs under
   `workspace/tasks/<task>/.crisai/runs/` for all of Test001–Test007 as of
   2026-07-02 (Test001: 33 runs; Test006 and Test007: 2 each, dated 2026-06-14 —
   full corpus inventory → `crisai-eval-baseline-campaign` §0.1); commit bodies
   `2f41bec`/`841769e` complement them with the root-cause analysis.
2. Build a trace scorer over `logs/` run events counting `SOURCE_MATERIALISED`,
   `SOURCE_CACHE_HIT`, `POLICY_VIOLATION`, and final outcome per run.
3. Run the case set with `CRISAI_MATERIALISE_SOURCES` off vs on (this machine's
   local `.env` already sets true — a non-default; always state which) and record
   the two rates side by side.

### You have a result when…

…a versioned eval set replays the multi-turn reference class over N repeated runs
and the measured wrong-source-continuation rate is materially lower with the
backbone on than off (target: zero for anchored references), with the difference
surviving re-runs. Falsified if the flag-on rate is not better, or the gates kill
legitimate runs at a rate that erases the benefit.

---

## Pillar 2 — Registry-owned semantics

Routing behaviour as auditable, validated, regression-tested configuration.

### Known art, and where it stops

Config-driven feature flags, rule engines, intent classifiers, and "semantic
router" libraries are known art; so is keeping prompts in files. What is uncommon:
holding the **entire** routing/verification vocabulary — router term families,
peer-verifier regexes, contract markers, lexicon, retrieval source-fit constraints,
intent/deliverable graph vertices and expansion edges — in two owned YAML files
(`registry/semantic_catalog.yaml`, 725 lines; `registry/semantic_graph.yaml`,
699 lines), with a validator, a golden regression set, and an enforced review rule
that vocabulary never lives in Python. The typical alternative scatters this
vocabulary through code and prompts, making routing behaviour unauditable and
undiffable.

### crisAI's shipped mechanism (the citable asset)

| Mechanism | Evidence |
|---|---|
| Two-file ownership split, documented in both file headers and enforced as a review rule | `registry/semantic_catalog.yaml:1-4`, `registry/semantic_graph.yaml` header; ADR-002 |
| Cross-file validation: doctor errors when a graph vertex term collides with a catalog function word | `src/crisai/registry_validation.py:511-513`; `uv run crisai doctor` |
| Router golden regression set (canonical query → expected intent + mode, parameterised) | `tests/unit/test_router_regression.py:22` (`GOLDEN_CASES`, 28 cases as of 2026-07-02), `test_router_golden:187` |
| Scar tissue proving the rule is real, not aspirational: hardcoded vocabulary repeatedly leaked into Python and was migrated back | commits `ef7ff0c` ("remove hardcoded _DEFAULT_CONFIG vocabulary"), `da29d33` ("move memory markers to semantic catalog") |
| Registry vocabulary tightened as part of a named-reproduction fix | commit `2f41bec` (#43): tightened workspace `source_scope_markers` to read/fetch phrasing alongside a code fix to the source-fit gate (`cli/pipelines.py`, `orchestration/source_constraints.py`) after Test006 — NOT a registry-only fix |
| Semantics version pinning in traces | `graph_version` = sha1 of graph file bytes (`src/crisai/orchestration/retrieval_association_graph.py:42`) |

### Open / unproven (label as such)

- The ownership rule leaks: route-hint thresholds live in Python
  (`request_contract.py`), `workflow_policy.yaml` capability markers and
  `search_synonyms.yaml` hold vocabulary outside the two sanctioned files, and
  TODO-049 records a term-duplication contradiction between catalog and graph.
- The catalog self-describes as "legacy" — a migration to graph-emitted facts is
  mid-flight; do not present the split as final.
- Doctor does not validate graph edge endpoints, emit-key vocabulary, or
  `primary_intent` values against the wired set — silent-tolerance gaps.
- No measured routing-accuracy number exists.

### What must be proven before claiming externally

Routing accuracy measured on the TODO-051 versioned eval set (routing is an
explicit TODO-051 dimension), with the semantic files pinned by hash, plus at least
one end-to-end demonstration that a misrouting class was fixed by a registry-only
diff without regressing the golden set. No such purely registry-only fix has been
demonstrated yet (2f41bec's Test006 fix paired its catalog edit with gate code
changes) — the demonstration is still to be produced.

### First three concrete steps in this repo

1. Extend `GOLDEN_CASES` until every branch of the router cascade
   (`src/crisai/orchestration/router.py:111-353`) has at least one case, so the
   golden set is a coverage instrument, not a sample.
2. Resolve or explicitly document the TODO-049 duplication and the out-of-file
   vocabulary (workflow_policy/search_synonyms) so the auditability claim is clean.
3. Add routing accuracy as a scored dimension of the eval runner, recording
   `graph_version` and a catalog-file hash with every result.

### You have a result when…

…routing accuracy over the versioned eval set is a published number tied to pinned
semantic-file hashes, and you can show a before/after pair where a registry-only
edit moved a failing case class to passing with the golden set green. Falsified if
fixing new misroutes routinely requires Python changes (the thresholds-in-code leak
becoming dominant would falsify the "routing is configuration" claim).

---

## Pillar 3 — Governed agent workflows

Author/challenger/refiner/judge with schema contracts and human-accountable
checkpoints.

### Known art, and where it stops

Multi-agent debate, self-critique/reflexion, LLM-as-judge, and role-based agent
frameworks (CrewAI/AutoGen-style) are known art. Common practice treats critique
as advisory and roles as prompt personas sharing one tool surface. The specific
discipline here: the judge is a **fail-closed gate** (a non-accept verdict raises
`WorkflowValidationError` and stops the run before finalisation), roles have
structurally different tool scopes (challenger and judge are read-only per
`registry/agents.yaml`), inter-stage state is schema-backed JSON rather than prose,
and the costly decisions stay human: retrieval confirmation, and knowledge
promotion which agents structurally cannot perform (agents write only
`knowledge_staging/`; promotion to `knowledge/` is a human git PR —
`registry/workspace_spaces.yaml`, `reference/knowledge-base-programme.md`). VISION
non-goals explicitly renounce replacing governance boards or human sign-off
(`reference/VISION.md:272-284`) — the pitch is *governed*, not autonomous.

### crisAI's shipped mechanism (the citable asset)

| Mechanism | Evidence |
|---|---|
| Peer workflow: author → challenger → refiner → judge, with refinement rounds, stagnation detection, bounded escalation | `run_peer_pipeline` (`src/crisai/cli/pipelines.py:1543`); prompts `prompts/design_author.md`, `design_challenger.md`, `design_refiner.md`, `judge.md` |
| Judge non-accept is a hard stop (traced as `POLICY_VIOLATION`, raises before finalisation) | `pipelines.py:2107-2129` |
| Final-deliverable verification against registry-owned regexes, with one repairable round | `src/crisai/orchestration/peer_verifier.py:388`; patterns in `semantic_catalog.yaml:231` (`peer_verifier`) |
| Schema-backed machine state (evidence bundles, request/task contracts, peer run contract, checkpoint decisions) | `src/crisai/schemas/*.schema.json`; ADR-003/ADR-004 |
| Human checkpoint at retrieval (continue/redirect/stop, bounded redirects) | `retrieval_checkpoint.py`; VISION near-term #1 (Done, TODO-001) |
| Structural human gate on knowledge promotion (staging read-write vs knowledge read-only) | `registry/workspace_spaces.yaml`; peer mode designated mandatory for high-stakes knowledge types (`reference/knowledge-base-programme.md:113-118`) |
| Doctrine that governance is structural, not prompt-level | commit `9c9ee2e`; ADR-013 tool `allow`/`internal` split |

### Open / unproven (label as such)

- Judge quality is unmeasured: no data on whether judge accept/reject agrees with
  human acceptance, nor whether challenger+refiner measurably improve artefacts
  over single-agent authoring. Today the gate's value is asserted, not shown.
- TODO-022: a mid-run peer failure discards all upstream work (no partial
  recovery) on the most expensive path.
- TODO-032: approvals config without central enforcement (see caveats table).
- TODO-057: peer planner tool-scoping parity gap.
- TODO-018: systematic artefact quality gates not yet built; TODO-033/034/035
  (roles, assurance, sign-off operating model) are unstarted design work.

### What must be proven before claiming externally

Via TODO-051: (a) peer mode vs single/pipeline mode on the same authoring tasks,
scored for grounded artefact quality at stated cost/latency multiples; (b) judge
calibration — agreement rate between judge verdicts and human review verdicts;
(c) gate precision — how often the hard stop blocks genuinely bad output vs kills
good runs.

### First three concrete steps in this repo

1. Define an artefact-quality rubric anchored to the existing validation profiles
   (`registry/workspace_artifact_profiles.yaml`, `crisai validate-artefacts`) plus
   the TODO-018 gate dimensions, so scoring is repeatable.
2. Run a fixed authoring task set in single vs peer mode; capture cost via
   `uv run crisai spend` (pricing in `registry/models.yaml`) and outcomes from
   traces; score both arms with the rubric.
3. Record judge decisions alongside a human verdict for each peer run in the set;
   compute agreement.

### You have a result when…

…on a versioned authoring task set, peer mode beats single mode on the rubric by a
stated margin at a stated cost multiple, and judge/human agreement is a published
rate. Falsified if peer mode's quality delta is within noise of its cost premium,
or the judge agrees with humans no better than chance — either finding would gut
the governance-workflow claim and must be reported, not buried.

---

## Pillar 4 — Measured LLM quality (the gate pillar)

Release-threshold evaluation — TODO-051. Every other pillar's external claim
routes through this one.

### Known art, and where it stops

Eval harnesses, benchmark suites, LLM-as-judge scoring, and CI-integrated evals
are abundant known art (HELM/promptfoo/RAGAS-class tooling). "We have evals" is
not a claim. The defensible claim is narrower and operational: **release-threshold
discipline for a governed enterprise-architecture workstation** — a versioned,
representative eval set covering routing, named-source resolution, source fit,
evidence grounding/citation, summary fidelity, artefact quality, policy gates,
cost, latency, and human acceptance, with defined release thresholds and a
documented baseline-change approval process. That is TODO-051's acceptance text
verbatim (`reference/TODO.md:99`), and it is the part most LLM products skip.

### What exists today (be precise — this pillar is mostly open)

As of 2026-07-02, TODO-051 is `todo`. Nothing shipped. The raw material:

| Asset | Evidence | Status |
|---|---|---|
| De facto reproduction corpus: named live test sessions | `workspace/tasks/Test001..Test007`, `test003`, `NewTest-*` dirs; run JSONs under `workspace/tasks/<task>/.crisai/runs/` | Unversioned and undocumented; run JSONs exist on disk for all of Test001–Test007 (Test006/007: 2 each as of 2026-07-02 — inventory → `crisai-eval-baseline-campaign` §0.1), with root-cause analysis in commit bodies `2f41bec`, `841769e` |
| Commit-body post-mortem convention: symptom → named TestNNN reproduction → root cause → fix → "Full suite green (N passed)" ledger | e.g. `git show 2f41bec` | A working reproducibility culture, not a harness |
| Router golden set | `tests/unit/test_router_regression.py` | Deterministic routing only; no LLM-output quality |
| Cost telemetry | `crisai spend` (`src/crisai/cli/main.py:601`), per-model pricing in `registry/models.yaml` | Observability, not thresholds |
| Trace events for grounding/gates | `SOURCE_MATERIALISED`, `POLICY_VIOLATION`, `policy_signal` in `logs/` traces | Scoring inputs, unaggregated |
| Config pinning primitives | `graph_version` sha1 in traces; models.yaml as single source of model ids | Partial — catalog hash and env snapshot not captured |

### What must be proven before claiming externally

This pillar *is* the proof machinery. Before any external claim from pillars 1–3:
the versioned eval set exists, thresholds are defined, at least one full baseline
run is recorded, and the reproducibility standard below is met. Before claiming
pillar 4 itself externally ("we gate releases on measured LLM quality"): at least
one release decision must actually have been gated by the thresholds.

### First three concrete steps in this repo

1. Inventory and version the TestNNN corpus: for each of Test001–Test007, extract
   from the task dir and/or commit body the prompt sequence, expected behaviour,
   and failure mode; store as a documented, reviewed eval-set artefact (through
   change control — see `crisai-change-control`; execution detail is owned by
   `crisai-eval-baseline-campaign`).
2. Define the metric per TODO-051 dimension and a provisional threshold for each,
   written down before the first measurement run (hypothesis-predicts-numbers —
   see `crisai-research-methodology`).
3. Build the repeatable runner + regression report so a second run is one command,
   and wire the report into the release checklist (TODO-050 governance baseline).

### You have a result when…

…there exists a versioned eval-set identifier, per-dimension thresholds, and a
baseline report such that a hypothetical release **can fail** — i.e. the gate is
capable of saying no. Falsified/degenerate if thresholds are set post hoc to
whatever the system already scores, or if the set is too small for a regression to
move any number (a gate that cannot fail is not a result).

---

## Reproducibility standard (applies to every pillar)

Any number intended for external use must record, at minimum:

1. **Named reproduction**: each eval case traceable to a TestNNN-style named
   session or a documented synthetic case — the repo's existing convention
   (commit bodies `2455c1c`, `a49593c`, `9c9ee2e`, `0b63dbf`, `b386a17`,
   `2f41bec`, `841769e` each name their reproduction).
2. **Versioned eval set**: an immutable set identifier; changes to the set go
   through a documented approval process (TODO-051 acceptance requirement).
3. **Pinned semantics**: `graph_version` (sha1 of `registry/semantic_graph.yaml`
   bytes, reported in traces) plus a hash of `registry/semantic_catalog.yaml`.
4. **Pinned models and config**: exact model ids from `registry/models.yaml`
   (model names are user configuration — never assume defaults) and all env
   non-defaults. Known local non-defaults on this machine as of 2026-07-02:
   `CRISAI_MATERIALISE_SOURCES=true`, `CRISAI_DEFAULT_MODEL=gpt-5.4-nano` —
   shipped defaults differ, so locally observed behaviour is not default behaviour.
5. **Repeat runs**: LLM outputs are stochastic; report across N runs, not one.
6. **Cost disclosure**: per-run spend from the usage-cost telemetry.

## Provenance and maintenance

Verified 2026-07-02 against main @ `c39273b`. Line numbers drift; re-verify before
relying on them:

- TODO-051/026/048/057 status: `grep -n "TODO-051\|TODO-026\|TODO-048\|TODO-057" reference/TODO.md`
- Materialisation flag + default: `grep -n "CRISAI_MATERIALISE_SOURCES" src/crisai/cli/pipelines.py .env.example`
- Judge hard gate: `grep -n "judge did not accept" src/crisai/cli/pipelines.py`
- Evidence schema pin: `grep -n "evidence_bundle_v1" src/crisai/orchestration/evidence_contract.py`
- Planner asymmetry (TODO-057 open?): `grep -n "_framing_only_planner_spec" src/crisai/cli/pipelines.py` (fixed when the peer path also wraps the spec)
- Internal tool split: `grep -n "download_source_bytes_by_handle" registry/servers.yaml src/crisai/orchestration/source_fetch.py`
- Router golden set size: `grep -cE '^\s*\(' tests/unit/test_router_regression.py`
- Doctor function-word check: `grep -n "all_function_words" src/crisai/registry_validation.py`
- Registry file sizes: `wc -l registry/semantic_catalog.yaml registry/semantic_graph.yaml`
- Eval corpus dirs: `ls workspace/tasks/ | grep -i test`
- Single-author + age: `git shortlog -sn HEAD | head -3` and `git log --reverse --format=%ad --date=short | head -1`
- UCL-specific content: `ls workspace/knowledge/templates/`; `grep -n ucl_dark registry/ui.yaml`; `head -1 src/crisai/apps/.style.md`
- Rename status: `grep -n "TODO-026" reference/TODO.md`
- Security defaults: `grep -n "CRISAI_RATE_LIMIT_RPM\|CRISAI_API_KEY" src/crisai/apps/web.py | head`
- Approvals gap: `sed -n '1,15p' registry/policies.yaml` and `grep -n "TODO-032" reference/TODO.md`
