---
name: crisai-eval-baseline-campaign
description: Executable, decision-gated campaign runbook for TODO-051 — building crisAI's LLM product-quality evaluation and acceptance baseline (routing accuracy, named-source resolution, source fit, grounding/citation, summary fidelity, artefact quality, policy gates, cost, latency, human acceptance). Load this when asked to work on TODO-051, "the eval baseline", "product quality evaluation", "release thresholds", "regression reporting for LLM quality", measuring whether a run retrieved the right sources or stayed grounded, building an eval harness or LLM-judge, or deciding whether the TestNNN run corpus can serve as an evaluation set.
---

# crisAI evaluation-baseline campaign (TODO-051)

**Campaign target** (owner-confirmed 2026-07-02): `reference/TODO.md` row TODO-051, priority P0, status `todo` — no commits have touched it yet. Its Definition of Done is the requirements spec for this whole campaign:

> Add a **versioned representative evaluation set** covering **routing, named-source resolution, source fit, evidence grounding/citation, summary fidelity, architecture artefact quality, policy gates, cost, latency, and human acceptance**. Define **release thresholds**, **regression reporting**, **safe handling of evaluation sources**, and a **documented process for approving baseline changes**.

Its rationale is the campaign's founding axiom — internalise it before touching anything:

> "Passing deterministic tests does not establish that an LLM workflow retrieves the right sources, remains grounded, produces useful architecture artefacts, or does so within acceptable cost and latency."

A green `uv run pytest` (a ~900-test deterministic suite as of 2026-07-02 — commit bodies ledger the exact count) is **not** product quality. This campaign builds the thing that measures product quality.

Related backlog wiring (verified in `reference/TODO.md`): TODO-018 (architecture quality gates) says its gate outcomes "feed the evaluation baseline in TODO-051"; TODO-027 (test hardening) explicitly says "Keep product-quality LLM evaluation in TODO-051"; the Recommended Sequencing step 1 groups TODO-050/051/030 as the team-adoption gate. TODO-030 (trace/log redaction, also untouched P0) constrains how evaluation sources may be handled — see Phase 5.

## When NOT to use this skill

- **Deterministic test mechanics** (exact pytest commands, markers, coverage gate, conftest stub trap, how to add unit tests, the existing golden/certified inventory as QA assets) → `crisai-validation-and-qa`.
- **The general hunch→accepted-result method** (evidence bar, hypothesis-predicts-numbers, experiment-flag lifecycle) → `crisai-research-methodology`. This skill is the one concrete campaign; that skill is the discipline.
- **Proof recipes for individual changes** (prove a routing change, prove a gate change against a TestNNN reproduction) → `crisai-proof-and-analysis-toolkit`.
- **Trace/log anatomy, `crisai spend` deep usage, run-JSONL interpretation as measurement tools** → `crisai-diagnostics-and-tooling`.
- **Branch/PR/commit/CI gating for landing the harness** → `crisai-change-control`.
- **External positioning / what counts as a publishable result** → `crisai-research-frontier`.

## Ground rules (fenced wrong paths — read before Phase 0)

These are the failure modes this repo has already paid for. Do not re-derive them.

| Wrong path | Why it is fenced | Evidence |
|---|---|---|
| **Judging output quality by eye** and calling it evaluated | The TODO-051 rationale exists precisely because "looks right" and deterministic-green both failed to predict the Test001–Test007 live failures | TODO-051 row; every defect in the Test corpus was found in live runs, not review |
| **Treating deterministic suite green as product quality** | ~830 passing tests (commit ledgers of 2026-06-13/14 record 828–835 passed) coexisted with wrong-source continuation (Test001), a gate false positive (Test006), a retrieval-reformulation failure (Test005), and competing planner searches (defect B) | TODO-051 rationale |
| **Building the eval on live SharePoint/OneDrive sources** | The live index drifts: real files drop out and `~$` Office lock stubs impersonate them (commit 2455c1c); Graph search is word-order sensitive (commit b386a17). An eval set on live sources measures index weather, not product quality | ADR-015 context; Test001/Test005 |
| **Putting eval vocabulary (judge criteria, expected intents, threshold terms) in Python source** | Semantic vocabulary lives in `registry/semantic_catalog.yaml` / `semantic_graph.yaml` by project rule (ADR-002); hardcoded-vocab leaks were repeatedly reverted (commits ef7ff0c, da29d33) | CLAUDE.md rule; ADR-002 |
| **Letting the eval spend tokens unbounded** | Token spend is one of the two highest-risk operations (VISION security principles). Bound every live-eval run structurally: `CRISAI_AGENT_MAX_TURNS` (default 30), `CRISAI_AGENT_STAGE_TIMEOUT_SECONDS` (default 300), `CRISAI_PEER_MAX_REFINEMENT_ROUNDS` (default 2), and — via the web API — `CRISAI_RATE_LIMIT_RPM` (default 0 = disabled; covers POST `/api/run`, `/api/run/start`, `/api/v1/runs` only, `src/crisai/apps/web.py:134`) | VISION; `crisai-config-and-flags` for the full catalogue |
| **Prose handoffs for eval results** | Machine-critical state must travel as JSON contracts / typed objects; reviewers must reject prose-only handoffs. An eval report a machine gates on is machine-critical | CLAUDE.md rule; decision of 2026-06-15 |
| **Trusting an LLM judge before proving it** | See Phase 2, option C obligations. An unproven judge is "judging by eye" with extra steps and token cost | — |
| **Committing business content into a versioned eval set** | Traces and task artefacts intentionally contain source excerpts; write-time redaction is incomplete (TODO-030). The existing corpus contains real UCL documents' content | TODO-030 row; Phase 5 |
| **Inventing accepted threshold numbers** | Every threshold in this skill is labelled CANDIDATE. Accepted numbers come only from Phase 3 baseline measurement plus the Phase 5 approval process | — |

One operational trap while you work: any `pytest` invocation imports the MCP server modules, which treat `sys.argv[1]` as a workspace root at import time and create `<first-arg>/.auth/` (`src/crisai/servers/sharepoint_server.py:29-34`). Flags-first invocations litter the repo root (`--no-cov/`, `-q/` droppings exist as of 2026-07-02); path-first invocations litter the test dir (`tests/unit/.auth/` exists). Live bug, unfixed. Details and cleanup → `crisai-diagnostics-and-tooling`.

---

## Phase 0 — Inventory what already exists

Nothing in this campaign starts greenfield. Three real assets exist. Verify each; the expected observations below were true on 2026-07-02 on the primary workstation.

### 0.1 The de facto run corpus (TestNNN sessions)

```bash
ls workspace/tasks/
for d in workspace/tasks/Test00* workspace/tasks/test003 workspace/tasks/NewTest*; do
  echo "$d: $(ls "$d"/.crisai/runs/*.json 2>/dev/null | wc -l) run JSONs"
done
```

**Expected** (2026-07-02): task dirs `Test001`–`Test007`, lowercase `test003`, `NewTest-02`..`NewTest-05`, `NewTests-01`, plus real work tasks (Power-BI*, Template_creation, architecture, …). Run-JSON counts: Test001: 33, Test002: 1, Test003: 1, Test004: 2, Test005: 1, Test006: 2, Test007: 2, test003: 3, NewTest-02: 4, NewTest-03: 2, NewTest-04: 6, NewTest-05: 2, NewTests-01: 4 — **63 recorded runs, of which 49 `completed` and 14 `failed`**. The failed runs are the valuable ones: they are labelled reproductions of real defects (Test005 = retrieval reformulation defect — word-order-sensitive Graph search, b386a17 — with polluted extracted constraints (TODO-055), where the gate fire itself was correct per the b386a17 post-mortem; Test004 peer run = empty planner output; Test001 = the wrong-source-continuation failure that motivated ADR-015).

**If dirs are missing instead → branch:** the corpus is machine-local. `.gitignore:81` ignores `workspace/tasks/*/` (only `README.md` is tracked — verify with `git ls-files workspace/tasks/`). On any other clone the corpus does not exist. This is finding #1 of the campaign: **the only representative evaluation data the project has is unversioned, single-machine, and contains real business content.** The DoD word "versioned" is therefore not yet satisfiable by pointing at this corpus — see Phase 5.

Each run JSON is schema `ui_run_state_v1` with top-level keys `schema_version, run_id, session, status, decision, expected_stages, events, final_output, error, metadata`. Signals inside (all verified against real files):

| Signal | Where in the run JSON |
|---|---|
| Routing decision | `decision` = `{intent, mode, agent, needs_retrieval, needs_review, confidence, reason}`; also a `routing_decision` event whose `metadata` adds `model_ref`, `provider`, `model_name` |
| Request contract | `metadata.request_contract` (schema `request_contract_v1`): `named_sources`, `resolved_sources`, `referenced_anchors`, `source_required`, `source_families`, `required_evidence_level`, `output_path`, `actions`, `quality_gates`, `route_hints` |
| Gate outcomes | `status: failed` + `error` string (e.g. `"Policy gate failed: source inventory contains item(s) outside the user's source constraints…"`); `stage_failed` / `run_failed` events |
| Human checkpoint | `checkpoint_requested` / `checkpoint_decision` events (present in the corpus) |
| Latency (coarse) | first-event vs last-event `timestamp` delta |
| Final output | `final_output` (prose; strip before any machine gating) |
| Trace linkage | `metadata.trace_run_id` joins to `logs/agent_trace.jsonl` `run_id` |

Event vocabulary observed across all 63 runs: `run_created, routing_decision, task_contract, checkpoint_requested, checkpoint_decision, stage_started, stage_delta, stage_output, stage_skipped, stage_failed, final_answer, run_completed, run_failed`.

### 0.2 The router golden set (the one metric that already has a harness)

```bash
grep -c '^    (' tests/unit/test_router_regression.py   # rough; authoritative count below
python3 - <<'EOF'
import ast
t = ast.parse(open('tests/unit/test_router_regression.py').read())
for n in ast.walk(t):
    if isinstance(n, ast.AnnAssign) and getattr(n.target,'id','')=='GOLDEN_CASES':
        print(len(n.value.elts), 'golden cases')
EOF
```

**Expected** (2026-07-02): **28 golden cases** in `GOLDEN_CASES` (`tests/unit/test_router_regression.py:22`), tuples of `(query, expected_intent, expected_mode)`, covering 12 intents (discovery 4, summary 4, peer_review 3, then 2 each of operations/publication/critical_peer_review/discovery_design/design_review/review/design/orchestrator, mixed_complexity 1). The test calls `decide_route(query, review_enabled=False, registry_dir=None)` against the **real** `registry/semantic_catalog.yaml` with the semantic-graph nudge monkeypatched off — fully deterministic, no LLM, no network, no API key. The file also carries four scenario tests (architecture prompts must not route to `operations`; genuine runtime troubles must; bare "continue" continuation; explicit pipeline-mode override). Its docstring is the extension contract: "Adding a new routing path: append a tuple to GOLDEN_CASES."

This is the template for every deterministic eval axis: real registry in, expected structured decision out, runs in CI already.

### 0.3 Cost/latency telemetry (exists, but cost is dormant on this machine)

```bash
grep -n '^\s*pricing:' registry/models.yaml ; echo "exit=$?"
uv run crisai spend --last 3
```

**Expected** (2026-07-02): the grep finds **nothing** (exit=1) — no model entry has a `pricing:` block, only the commented example at the top of `registry/models.yaml`. Consequently `crisai spend` prints `No cost events found for any run. / Cost tracking requires model pricing configured in registry/models.yaml.` and exits 0.

**If pricing blocks exist instead → branch:** someone has already activated cost telemetry; `crisai spend --last N` (default 1, `--run <prefix>` to filter) will print per-stage rows (Run, Stage, Agent, Provider, Model, In, Out, Cost USD) plus per-run totals, parsed from `logs/agent_trace.jsonl` events carrying `metadata.observability.cost` with `schema_version: usage_cost_v1`. Skip the pricing-activation step in Phase 3.

Even without pricing, **token and latency signals exist today**: every `stage_output` trace event carries `metadata.observability` (`ui_stage_observability_v1`) with `provider_usage` (`requests, input_tokens, output_tokens, total_tokens, cached_tokens`) and `execution_time` (`started_at, ended_at, duration_ms`). Verified in the local `logs/agent_trace.jsonl` (last written 2026-06-19). The cost estimator is `src/crisai/orchestration/usage_cost.py` (`usage_cost_metadata()`: returns `None` unless both provider usage and valid registry pricing are present — it never guesses).

### 0.4 What does NOT exist (verified 2026-07-02)

- No `tests/eval/` directory (`ls tests/` → `cli integration orchestration smoke unit` + `conftest.py`).
- No materialised source caches: `find workspace/tasks -maxdepth 2 -name sources -type d` returns nothing — despite the local `.env` setting `CRISAI_MATERIALISE_SOURCES=true`, the 63-run corpus predates the ADR-015 materialisation wiring. Grounding evaluation cannot lean on existing cached sources.
- `workspace/tasks/Test001/.crisai/anchors.json` is `{"schema_version": "session_anchors_v1", "anchors": []}` — the anchor store is empty in the recorded corpus; named-source-resolution signals must come from `request_contract` fields and future runs, not historical anchors.
- No eval, threshold, or baseline vocabulary anywhere in `registry/` or docs.

**Gate to Phase 1:** you can state, with commands run, (a) how many recorded runs exist here, (b) that they are unversioned, (c) the golden-set size, (d) whether cost telemetry is active. If any of these four is unknown, stay in Phase 0.

---

## Phase 1 — Define the metric set (the DoD's ten axes)

For each DoD axis: a measurable definition, the repo data source, and a CANDIDATE quality bar. **Every number below is CANDIDATE — a starting hypothesis to be replaced by Phase 3 measurement and Phase 5 approval. None is an accepted threshold.**

| # | Axis | Measurable definition | Data source in this repo (verified) | CANDIDATE bar |
|---|---|---|---|---|
| 1 | Routing accuracy | % of eval queries where `decide_route()` returns expected `(intent, mode)`; optionally `agent`, `needs_retrieval` | `crisai.orchestration.router.decide_route` (deterministic); golden set §0.2; `routing_decision` events in run JSONs | 100% on the golden set (it is deterministic — any miss is a regression, not noise); new candidate queries must pass before promotion into `GOLDEN_CASES` |
| 2 | Named-source resolution | % of runs naming a specific source where `request_contract.resolved_sources`/`referenced_anchors` bind to the correct stable identity before any live search | `metadata.request_contract` fields `named_sources`, `resolved_sources`, `referenced_anchors`; `session_anchors_v1` store `workspace/tasks/<id>/.crisai/anchors.json` | UNSTABLE — TODO-048/TODO-003 (both P0 in-progress) own this behaviour; measure it, but do not set a release bar until the backbone is declared complete |
| 3 | Source fit | Two error rates: gate **false positives** (legitimate run blocked — the Test006 class) and **false negatives** (off-title/off-scope source admitted — the defect-A class) | `_enforce_source_inventory_fit` (`src/crisai/cli/pipelines.py:642`, invoked at :1500); `run_failed` `error` strings; Test006's run JSON is the labelled false-positive exemplar (Test005's gate fire was correct — retrieval reformulation defect, b386a17); TODO-055 tracks the known extractor imprecision | 0 false negatives on the eval set; false positives measured and trending down (structural fixes 2f41bec, b386a17 already landed) |
| 4 | Grounding / citation | % of source-backed runs whose evidence bundle has ≥1 `content_read` item for each required source, empty unrecovered `read_failed`, and whose `final_output` claims map to bundle items | `evidence_bundle_v1` schema (`src/crisai/schemas/`): `items[].evidence_level` ∈ `{search_hit_only, metadata_read, content_read, read_failed}`, `gaps[]`; gate `_validate_evidence_bundle` (`pipelines.py:582`) + `_unresolved_required_read_failures` (`pipelines.py:671`) | Gate-level: 100% (the gate already enforces it fail-closed). Claim-to-evidence mapping: no deterministic signal exists — needs option C (Phase 2) or human labels |
| 5 | Summary fidelity | Faithfulness of summary output to the materialised source content (no invented facts, no dropped critical facts) | **No deterministic repo signal.** Requires frozen source + judged comparison (Phase 2 option C) or human labels. Materialised copies under `workspace/tasks/<id>/sources/` will be the reference text once TODO-048 produces them | undefined until a judging method is proven |
| 6 | Artefact quality | Layer 1 (deterministic): `uv run crisai validate-artefacts` pass rate against `registry/workspace_artifact_profiles.yaml` (required sections, front matter). Layer 2: peer judge verdicts per `peer_run_contract` `acceptance_dimensions`. Layer 3: TODO-018 profile-driven checks (not built) | `crisai validate-artefacts` (`src/crisai/cli/main.py:452`, scans knowledge/staging/tasks roots or `--path`); `peer_run_contract.schema.json` (`expected_output_type, must_ground_in_sources, acceptance_dimensions, role_focus_*`) | Layer 1: 100% on eval artefacts (deterministic). Layers 2–3: measure only |
| 7 | Policy gates | Gate decision correctness on labelled cases: every gate fire and every gate pass in the eval set is either expected or a finding | `policy_signal` / `policy_violation` trace events (`logs/agent_trace.jsonl`); `stage_failed`/`run_failed` events + `error` strings in run JSONs; `registry/workflow_policy.yaml` (capability markers → hard requirements, `write_target_subdir: workspace/tasks`) | 100% agreement with labels — gates are deterministic code paths; disagreement means either a gate bug or a bad label |
| 8 | Cost | USD per run and per stage, `usage_cost_v1` estimated cost; interim proxy: input/output token counts | `crisai spend`; `metadata.observability.provider_usage` in trace events (works today); requires `pricing:` blocks in `registry/models.yaml` for USD (§0.3) | measure a distribution first; then CANDIDATE per-workflow-class ceilings (e.g. p95 of baseline + headroom). Do not pick a dollar number before Phase 3 |
| 9 | Latency | Per-stage `execution_time.duration_ms` (trace) and end-to-end run wall time (run-JSON event timestamp delta) | trace `metadata.observability.execution_time`; run JSON timestamps (§0.1). Note the recorded corpus has e.g. a 32 s single-mode discovery run (Test005) | as with cost: distribution first, then p95-based CANDIDATE ceilings per mode (single vs pipeline vs peer are different classes) |
| 10 | Human acceptance | Explicit accept/reject judgement per eval deliverable, recorded as structured data; weak existing proxy: `checkpoint_decision` events (user redirect/stop at the retrieval checkpoint signals rejection of retrieval quality) | `checkpoint_requested`/`checkpoint_decision` events exist in the corpus; **no acceptance record exists for final outputs** — this axis needs a new, schema-backed capture (align with TODO-016, routing feedback capture, P2) | undefined until capture exists; the DoD requires it, so Phase 2 must design it |

Two structural rules for whatever you build here:

1. **Expected values are data, not code.** Golden queries, expected intents, expected gate outcomes, judge criteria are semantic vocabulary → they belong in registry YAML or versioned eval-set files, never inline in Python (ADR-002; CLAUDE.md). The existing `GOLDEN_CASES`-in-Python placement predates this campaign; treat it as grandfathered, and raise the "should the golden set move to registry/eval data?" question in the Phase 2 design rather than silently copying the pattern.
2. **Results are contracts, not prose.** Define an eval-report schema (e.g. `eval_report_v1` under `src/crisai/schemas/`, following the 12 existing JSON schemas there) before writing the first report. A Markdown summary may accompany it; nothing downstream may parse the Markdown.

**Gate to Phase 2:** every one of the ten axes has a written measurable definition and a named data source (or an explicit "signal does not exist — must be built" verdict, as for #5 and #10). If you cannot name the data source, go read the actual files in §0.1 again.

---

## Phase 2 — Build the eval harness (two decision gates)

### Decision gate 2A: where does the harness live?

Constraints (all verified): CI runs `uv run pytest -q` across Python 3.10–3.14 — anything unguarded under `tests/` executes five times per push. pytest `addopts` force `--cov=crisai` with `fail_under = 70`, so subset invocations fail the coverage gate (recurring nuisance in this repo's history). The only registered marker is `smoke` (`pyproject.toml:61-63`); `--strict-markers` is off. The repo-native precedent for opt-in live tests is `tests/smoke/conftest.py`: `require_smoke()` skips everything unless `CRISAI_RUN_SMOKE_TESTS=1`, plus per-provider key skips.

Options, ranked:

1. **`tests/eval/` with a smoke-style env guard** (`CRISAI_RUN_EVALS=1`, own `conftest.py`, own registered marker `eval`). RECOMMENDED for the deterministic axes (#1, #3-gate-level, #6-layer-1, #7) and acceptable for guarded live axes. Pros: inherits pytest infra, parametrisation, CI wiring for the deterministic subset; matches the existing suite-design contract ("network-free except tests/smoke" — extend the sentence, don't break it). Cons: coverage-gate friction on subset runs; pytest argv `.auth` droppings (Ground rules); eval failures must not be conflated with unit-test failures in CI reporting.
2. **A `crisai eval` CLI command** (Typer command beside `spend` and `validate-artefacts` in `src/crisai/cli/main.py`). Best long-term fit with VISION Principle 7 (Observable Cost And Quality) and gives operators a first-class tool; but it is runtime-surface code needing tests, docs, and change control of its own. Reasonable as a **later** promotion of a proven harness, wasteful as the first iteration.
3. **A standalone `eval/` directory of scripts outside `tests/`.** Avoids all pytest friction; loses parametrisation, CI integration, and discoverability; invites exactly the unversioned-scripts drift this campaign is meant to end. Use only for one-off Phase 3 measurement scripts, and promote or delete them.

Whatever you choose: the harness must run **read-only against recorded data by default**, and every live-LLM path must be double-gated (env guard AND explicit CLI/marker selection).

### Decision gate 2B: evaluation methodology per axis

Three methods, with cost/validity trade-offs and proof obligations. Most axes need method A; a few need B; two cannot be measured without C or humans.

**A. Deterministic replay / offline scoring of recorded runs.**
Score the 63 existing run JSONs (and all future ones) against expected structured outcomes: routing decisions, gate fires, contract fields, token/latency numbers.
- Cost: zero tokens. Validity: high for everything that is deterministic given the recorded inputs (routing, gates, contracts, telemetry); **zero** for questions about behaviour not yet recorded.
- Obligation: the scorer must consume only schema-backed fields (`ui_run_state_v1`, `request_contract_v1`, `evidence_bundle_v1`, trace observability), never `final_output` prose.
- Trap: recorded runs embed the registry/code versions that produced them. A replay score is a statement about *that* build. Record `git rev-parse HEAD` and registry file hashes alongside every baseline number.

**B. Live-LLM eval runs against a frozen local source set.**
Drive real runs headlessly — `uv run crisai ask -m "<query>" --session <eval-session> [--pipeline|--peer] --no-retrieval-checkpoint` (all flags verified in `src/crisai/cli/main.py:796`), or POST `/api/v1/runs` with a `ui_run_request_v1` body (`{schema_version, message, mode, agent, review, verbose, session}` required; `retrieval_checkpoint` optional) — then score the produced run JSON with method A's scorer.
- Cost: real tokens per run (bound it — Ground rules). Validity: high, this is the product actually running; **but** non-deterministic: expect run-to-run variance, so score over N repetitions and report rates, not single outcomes.
- Obligation 1 — **frozen sources**: eval queries must resolve against local workspace copies (files under `workspace/`, readable via the workspace MCP), not live SharePoint/OneDrive. The Test001/Test005 history proves live sources make the eval non-reproducible. Building the frozen set is real work: sanitised, synthetic-or-cleared documents that exercise the same shapes (versioned decks, near-duplicate titles, an intentional `~$` lock-stub decoy).
- Obligation 2 — **spend telemetry on**: add `pricing:` blocks to `registry/models.yaml` first (Phase 3.0) so every eval run is cost-accounted via `crisai spend`.
- Obligation 3 — model identity is a variable, not a constant: agents' `model_ref`s come from `registry/agents.yaml` → `registry/models.yaml` and this machine runs a non-default `CRISAI_DEFAULT_MODEL`. Record the resolved provider/model per stage (the `routing_decision` event already carries `model_ref/provider/model_name`) in every eval report.

**C. LLM-as-judge (for summary fidelity #5, claim-to-evidence mapping #4b, artefact usefulness #6-layer-2+).**
- Cost: judge tokens on top of run tokens. Validity: **unproven until you prove it.** Before any judge score enters a baseline or threshold, ALL of the following must hold (this is a theory obligation, not bureaucracy):
  1. **Human agreement**: a seed set of human-labelled examples (accepted/rejected with reasons) exists, and the judge's agreement with those labels is measured and reported. If you cannot state the agreement number, the judge is not proven.
  2. **Self-consistency**: the judge re-scores the same artefact with acceptably low variance across repeated calls (measure it; do not assume temperature-0 determinism across providers).
  3. **Registry-configured identity**: the judge is an agent with its own `model_ref` in registry config (per the per-agent-model rule, ADR-001) — never an inline hardcoded model call. Its rubric/criteria vocabulary lives in registry or versioned eval data, not Python (ADR-002).
  4. **Asymmetric trust**: judge scores may *flag* regressions for human review; they may not *gate* releases until obligations 1–2 are demonstrated and the Phase 5 approval process explicitly admits them.
- Note this repo's prior: prompt instructions are not trusted as contracts here (commit 9c9ee2e — a model ignored "do not retrieve"; enforcement went structural). A judge is a prompt-instructed model. Weight its evidence accordingly.

**Gate to Phase 3:** a written harness design exists stating: chosen location, per-axis method (A/B/C/human), the eval-report schema, the frozen-source plan, and the spend bound per eval campaign run. If the design puts any expected-value vocabulary in Python or any machine-critical result in prose, it fails review before it is built (CLAUDE.md rules).

---

## Phase 3 — Baseline run and CANDIDATE thresholds

3.0 **Activate cost telemetry** (one registry edit, no code): add `pricing:` blocks (currency `USD`, unit `per_1m_tokens`, `input`/`output`, optional `cached_input`/`reasoning` — exact shape documented in the comment at the top of `registry/models.yaml` and validated by `ModelPricing.from_mapping` in `src/crisai/orchestration/usage_cost.py`) to every model the eval touches, using current provider price sheets. Verify: run anything (`uv run crisai ask -m "hello"`), then `uv run crisai spend --last 1` → expect a table with a Cost USD column, not the "No cost events" message. Land this via normal change control; note in the commit that prices are external facts with a date.

3.1 **Score the recorded corpus** (method A) for axes #1, #3, #7, #8-tokens, #9. Expected shape of results: routing 100% agreement on golden queries; the 14 failed runs reproduce their documented defect classes; token/latency distributions per mode emerge. **If a deterministic axis disagrees with its label → stop and investigate before proceeding**: either the scorer is wrong, the label is wrong, or behaviour changed since the run was recorded (check the run's date against `git log`).

3.2 **Run the live eval set** (method B) over the frozen sources, N ≥ 3 repetitions per query, all modes represented (single, pipeline, peer — mode-parity gaps are this repo's dominant regression pattern; an eval that only exercises pipeline mode would have missed defects fixed in commits a49593c, 0b63dbf, 841769e, and would miss the still-open TODO-057 peer-planner gap today).

3.3 **Write the baseline document**: per axis — measured value(s), data volume, git commit + registry state it was measured on, and a CANDIDATE threshold derived from the measurement (not from this skill, not from wishes). Emit it as the schema-backed report plus a human-readable summary.

**Gate to Phase 4:** the baseline report exists, is reproducible by re-running the harness command printed inside it, and every threshold in it is labelled CANDIDATE with its derivation stated.

---

## Phase 4 — Regression reporting and the CI decision gate

**Decision gate: what runs in CI?**

- **In CI unconditionally (safe now):** the deterministic axes — router golden set (already in CI via `tests/unit/test_router_regression.py`), gate-decision replay scoring, contract-shape checks, `crisai validate-artefacts` on eval artefacts. These are token-free and stable. Cost: seconds. Do it.
- **NOT in CI: live-LLM and judge axes.** CI has no provider keys for the test job, live runs cost money per push × 5 Python versions, and non-deterministic scores would make the merge gate flaky — this repo treats CI as a **hard** merge blocker (security gate precedent, PR #45 story), so a flaky gate would train people to override gates. Run these on demand and on a cadence (pre-release at minimum), env-guarded exactly like `tests/smoke`.
- **Regression report:** every eval campaign run appends/writes a schema-backed report; regression = any axis crossing its accepted threshold, or any statistically meaningful drop vs baseline on measured-only axes. The report names the commit, registry hashes, model identities, and total spend (`crisai spend` totals) of the campaign run. Prose summaries may accompany; the comparison logic reads only the contract.

**If CI wiring is proposed for a live axis anyway → branch:** require the proposer to state the per-push token cost × 5 matrix jobs and the flake-rate evidence from ≥ 10 repeated campaign runs. This has never been done as of 2026-07-02; the burden of proof is on inclusion.

---

## Phase 5 — Promotion through change control

The DoD explicitly requires process, not just numbers. Four deliverables:

1. **ADR for the baseline.** Next free ID is CRISAI-ADR-016 (`reference/decisions/` holds 001–015 as of 2026-07-02; format per its README: Status/Date/Context/Decision/Consequences/Related). The ADR records: the metric set, the harness location/methods, which thresholds were promoted CANDIDATE → accepted and on what measurement, and the rule that threshold changes require the process in item 3. Land through the normal flow → `crisai-change-control`.
2. **TODO-051 DoD checklist.** Walk the row's DoD sentence clause by clause (versioned set ✓/✗, ten axes ✓/✗ each, thresholds, regression reporting, safe source handling, approval process) and update the TODO row status only when every clause is either satisfied or explicitly re-scoped by the owner in the row text.
3. **Documented baseline-change approval process.** Who may change a threshold or replace baseline numbers, on what evidence, recorded where (the ADR's Related section + a dated entry). A threshold edit is a release-gate change — it gets the same review weight as a policy-gate code change, and no skill or automation may route around it.
4. **Safe handling of evaluation sources** (the TODO-030 interlock):
   - The existing TestNNN corpus contains real business content (UCL documents' excerpts in `final_output`, traces, and contracts) and stays where it is: gitignored, local, referenced by run-id in reports but never copied into the repo.
   - The **versioned** eval set (the DoD requirement) must be built from sanitised/synthetic sources cleared for the repo's visibility level, decoys included, so a fresh clone can run the deterministic axes. Nothing goes into it that could not be pushed to the public GitHub remote.
   - Remember TODO-030 is open: trace/log write-time redaction is incomplete, so eval campaign traces inherit the same "not safe to share" status as all other traces. Never attach raw traces to reports that leave the machine.

**Campaign success is measurable, by construction:** TODO-051's row flips from `todo` with every DoD clause evidenced; a fresh clone can run the deterministic eval axes and reproduce the committed baseline numbers; a live campaign run produces a schema-backed report with cost accounted in `crisai spend`; and the next real regression (history says it will be a mode-parity gap) is caught by a threshold, not by a user's live session.

---

## Provenance and maintenance

All volatile facts above verified 2026-07-02 on the primary workstation. Re-verify before relying:

```bash
# TODO-051 row text and status (line number may drift)
grep -n "TODO-051" reference/TODO.md
# Run corpus inventory and counts
for d in workspace/tasks/Test00* workspace/tasks/test003 workspace/tasks/NewTest*; do echo "$d: $(ls "$d"/.crisai/runs/*.json 2>/dev/null | wc -l)"; done
# Corpus is unversioned
git ls-files workspace/tasks/ ; grep -n "workspace/tasks" .gitignore
# Golden set size
grep -n "GOLDEN_CASES" tests/unit/test_router_regression.py
# Cost telemetry dormant (expect no match) and spend command exists
grep -n '^\s*pricing:' registry/models.yaml ; grep -n '@app.command("spend")' src/crisai/cli/main.py
# Gate function anchors
grep -n "_validate_evidence_bundle\|_enforce_source_inventory_fit\|_unresolved_required_read_failures" src/crisai/cli/pipelines.py
# Evidence levels enum
grep -n "search_hit_only" src/crisai/schemas/evidence_bundle_v1.schema.json
# Smoke-guard precedent for opt-in live tests
grep -n "CRISAI_RUN_SMOKE_TESTS" tests/smoke/conftest.py pyproject.toml
# No tests/eval yet; no materialised sources yet
ls tests/ ; find workspace/tasks -maxdepth 2 -name sources -type d
# Next ADR id
ls reference/decisions/ | tail -3
# Spend bounds defaults
grep -rn "CRISAI_AGENT_MAX_TURNS\|CRISAI_PEER_MAX_REFINEMENT_ROUNDS" src/crisai/cli/pipeline_display.py src/crisai/orchestration/peer_judge.py | head -5
```
