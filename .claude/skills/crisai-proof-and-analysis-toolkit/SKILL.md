---
name: crisai-proof-and-analysis-toolkit
description: First-principles proof and analysis recipes for crisAI, each with a worked example from this repo's own history. Load this when you need to PROVE a claim rather than assert it — proving a routing/vocabulary change is safe, justifying a gate or policy change, deciding whether a diagnosis really explains a failure, choosing prompt-text vs structural enforcement, proving behaviour from trace events instead of prose, auditing a pipeline change across all three run modes (single/pipeline/peer), or analysing what happens when an input file is missing or corrupt (fail-open vs fail-closed). Also load it when reviewing someone else's fix and asking "what evidence would make this claim solid?"
---

# crisAI proof and analysis toolkit

Seven reusable proof recipes, each grounded in a real episode from this
repository's history (all commits verifiable with read-only `git show`).
The house standard of evidence, distilled from the commit record:

- A claim about behaviour is proven by a **regression test, a trace event, or a
  named reproduction** — never by prose, screenshots, or "it looked right".
- A root-cause diagnosis is accepted only when **one mechanism explains every
  observation**, including the negative ones (the fixes that did NOT work).
- A behaviour that must hold is **made structurally impossible to violate**,
  not requested in a prompt.

Terminology used below (defined once): a **gate** is a deterministic policy
check that can abort a run (e.g. the evidence-bundle / source-inventory
validation in `src/crisai/cli/pipelines.py`); a **TestNNN session** is a
numbered live evaluation session whose task directory lives under
`workspace/tasks/` (Test001–Test007 plus lowercase `test003` exist on disk as
of 2026-07-02, each with run records under `.crisai/runs/*.json`); the three
**run modes** are the coroutines `run_single`, `run_pipeline`, and
`run_peer_pipeline` in `src/crisai/cli/pipelines.py`.

---

## Recipe 1 — Golden-set regression proof (routing claims)

**When to use.** Any change that could move a request to a different route:
edits to `registry/semantic_catalog.yaml` term lists, `registry/semantic_graph.yaml`
vertices/edges/priorities, or the router cascade itself. The claim to prove is
always two-sided: "the intended queries now route differently, AND nothing
else moved."

**The instrument.** `tests/unit/test_router_regression.py` — 28 parametrised
`GOLDEN_CASES` tuples `(query, expected_intent, expected_mode)` as of
2026-07-02, run against the **real** `registry/semantic_catalog.yaml` (the
deterministic graph nudge is suppressed, but task contracts still load the
real `registry/semantic_graph.yaml` via the settings fallback in
`task_contract.py:_resolve_registry_dir` — golden cases exercise catalog
terms AND graph intent emits; the test file's own docstring understates
this, see `crisai-semantic-registry-reference` §10). It also carries named
regression tests
(architecture prompts must not route to operations; crisAI-runtime troubles
still must; continuation intent; explicit pipeline-mode override).

**Steps.**
1. Before changing anything, write the new expected `(query, intent, mode)`
   rows for the behaviour you intend — predictions first, edits second.
2. Make the registry/router edit.
3. Run the golden set (path FIRST, flags after — see the warning below):
   `uv run pytest tests/unit/test_router_regression.py --no-cov`
4. Read the result as a two-part proof:
   - your new cases pass → the intended change happened;
   - the pre-existing 28 cases still pass **unmodified** → nothing else moved.
   Editing an existing golden case to make your change pass is not a proof;
   it is a documented behaviour change and must be argued in the commit body.
5. Append your new queries to `GOLDEN_CASES` so the proof is permanent (the
   file's own docstring instructs exactly this).

**Worked example.** Commit `216ca3d` (ADR-014, PR #23) rewrote two whole term
families (`operations_terms` from generic debugging nouns to crisAI-runtime
phrases; `discovery_terms` stripped of bare object-type nouns). The commit
body states the proof verbatim: *"The router golden set is unchanged and
passes; added regression tests proving architecture prompts no longer route to
operations and genuine crisAI-runtime prompts still do."* That is the pattern:
golden set unchanged = no collateral movement; new named tests = the intended
delta. The suite itself was created by `fec2cb5` (2026-05-11, 27 cases
"covering every routing path … so a catalog edit immediately surfaces routing
regressions in CI").

**Pitfalls.**
- Route-hint thresholds (≥2 matches etc.) are hardcoded in Python
  (`src/crisai/orchestration/request_contract.py`), not in the registry — a
  "registry-only" tuning claim must check whether the knob is actually there
  (see crisai-semantic-registry-reference).
- Running a test subset trips the 70% coverage gate
  (`pyproject.toml` `[tool.coverage.report] fail_under = 70`); use `--no-cov`
  for a subset run.
- **Always put the test path before any flags.** Every MCP server module
  treats `sys.argv[1]` as a workspace root at import time
  (`src/crisai/servers/sharepoint_server.py:29-34`); `pytest --no-cov tests/…`
  can create a junk `--no-cov/.auth/` directory at the repo root. Full test
  mechanics belong to crisai-validation-and-qa.

---

## Recipe 2 — Named-reproduction discipline (gate and policy changes)

**When to use.** Any change to a gate, policy check, retry, or fallback. The
rule as practised in this repo: **a gate change is justified by a numbered,
reproduced failure — never by a hypothetical.** Every gate-adjacent commit in
the ADR-015 era opens with its reproduction by name.

**Steps.**
1. Reproduce the failure in a live session and give it a number
   (`TestNNN`); the task directory under `workspace/tasks/TestNNN/` with its
   run records (`.crisai/runs/*.json`) becomes the durable evidence.
2. State the reproduction in the commit body's first paragraph: session name,
   the exact user ask, the observed failure, and the run-level mechanics
   (which gate fired, on what evidence).
3. Derive the root cause from the persisted session state, not from memory —
   `0cdd086`'s body says "reproduced deterministically from the persisted
   session".
4. Fix, then add a regression test that encodes the reproduction (not just
   the fix's mechanism).
5. Close the body with the suite ledger line: `Full suite green (N passed;
   ruff + mypy clean)` — N is monotonically tracked across commits
   (821 → 831 → 834 → 835 → 854 → 860 → 862 → 863 across the June-14 arc).

**Worked examples — the full TestNNN → commit map (all verified 2026-07-02):**

| Session | Commit (PR) | What the reproduction proved |
|---|---|---|
| Test001 | `0cdd086` (#26) | GUID-duplicate candidates starved anchor-resolution slots; "It was never a score problem and never really the lock file" |
| Test001 + test003 | `2455c1c` (#28) | `~$`/`.~lock.` Office stubs impersonate real documents in OneDrive search |
| test003 defect A | `a49593c` (#29) | source-inventory fit gate lived only in `run_single`; pipeline route bypassed it. Body: "Reproduced: running the existing gate on test003's actual output does raise a violation listing exactly those rows" |
| test003 defect B | `9c9ee2e` (#30) | see Recipe 4 |
| Test004 | `0b63dbf` (#39) | reasoning model committed an empty final message (449 output tokens, output_length 0); peer path treated it as fatal |
| Test005 | `b386a17` (#42) | OneDrive/Graph search is word-order sensitive; reformulated query returned wrong files. Body: "A live check confirmed the cause" — the discriminating experiment is named |
| Test006 | `2f41bec` (#43) | an output path ("save under workspace/…") was scraped into an input source-scope requirement |
| Test007 | `841769e` (#44) | see Recipe 5 |

Find them all with: `git log --oneline -i --grep='Test00'` and
`git log --oneline --grep='test003'`.

**Pitfall.** A gate that fails hard stays hard unless the owner decides
otherwise: `b386a17` records "Per the user's call, the inventory gate keeps
its hard failure" — do not soften a gate as a side effect of fixing its false
positives.

---

## Recipe 3 — One-mechanism-explains-all-observations (root-cause acceptance)

**When to use.** Before accepting any diagnosis — yours or someone else's.
The test: does one mechanism explain **every** observation, including why the
previous fixes failed? A mechanism that explains only the positive
observations is a partial theory, and partial theories generate dead-end
fixes.

**Steps.**
1. List ALL observations: the original symptom, every failed fix attempt and
   its exact failure, and every eliminated hypothesis (with the evidence that
   eliminated it).
2. For each candidate mechanism, check it against the full list. Reject any
   mechanism that leaves an observation unexplained.
3. Actively eliminate the "obvious" alternatives with a discriminating
   experiment before escalating complexity.
4. Consider mechanisms **outside your code**: platform configuration,
   external-service behaviour, tenant settings.
5. Record the accepted mechanism where the next person will find it — in this
   repo that is the fix/revert commit body.

**Worked example — the AADSTS7000218 saga (all commits 2026-05-03).**
Azure AD rejected the device-code token exchange with AADSTS7000218 ("must
contain client_assertion or client_secret"). Three escalating, increasingly
RFC-literate code fixes each explained only part of the evidence:

1. `2fbd2e8` — "the server wants a secret, so use ConfidentialClientApplication
   when MS_CLIENT_SECRET is set." Failed: MSAL 1.36.0's
   ConfidentialClientApplication has no `initiate_device_flow` (AttributeError).
2. `5c5ec96` — raw-requests device flow, secret included in token polling.
   Still AADSTS7000218.
3. `c11eb8f` — per RFC 8628 §3.1, secret included in BOTH the `/devicecode`
   initiation POST and the `/token` polling POST. **Still failed** — the
   fully-compliant request was rejected too.

In parallel, `18e36d0`/`88d299f` (add then remove diagnostic prints) ran the
eliminating experiment: MS_CLIENT_SECRET **was** reaching the MCP subprocess,
killing the "env var not propagated" hypothesis.

The accepted mechanism (`da4f4bd`, the revert): *"Device code flow for
confidential clients (AADSTS7000218) is not supported by Azure AD in this
tenant configuration regardless of whether client_secret is included in the
request."* This single mechanism explains everything — why each code fix
failed, why the RFC-perfect request with the secret in both calls still
failed, and why no code change could ever work. The real fix was a portal
checkbox: enable "Allow public client flows" on the app registration.
`_build_app` in `src/crisai/ms_graph.py:117` still returns only
`PublicClientApplication` today.

**Second, in-repo example.** Test001 (`0cdd086`, ADR-015): the visible
culprit was a `~$` Office lock file failing to read. The accepted mechanism
was one level deeper — GUID-duplicate candidates of the *other* deck starved
the anchor-resolution slots, so the wanted source fell through to a live
search that matched the stub. The body's acceptance sentence is the recipe in
miniature: "It was never a score problem and never really the lock file."
Both the lock-file filter (`2455c1c`) and the dedup fix (`0cdd086`) were
needed, but only the starvation mechanism explained why turn 1 succeeded and
turn 2 failed on the same corpus. The full incident chronicle lives in
crisai-failure-archaeology; the method lives here.

---

## Recipe 4 — Structural-vs-prompt enforcement analysis

**When to use.** Whenever a behaviour MUST hold ("the planner must not
retrieve", "the agent must not write outside the workspace"). Ask: is the
constraint enforced by structure (the forbidden action is impossible) or by
prompt text (the model is asked nicely)? In this repo, prompt text is
**documented as insufficient** — a model has ignored an explicit prohibition
in a live session.

**The doctrine's origin — commit `9c9ee2e` (test003 defect B, PR #30).**
The pipeline retrieval planner's contract is framing-only, and its runtime
prompt literally said "Do not retrieve or read source documents in this
stage." The planner nevertheless had the same source-search MCP servers as
context_retrieval, and *"the model ignored the instruction: in test003 it ran
its own OneDrive search and returned a separate, wrong file list."* The fix
removed the capability instead of repeating the instruction: the planner
stage runs on a spec copy with the source-search servers stripped
(`_framing_only_planner_spec`, `src/crisai/cli/pipelines.py:623`, denying
`_PLANNER_FRAMING_DENIED_SERVERS = {"sharepoint_docs", "documents", "intranet"}`
at line 620). The commit body names the principle: *"A framing-only planner
with no retrieval tools cannot run a competing search."*

**Steps.**
1. Write the invariant as a sentence: "X must never happen in stage Y."
2. Enumerate what makes X *possible*: attached MCP servers, tools in
   `tools.allow`, writable paths, reachable endpoints.
3. Prefer, in order: remove the tool/server from the stage spec → move the
   tool to `tools.internal` (agent-invisible, deterministic-orchestration
   only) → add a deterministic gate that fails the run → registry vocabulary
   change. Prompt text is documentation of intent, never the enforcement.
4. Prove the structure with a test that asserts the *capability* is absent
   (9c9ee2e's tests assert source servers removed, framing servers kept,
   original spec untouched) — not a test that the model "behaves".
5. Audit mode parity (Recipe 6): the same commit body scoped itself honestly
   — "Scope: pipeline path (run_pipeline) … applying the same restriction
   [to peer] is a follow-up." That follow-up is still open as of 2026-07-02
   (TODO-057, `reference/TODO.md:117`): `run_peer_pipeline` still runs the
   planner with the raw spec (`spec=specs["retrieval_planner"]`,
   `src/crisai/cli/pipelines.py:1677`).

**Other structural enforcements in the same spirit** (own the pattern, not
the inventory — details in crisai-architecture-contract): the `allow` vs
`internal` tool split with `allow ∩ internal` a validation error; the
destination-scope exclusion in `2f41bec` (the gate *cannot* mistake an output
path for an input scope because the structured `output_path` is threaded into
constraint inference, rather than the prompt being told to be careful).

---

## Recipe 5 — Trace-based proof (assert on events, not prose)

**When to use.** Proving that something *happened* (or did not) during a run:
a source was materialised, a fallback fired, a checkpoint was requested. The
final answer's prose can look perfect while the mechanism you shipped never
executed — only the event stream can tell them apart.

**Worked example — Test007 and commit `841769e` (#44).** ADR-015 slice 3b had
wired source materialisation into `run_pipeline` only. Test007 ran the main
knowledge-authoring path (peer mode), *"read its source live and authored a
strong artefact"* — a run that eyeballing would score as a success (the run
record exists: `workspace/tasks/Test007/.crisai/runs/`, one completed peer run
with 495 events as of 2026-07-02). The proof of the hole was an **event
count**: *"zero SOURCE_MATERIALISED events fired and no cache was written."*
Prose said success; the event count said the new subsystem never ran in the
mode that mattered. The fix wired `_materialise_confirmed_sources` into
`run_peer_pipeline`, and the regression test asserts the materialiser is
invoked on the peer path (`tests/cli/test_pipelines.py::test_run_peer_pipeline_materialises_confirmed_sources`).

**Where events live (as of 2026-07-02).** Two distinct streams — assert
against the right one:

| Stream | Location | Carries |
|---|---|---|
| Agent trace (JSONL, one event per line) | `logs/agent_trace.jsonl` (`settings.log_dir` / `tracing.py:TRACE_FILE_NAME`) | workflow/stage events AND `source_signal` events: stages `SOURCE_MATERIALISED`, `SOURCE_CACHE_HIT`, `SOURCE_MATERIALISE_SKIPPED`, `SOURCE_MATERIALISE_ERROR` (emitted at `src/crisai/cli/pipelines.py:284-313`), keyed by `run_id` |
| Run record (JSON per run) | `workspace/tasks/<task>/.crisai/runs/<run_id>.json` | `schema_version, run_id, session, status, decision, expected_stages, events, final_output, error, metadata`; event types observed (full set, 2026-07-02): `run_created`, `routing_decision`, `task_contract`, `stage_started`, `stage_delta`, `stage_output`, `stage_skipped`, `stage_failed`, `checkpoint_requested`, `checkpoint_decision`, `final_answer`, `run_completed`, `run_failed` |

Verified 2026-07-02: **no** run record on disk contains `source_signal`
events — source-materialisation proofs must query `agent_trace.jsonl`, not
the run JSONs. (The local `agent_trace.jsonl` spans 2026-05-22 → 2026-06-19
and DOES contain the Test007 peer run's events — 40 events keyed by the run
record's `metadata.trace_run_id`, which differs from the run record's own
`run_id`. Its zero `source_signal` count is expected: the run happened
BEFORE `841769e` wired materialisation into the peer path — it is the very
hole that commit fixed. Materialisation is also opt-in via
`CRISAI_MATERIALISE_SOURCES` — a zero count with the flag off proves
nothing.)

**Copy-pasteable event-count proofs:**

```bash
# Did materialisation fire at all? (0 with flag ON in the exercised mode = a hole)
grep -c '"stage": "SOURCE_MATERIALISED"' logs/agent_trace.jsonl

# Per-run breakdown of all source signals
grep '"event_type": "source_signal"' logs/agent_trace.jsonl \
  | python3 -c 'import sys,json,collections; c=collections.Counter((e["run_id"],e["stage"]) for e in map(json.loads,sys.stdin)); [print(k,v) for k,v in c.items()]'

# Did the planner fallback fire in a given run?
grep 'RETRIEVAL_PLANNER FALLBACK' logs/agent_trace.jsonl

# What did a run actually do, from its run record?
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["status"], d["decision"]["mode"]); [print(e["event_type"], e.get("stage")) for e in d["events"]]' workspace/tasks/Test007/.crisai/runs/<run_id>.json
```

**Steps.**
1. Before shipping a mechanism, decide which event proves it ran and make
   sure the code emits it (`_trace_workflow_policy_event` /
   `workflow.trace_event`).
2. After a live run, count that event for the run_id. Zero when you expected
   nonzero is a finding, even if the output looks fine.
3. Encode the proof as a regression test asserting the event/call, the way
   `0b63dbf`'s test asserts `RETRIEVAL_PLANNER FALLBACK` is traced.
4. Never accept "the answer mentions the cached copy" as evidence — prose
   parsing of machine-critical state is banned by this repo's contract rules.

Deeper trace anatomy, redaction caveats, and summarising tooling belong to
crisai-diagnostics-and-tooling.

---

## Recipe 6 — Mode-parity audit (any pipeline-path change)

**When to use.** Every change touching run behaviour. Mode-parity gaps are
the **dominant regression pattern in this repo**: a fix lands on one mode and
the same defect resurfaces on another. Three shipped instances: the
source-inventory gate lived only in `run_single` (`a49593c` #29); the
empty-planner fallback lived only in `run_pipeline` (`0b63dbf` #39);
materialisation was wired into `run_pipeline` only (`841769e` #44). One
instance is still open: the framing-only planner blinding (TODO-057, above).

**The audit, mechanically (as of 2026-07-02 the three coroutines start at
lines 849 / 1082 / 1543 of `src/crisai/cli/pipelines.py`):**

```bash
# 1. Locate the three mode boundaries
grep -n 'async def run_single\|async def run_pipeline\|async def run_peer_pipeline' src/crisai/cli/pipelines.py

# 2. Find every call site of the helper/gate/feature you changed
grep -n '_materialise_confirmed_sources\|_build_retrieval_planner_fallback\|_enforce_source_inventory_fit\|_framing_only_planner_spec' src/crisai/cli/pipelines.py

# 3. Bucket each call-site line number into the function ranges from step 1
#    (as of 2026-07-02: run_single 849–1081, run_pipeline 1082–1542,
#     run_peer_pipeline 1543–~2302; build_peer_run_result follows at 2303)

# 4. Confirm mode dispatch — all three entry points are re-exported and called
#    from src/crisai/cli/main.py (lines 109-111 bind them; ~705/718/731 dispatch)
grep -n 'run_peer_pipeline\|run_pipeline\|run_single' src/crisai/cli/main.py
```

**Steps.**
1. Run the grep pair above for the symbol you are adding or changing.
2. For each of the three modes, write one line: "covered at line L" /
   "intentionally excluded because …" / "GAP". An intentional exclusion must
   be argued in the commit body (`a49593c` did: "run_peer is unaffected
   because inventory asks never route to peer"; `9c9ee2e` did: "peer is not a
   source-inventory path" — and that argument later proved too optimistic for
   the planner case, hence TODO-057).
3. If a mode is a GAP, either cover it in the same change or open a TODO with
   the reproduction that would prove it (Recipe 2).
4. Add a per-mode regression test for the covered behaviour — `841769e`'s
   test exists precisely because the pipeline-mode test could not catch the
   peer-mode hole.

**Reference parity table as of 2026-07-02** (call-site lines in
`src/crisai/cli/pipelines.py`):

| Helper | run_single | run_pipeline | run_peer_pipeline |
|---|---|---|---|
| `_framing_only_planner_spec` | n/a (single retrieves directly, by design) | 1207 | **GAP — TODO-057 (P1, open)** |
| `_build_retrieval_planner_fallback` | n/a | 1222 | 1696 |
| `_enforce_source_inventory_fit` | inline gate in run_single | 1500 | argued-out (inventory never routes to peer) |
| `_materialise_confirmed_sources` | n/a | 1373 | 1778 |

---

## Recipe 7 — Fail-open vs fail-closed analysis (missing/corrupt inputs)

**When to use.** Any code that loads a file, config, cache, or external
resource. Ask, for every input: **"what happens when this is missing or
corrupt?"** — and verify the answer is a *decision*, not an accident. Both
behaviours are legitimate; undocumented asymmetry is the trap.

**Worked example — the two semantic registries load with opposite policies
(verified in code, 2026-07-02):**

| | `semantic_catalog.yaml` | `semantic_graph.yaml` |
|---|---|---|
| Loader | `load_semantic_catalog` (`src/crisai/orchestration/semantic_catalog.py:591`) | `load_retrieval_association_graph` (`src/crisai/orchestration/retrieval_association_graph.py:148`) |
| Missing file | **fail-closed**: raises `FileNotFoundError` (line 611) — the run dies | **fail-open**: log warning, return `None` (lines 156-157) |
| Corrupt/invalid YAML | raises `SemanticCatalogError` | log warning, return `None` (161-165, 180-181, 218-219) |
| Silent degradation | none — you cannot run without it | routing quietly degrades: every task contract falls back to `primary_intent="respond"` / `deliverable_type="general_answer"` (`task_contract.py:77-78`), `suggested_sources` defaults to `{"generic_retrieval"}` (`retrieval_association_graph.py:261`) |
| Caching | `@functools.lru_cache(maxsize=8)` — edits need a process restart | re-read from disk on every message — edits take effect live |
| Observability of the failure | immediate and loud | a warning log line plus `graph_loaded: false` in the deterministic-context trace metadata (`retrieval_association_graph.py:300-310`). `graph_version` alone is NOT reliable: it is `"unavailable"` only when the file is missing and `"unreadable"` only on OSError — corrupt/invalid YAML that reads fine still gets a healthy-looking 12-char sha1 (`retrieval_association_graph.py:322-332`) |

The consequence: a broken `semantic_graph.yaml` does not stop anything — runs
continue with silently degraded routing, and the reliable tell in every
failure mode is `graph_loaded: false` in the deterministic-context trace
metadata (emitted in all three modes), plus the log warning; do not trust
`graph_version` — after a bad YAML edit it still shows a normal sha1.
`uv run crisai doctor` distinguishes
missing vs invalid graph explicitly (`src/crisai/registry_validation.py`), so
the analysis step "run doctor after registry edits" is the fail-open
mitigation.

**Steps.**
1. For the input you touch, find the loader and classify: what does it do on
   missing / unparseable / structurally-wrong / empty?
2. If fail-open: enumerate the degraded behaviour precisely (what defaults
   kick in?) and verify there is a detectable signal (log line, sentinel
   value in traces, doctor check). If there is no signal, add one — silent
   fail-open is the bug class.
3. If fail-closed: verify the error message tells the operator what to fix,
   and that it fails at the earliest sensible moment (the catalog fails at
   first load, not mid-run).
4. Check both caching and failure policy together: fail-open + cached would
   mean a corrupt file poisons everything until restart; fail-open +
   re-read-per-message (the graph's actual combination) self-heals on the
   next successful parse.
5. State the chosen policy in the code's docstring or the commit body so it
   reads as intent, not accident.

**Deliberate fail-open elsewhere, for contrast:** source materialisation is
best-effort by explicit design — "failures are traced and never abort the
run" (`_materialise_confirmed_sources` docstring, `pipelines.py:245-249`;
every exception is caught and traced as `SOURCE_MATERIALISE_ERROR`). The
evidence gates are deliberately fail-closed — "a wildly wrong search should
fail loudly, not present wrong files" (`b386a17`). Same codebase, opposite
policies, each argued where it lives. That is the standard.

---

## When NOT to use this skill

- **You want the incident history itself** (what happened, when, with which
  commits, current status) → **crisai-failure-archaeology**. This skill owns
  the *methods*; that one owns the chronicle.
- **You are triaging a live failure right now** (symptom → next diagnostic
  step) → **crisai-debugging-playbook**.
- **You need exact test commands, markers, coverage-gate mechanics, or the
  conftest/smoke-test traps** → **crisai-validation-and-qa**.
- **You need trace/log anatomy, spend measurement, or diagnostic scripts** →
  **crisai-diagnostics-and-tooling**.
- **You are taking a hunch through the idea lifecycle to an accepted result**
  (evidence bar, experiment flags, default-flips) →
  **crisai-research-methodology** (it builds on these recipes but owns the
  lifecycle).
- **You are executing the TODO-051 eval-baseline campaign** →
  **crisai-eval-baseline-campaign**.
- **You need catalog/graph schema detail or how to add an intent** →
  **crisai-semantic-registry-reference**.

---

## Provenance and maintenance

All claims verified against the working tree and git history on 2026-07-02.
Line numbers drift; re-verify before quoting them.

```bash
# Recipe 1 — golden set still exists, count the cases
python3 -c "import ast; t=ast.parse(open('tests/unit/test_router_regression.py').read()); print([len(n.value.elts) for n in ast.walk(t) if isinstance(n,ast.AnnAssign) and getattr(n.target,'id','')=='GOLDEN_CASES'])"

# Recipe 2 — the TestNNN commit map
git log --oneline -i --grep='Test00'
ls workspace/tasks/ | grep -i '^test'

# Recipe 3 — the auth-saga commits and the revert body
git show --no-patch --format='%h %s' 2fbd2e8 5c5ec96 c11eb8f da4f4bd
grep -n 'def _build_app' src/crisai/ms_graph.py

# Recipe 4 — structural planner blinding and its open peer gap
grep -n '_PLANNER_FRAMING_DENIED_SERVERS\|_framing_only_planner_spec' src/crisai/cli/pipelines.py
grep -n 'TODO-057' reference/TODO.md

# Recipe 5 — source-signal event emission and trace file name
grep -n 'SOURCE_MATERIALISED\|source_signal' src/crisai/cli/pipelines.py
grep -n 'TRACE_FILE_NAME' src/crisai/tracing.py

# Recipe 6 — mode boundaries and helper call sites
grep -n 'async def run_single\|async def run_pipeline\|async def run_peer_pipeline' src/crisai/cli/pipelines.py
grep -n '_materialise_confirmed_sources\|_build_retrieval_planner_fallback\|_enforce_source_inventory_fit\|_framing_only_planner_spec' src/crisai/cli/pipelines.py

# Recipe 7 — loader failure policies and caching
grep -n 'lru_cache\|FileNotFoundError\|SemanticCatalogError' src/crisai/orchestration/semantic_catalog.py
grep -n 'return None\|_log.warning\|graph_version' src/crisai/orchestration/retrieval_association_graph.py

# Coverage gate and pytest addopts (Recipe 1/2 pitfalls)
grep -n 'fail_under\|addopts' pyproject.toml
```
