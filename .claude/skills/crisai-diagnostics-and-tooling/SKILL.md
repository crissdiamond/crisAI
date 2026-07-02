---
name: crisai-diagnostics-and-tooling
description: Measure crisAI behaviour instead of eyeballing it — load when you need to read or interpret logs/agent_trace.jsonl, per-task run history JSONs under workspace/tasks/<session>/.crisai/runs/, per-MCP server logs, token/cost figures (crisai spend), doctor output, or graph_version; when diagnosing what a run actually did (routing decision, contracts, stage outputs, gates, checkpoints, spend); when cleaning up stray "--no-cov"/"-q"/"--collect-only" directories at the repo root; or when checking pipeline-vs-peer mode parity before or after a change.
---

# crisAI diagnostics and tooling

Rule of the house: **measure, don't eyeball**. Every run leaves a machine-readable
record; a claim about what an agent, gate, or router "did" is only evidence when it
points at a trace event, a run snapshot, or a doctor/spend output. This skill maps
every diagnostic surface, teaches you to read a run end-to-end, and ships three
scripts under `scripts/` in this skill directory.

All paths below assume default settings (`CRISAI_LOG_DIR` → `<repo>/logs`,
`CRISAI_WORKSPACE_DIR` → `<repo>/workspace`); overrides move the whole directory.

## 1. Map of diagnostic surfaces

| Surface | Path | Format | Written by |
|---|---|---|---|
| Agent trace (the primary record) | `logs/agent_trace.jsonl` | JSONL, one event per line | `src/crisai/tracing.py` (`append_trace`/`write_trace_event`), driven by `src/crisai/cli/pipeline_engine.py` and `cli/pipelines.py` |
| Application log | `logs/crisai.log` | JSON lines, ECS-style fields (`timestamp`, `log.level`, `log.logger`, `message`, `service`) | `src/crisai/logging_utils.py` (`JsonFormatter`) |
| Per-MCP-server logs (the tool-side record) | `logs/<server>_mcp.log` — `sharepoint_mcp.log`, `workspace_mcp.log`, `diagram_mcp.log`, `document_mcp.log`, `document_export_mcp.log`, `intranet_mcp.log`, `session_memory_mcp.log`, `vision_mcp.log` | Same JSON-line format; one line per tool call/notable action | Each `src/crisai/servers/*_server.py` via `logging_utils.append_json_log_line` / `configure_mcp_framework_logging` |
| Web run snapshots (per run, per task) | `workspace/tasks/<session>/.crisai/runs/<run_id>.json` | Single JSON document, schema `ui_run_state_v1` | `src/crisai/apps/run_history.py` — **web API runs only**; CLI (`crisai ask`) runs exist only in the agent trace |
| Task session state | `workspace/tasks/<session>/.crisai/{task,history,memory,anchors}.json` | JSON | `src/crisai/cli/session_store.py` |
| Materialised source cache | `workspace/tasks/<session>/sources/<source-id>/<revision>/` (raw bytes + `extracted.json` + `meta.json`) | Files + JSON sidecars | `src/crisai/workspace/source_cache.py` via `_materialise_confirmed_sources` (`cli/pipelines.py:235`); only when `CRISAI_MATERIALISE_SOURCES` is truthy. As of 2026-07-02 no `sources/` dir exists on disk here yet. Note the module docstring still says `.crisai/sources/` — stale; the call site passes the visible task root deliberately (agents cannot read `.crisai/`). |
| Cost/usage | embedded in agent-trace `metadata.observability`; queried with `crisai spend` | — | `cli/pipeline_engine.py` + `orchestration/usage_cost.py` |

There is no separate tool-trace file. `registry/policies.yaml` declares
`tracing: {write_agent_trace: true, write_tool_trace: true, redact_secrets: true}`,
but as of 2026-07-02 **no Python module reads `registry/policies.yaml` at all**
(`grep -rn "policies" src/crisai/ --include='*.py'` returns nothing). Those flags are
declarative intent, not behaviour. Tool-side visibility comes from the per-MCP logs.

### Redaction warning (TODO-030, P0, open as of 2026-07-02)

Traces and logs **intentionally contain full agent stage content and source
excerpts** — business content included. The only implemented write-time redaction is
in `src/crisai/tracing.py`: `read_handle` keys are dropped from payloads and
`sharepoint_doc:...` tokens are masked in text. There is no general secret/business
redaction despite `redact_secrets: true` in policies.yaml. **Never describe or treat
these logs as safe to share**; scrub before attaching anything to an issue or PR.

## 2. Agent trace anatomy (`logs/agent_trace.jsonl`)

Every event is one JSON object:

```json
{"timestamp": "…+00:00",
 "service": {"name": "crisai", "component": "agent_trace"},
 "event_type": "stage_output",
 "stage": "CONTEXT RETRIEVAL OUTPUT",
 "content": "…full stage text…",
 "run_id": "f6a0eed83f564bb0a0ec83e17278fbc6",
 "agent_id": "context_retrieval",
 "metadata": { "observability": { … } }}
```

`run_id` correlates all events of one workflow execution. Event types observed in the
live trace and defined in code:

| event_type | Meaning | Where emitted |
|---|---|---|
| `workflow_event` | run lifecycle (`WORKFLOW_START` with `metadata.mode`, `WORKFLOW_END`) | `cli/pipelines.py` |
| `workflow_input` | the composed user/system input (`USER INPUT`) | `cli/pipelines.py` |
| `policy_signal` | machine-critical contract snapshots: stages `TASK_CONTRACT`, `REQUEST_CONTRACT`, `WORKSPACE_WRITE_AUTHORIZATION`, `DETERMINISTIC_RETRIEVAL_CONTEXT`, `PEER_RUN_CONTRACT` | `cli/pipelines.py` |
| `stage_start` / `stage_end` | stage brackets (`<LABEL>_START` / `<LABEL>_END`), no metrics | `pipeline_engine.run_stage` |
| `stage_output` | the stage's final text + **`metadata.observability`** (tokens, timing, model, cost) | `pipeline_engine.run_stage:256` |
| `stage_error` | timeout / exception / empty output, with observability | `pipeline_engine.run_stage` |
| `stage_skipped` | skipped stage with reason | `pipeline_engine.trace_stage_skip` |
| `checkpoint` / `checkpoint_decision` | retrieval checkpoint request and human decision (`continue`/`redirect`/`stop`) | `cli/pipelines.py` |
| `policy_violation` | a gate firing (evidence validation, source-fit, write policy…) | `cli/pipelines.py` (8 call sites) |
| `workflow_output` | `FINAL_OUTPUT` with observability for the final stage | `cli/pipelines.py` |
| `peer_timeline` | peer-mode round/escalation timeline | `cli/pipelines.py` |
| `source_signal` | materialisation events `SOURCE_MATERIALISED`, `SOURCE_CACHE_HIT`, `SOURCE_MATERIALISE_ERROR` | `cli/pipelines.py:_materialise_confirmed_sources` |

Stage labels follow the pattern `<AGENT> OUTPUT` plus `_START`/`_END`/`_ERROR`
suffixes (e.g. `RETRIEVAL_PLANNER OUTPUT`, `CONTEXT RETRIEVAL REPAIR OUTPUT` for the
one-shot evidence repair retry, `EVIDENCE_CONTRACT_REPAIR`, `RETRIEVAL_CHECKPOINT`).

### The observability block (schema `ui_stage_observability_v1`)

Attached to `stage_output`/`workflow_output`/`stage_error` metadata by
`_merge_stage_observability_metadata` (`cli/pipeline_engine.py:342`):

```json
"observability": {
  "schema_version": "ui_stage_observability_v1",
  "provider_usage": {"requests": 5, "input_tokens": 43367, "output_tokens": 1776,
                      "total_tokens": 45143, "cached_tokens": 25600},
  "execution_time": {"started_at": "…", "ended_at": "…", "duration_ms": 25610},
  "model": {"schema_version": "model_observability_v1", "provider": "openai",
             "model_name": "gpt-5.4-mini", "source": "model_ref:openai_fast",
             "model_ref": "openai_fast"},
  "cost": { "schema_version": "usage_cost_v1", "total_cost_usd": … }
}
```

Interpretation caveats (both verified against the live trace):

- **`cost` appears only when the model's registry entry has a `pricing` block**
  (`registry/models.yaml`). As of 2026-07-02 no model has pricing configured, so the
  live trace has zero cost events and `crisai spend` reports none. Token counts are
  still present regardless.
- **LiteLLM-backed stages (gemini/anthropic/deepseek/local providers) may report no
  `provider_usage` tokens** — in the live trace, `context_synthesizer`
  (deepseek) and `review` (gemini) stages show timing and model identity but empty
  token counts. Do not read a missing count as zero spend.
- `streaming` sub-block records streaming fallback (`attempted`, `fallback`,
  `fallback_reason`).

## 3. Web run snapshots (`workspace/tasks/<session>/.crisai/runs/<run_id>.json`)

Schema `ui_run_state_v1`, persisted by `apps/run_history.py`. Top-level keys:
`schema_version, run_id, session, status (completed|failed), decision,
expected_stages, events, final_output, error, metadata`.

- `decision` is the full routing decision: `intent, mode, agent, needs_retrieval,
  needs_review, confidence, reason`.
- `metadata` holds `snapshot_schema_version (crisai_run_snapshot_v1), created_at,
  updated_at, completed_at, message_summary, trace_run_id, request_contract`
  (the complete `request_contract_v1` JSON).
- `events` is a list of `ui_event_v1` objects (`run_created, routing_decision,
  task_contract, stage_started, stage_delta, stage_output, checkpoint_requested,
  checkpoint_decision, run_failed, …`). `stage_output` events carry the same
  `observability` block as the agent trace.

**Three traps** (all verified):

1. **The snapshot `run_id` is NOT the trace `run_id`.** Use
   `metadata.trace_run_id` to find the run in `logs/agent_trace.jsonl`.
2. **Events are truncated**: the persisted list keeps only the FIRST 500 events
   (`MAX_EVENTS_PER_RUN`, `apps/run_history.py:16,161`) and `stage_delta` streaming
   spam consumes that budget fast — a real Test003 run's snapshot retains only 2 of
   6 stage outputs. Event `content` is capped at 20 000 chars, `final_output` at
   120 000. Top-level `status`, `error`, `final_output` remain authoritative; for
   the full stage record follow `trace_run_id` into the agent trace.
3. **Only web-API runs get snapshots.** `crisai ask` runs appear solely in
   `logs/agent_trace.jsonl` (plus session history/memory files).

`workspace/tasks/` currently holds a de facto regression corpus: `Test001`–`Test007`,
lowercase `test003`, `NewTest-02..05`, `NewTests-01` (all with real run snapshots,
including gate-failure runs) alongside real work tasks. As of 2026-07-02 all seven
`TestNNN` dirs exist on disk.

## 4. Reading a run end-to-end (the recipe)

Given "what happened in run X?", walk the record in this order — each step is a
concrete grep against one of the two entry points:

1. **Routing decision** — snapshot `decision` / trace `WORKFLOW_START` metadata
   (`mode`) — did it go single/pipeline/peer, which intent, what confidence?
2. **Contracts** — `policy_signal` events `REQUEST_CONTRACT` and `TASK_CONTRACT`:
   `source_required`, `required_evidence_level`, `output_path`, quality gates. This
   is what the gates will later enforce; most "why did the gate fire?" questions are
   answered here.
3. **Deterministic retrieval context** — `DETERMINISTIC_RETRIEVAL_CONTEXT`
   policy_signal: `graph_loaded`, `graph_version`, activated topics (see §7).
4. **Stage outputs** — `stage_output` events in order; check for
   `CONTEXT RETRIEVAL REPAIR OUTPUT` (evidence contract failed once and was
   repaired) and `RETRIEVAL_PLANNER FALLBACK` content (empty planner output,
   deterministic handoff substituted).
5. **Checkpoints** — `checkpoint` / `checkpoint_decision` (`continue` / `redirect`
   with instruction / `stop`).
6. **Gates** — `policy_violation` events and the snapshot's top-level `error`.
   Real gate strings you will see: "Policy gate failed: required source read failed
   and was not recovered by matching content-read evidence…", "…requires
   content-read evidence, but no source in the evidence bundle…", "…requires
   artefact creation/update, but no file changes were detected…", "Task artefact
   conformance failed…".
7. **Spend** — per-stage `observability.provider_usage` (or `crisai spend` once
   pricing is configured).

Or run the shipped summariser (§8), which prints exactly this.

## 5. `crisai spend`

```
uv run crisai spend                 # latest run
uv run crisai spend --last 5        # five most recent runs
uv run crisai spend --run f6a0eed8  # run_id prefix match
```

Implementation: `cli/main.py:540-675`. It reads `settings.log_dir/agent_trace.jsonl`
(no other source), keeps only events whose
`metadata.observability.cost.schema_version == "usage_cost_v1"`, groups by trace
`run_id`, and renders a Rich table with columns
`Run | Stage | Agent | Provider | Model | In | Out | Cost USD` plus a per-run Total
row. Malformed JSONL lines produce warnings, not failures.

Real output on this machine (2026-07-02) — because `registry/models.yaml` has no
`pricing` blocks, there are no cost events:

```
╭──────────────── ◇ crisai spend ────────────────╮
│ No cost events found for any run.              │
│ Cost tracking requires model pricing           │
│ configured in registry/models.yaml.            │
╰────────────────────────────────────────────────╯
```

To activate cost telemetry add per-model pricing to `registry/models.yaml`
(`pricing: {currency: USD, unit: per_1m_tokens, input: …, output: …}`; optional
`cached_input`, `reasoning`). Only USD and per-1M-token units are accepted
(`orchestration/usage_cost.py:10,33-36`); invalid pricing is logged and ignored, so
a typo silently disables cost rather than failing the run. Until then, use the
summariser script for raw token counts, which need no pricing.

## 6. `crisai doctor`

```
uv run crisai doctor            # registry + env + hygiene validation
uv run crisai doctor --models   # additionally dry-build every agent's model
```

`--models` is the only flag (`cli/main.py:491`). Exit code 0 when there are no
errors (warnings alone still exit 0 with a ✅ panel); exit 1 on any error. CI runs
plain `uv run crisai doctor` as a merge-blocking gate on every Python version.

What it checks (`registry_validation.run_doctor:825`), in order:

| Check group | Examples |
|---|---|
| Env setup | `.env` present; keys missing vs `.env.example`; **warns when `CRISAI_API_KEY` unset** ("All API endpoints are unprotected"); `CRISAI_SESSION_MEMORY_STRATEGY` value |
| Runtime environment | active interpreter vs `.python-version` pin; anyio asyncio backend importability (a stale venv makes every web request 500 through the middleware) |
| Registry files | schema/enum validation of all `registry/*.yaml`; info line `semantic_graph.yaml loaded (N vertices)` — 31 as of 2026-07-02 |
| Cross-references | agent→model_ref, agent→server ids, prompt files, tools.allow vs tools.internal overlap, capability metadata |
| Hygiene | tracked secret-like paths; token-cache paths configured inside the workspace; token cache file permissions (wants 0600) |
| `--models` only | dry-builds each agent (`factory.build_agent(agent, mcp_servers=[])`) — no API calls, but **client construction is eager**: every shipped model sets an explicit `base_url`, and for the openai provider that path requires the API key at build time (`model_resolver.py:95-99`, `agents/factory.py:57`). So `doctor --models` reports per-agent errors when `OPENAI_API_KEY` (or the relevant provider key) is absent, even though nothing is called. |

Real output on this machine (2026-07-02): ✅ with two warnings (`.env` missing
`CRISAI_TERMINAL_TITLE_ENABLED`; `.auth/msal_token_cache.json` too permissive).

## 7. `graph_version`: proving which semantic graph a run used

`graph_version` in `DETERMINISTIC_RETRIEVAL_CONTEXT` trace metadata is the **first
12 hex chars of SHA-1 over the bytes of `registry/semantic_graph.yaml`**
(`orchestration/retrieval_association_graph.py:322-332`) — it is NOT the `version: 1`
field inside the YAML, which never changes. Sentinels: `"unavailable"` (file
missing), `"unreadable"` (OSError). The graph is fail-open: `graph_loaded: false`
means routing continued without it.

To prove a run used the current graph (worked example — these matched on this
machine, value `aa3594c2dddc`):

```bash
python3 -c "from hashlib import sha1; from pathlib import Path; \
print(sha1(Path('registry/semantic_graph.yaml').read_bytes(), usedforsecurity=False).hexdigest()[:12])"
grep '"DETERMINISTIC_RETRIEVAL_CONTEXT"' logs/agent_trace.jsonl | tail -1 | python3 -c \
"import json,sys; print(json.loads(sys.stdin.read())['metadata']['graph_version'])"
```

Any registry-graph edit changes the hash, so a before/after trace comparison is hard
evidence that a routing difference did (or did not) come from the graph change.

## 8. Shipped scripts (`.claude/skills/crisai-diagnostics-and-tooling/scripts/`)

All three were built and tested against the real repo state on 2026-07-02.

### 8.1 `summarise_run.py` (read-only)

Summarises a run from either record type:

```bash
python3 .claude/skills/crisai-diagnostics-and-tooling/scripts/summarise_run.py \
    workspace/tasks/Test003/.crisai/runs/<run_id>.json
python3 .claude/skills/crisai-diagnostics-and-tooling/scripts/summarise_run.py \
    logs/agent_trace.jsonl --run <trace_run_id_prefix>   # default: latest run
```

Real output against the trace for Test003's run (note all six stages, vs only two
surviving in the truncated snapshot):

```
run_id:        f6a0eed83f564bb0a0ec83e17278fbc6   (27 trace events)
mode:          pipeline
contract:      source_required=True evidence_level=metadata_read
policy signals: TASK_CONTRACT, REQUEST_CONTRACT, WORKSPACE_WRITE_AUTHORIZATION, DETERMINISTIC_RETRIEVAL_CONTEXT

Stages:
  stage                        model                     in tok   out tok    cached       ms   cost USD
  -----------------------------------------------------------------------------------------------------
  retrieval_planner            gpt-5.4-mini               4,396       693         -     4317          -
  context_retrieval            gpt-5.4-mini              42,730     5,574    23,552    38634          -
  context_synthesizer          deepseek/deepseek-v4-f         -         -         -    25948          -
  design                       gpt-5.4-mini               3,765     1,451         -     7210          -
  review                       gemini/gemini-2.5-pro          -         -         -    21900          -
  orchestrator                 gpt-5.4-mini               6,482     1,395         -     6369          -
  -----------------------------------------------------------------------------------------------------
  TOTAL                                                  57,373     9,113    23,552          - (no pricing in registry/models.yaml)

Checkpoints:
  - checkpoint: RETRIEVAL_CHECKPOINT
  - checkpoint_decision: RETRIEVAL_CHECKPOINT_DECISION continue
```

How to interpret it:

- **`-` in token columns on deepseek/gemini rows** = LiteLLM stage without usage
  reporting, not a free stage (§2 caveat).
- **A repeated stage row** (e.g. `context_retrieval` twice in Test001's failed run
  `ce0025eb…`) = the one-shot evidence-contract repair retry ran; if the run still
  failed afterwards, the bundle never validated.
- **`Gates / errors` section** prints `policy_violation`/`stage_error` events and
  the snapshot's terminal `error` — the exact gate string tells you which enforcement
  fired (evidence transport, source-fit, write policy, artefact conformance).
- **The 500-event-cap WARNING** on snapshots means: trust `status`/`error`/
  `final_output`, then re-run the summariser against `logs/agent_trace.jsonl
  --run <trace_run_id>` for the complete stage table.
- **Empty `final_output` + `status: failed`** = the run died at a hard gate before
  finalisation (by design — gates fail hard, not soft).

### 8.2 `cleanup_stray_auth_dirs.sh` (MUTATING — deletion only, with confirmation)

```bash
./.claude/skills/crisai-diagnostics-and-tooling/scripts/cleanup_stray_auth_dirs.sh --dry-run   # list only
./.claude/skills/crisai-diagnostics-and-tooling/scripts/cleanup_stray_auth_dirs.sh            # list + confirm + remove
```

Root cause (verified in code): every MCP server module resolves its workspace root
from `sys.argv[1]` **at import time** and immediately creates `<ROOT>/.auth`
(`src/crisai/servers/sharepoint_server.py:29-34`; same argv pattern across the
server modules). Any `pytest <flag> …` invocation with a flag before the test path
(e.g. `pytest --collect-only -q`) therefore litters the repo root with directories
literally named `--no-cov/`, `-q/`, `--collect-only/`, each containing only
`.auth/`. Live and recurring as of 2026-07-02 (droppings dated May 18 – Jul 2);
safe to delete; they recur until the import-time side effect is fixed.

The script only removes top-level dirs that (a) are named like a flag (leading
`-`), (b) are untracked by git, and (c) contain nothing but `.auth/`. Everything
else is listed as `SKIP`. Dry-run output on this machine found exactly
`./--no-cov`, `./--collect-only`, `./-q`.

### 8.3 `mode_parity_check.py` (read-only)

Mode-parity gaps — a fix landing in `run_pipeline`/`run_single` but not
`run_peer_pipeline` — are this repo's dominant regression pattern (gate parity
PR #29, planner-fallback parity PR #39, materialisation parity PR #44). This script
AST-parses `src/crisai/cli/pipelines.py` and diffs the sets of function calls made
inside the three mode entry points:

```bash
python3 .claude/skills/crisai-diagnostics-and-tooling/scripts/mode_parity_check.py
```

Interpretation: each printed name is a question ("should the other mode do this
too?"), not a verdict — many asymmetries are intentional (peer has its own
author/challenger/refiner/judge helpers; single mode inlines its own stage
bookkeeping). On 2026-07-02 the pipeline-not-peer list correctly surfaces the two
known asymmetries:

- `_framing_only_planner_spec` — pipeline strips source-search servers from the
  retrieval planner (`pipelines.py:1207`); peer mode still runs the planner with the
  raw spec. This is the open item **TODO-057**, the most predictable next parity
  failure.
- `_enforce_source_inventory_fit` — pipeline-final gate; peer mode relies on
  `enforce_peer_final_deliverable_verification` instead.

Run it whenever you change `run_pipeline` and diff its output before/after: a new
name appearing on the pipeline-only side is a prompt to add peer coverage or record
the intentional asymmetry.

## 9. Quick greps you will keep reusing

```bash
# All gate firings ever recorded (--json-lines is required: without it,
# json.tool parses stdin as ONE document, errors on line 2, and prints nothing)
grep '"policy_violation"' logs/agent_trace.jsonl | python3 -m json.tool --json-lines --no-ensure-ascii | less

# Failed runs across the eval corpus, with reasons
python3 - <<'EOF'
import json, glob
for f in sorted(glob.glob("workspace/tasks/*/.crisai/runs/*.json")):
    d = json.load(open(f))
    if d.get("status") == "failed":
        print(f, "|", (d.get("error") or "")[:120])
EOF

# One run's full event stream from the trace
grep '<trace_run_id>' logs/agent_trace.jsonl

# Latest tool activity on the SharePoint connector
tail -20 logs/sharepoint_mcp.log
```

## 10. When NOT to use this skill

- **Triaging a failure symptom** ("run dies with X, what do I try?") → use
  `crisai-debugging-playbook`; come back here for the measurement tools it tells
  you to run.
- **Historical incident context** (why a gate exists, what investigation produced
  it) → `crisai-failure-archaeology`.
- **Setting up, starting, or stopping services**, `./start`/`./stop`, ports,
  bootstrap, daily operation → `crisai-build-run-operate`.
- **Env-var/flag catalogue** (defaults, guards, what `CRISAI_MATERIALISE_SOURCES`
  does product-wise) → `crisai-config-and-flags`.
- **Test commands and what counts as evidence for a change** →
  `crisai-validation-and-qa`. In particular, do not run `pytest` with flags before
  the test path until the argv[1] import bug is fixed (§8.2).
- **Building a proof from these measurements** (router golden set, gate
  reproduction, trace-based proof discipline) → `crisai-proof-and-analysis-toolkit`.

## Provenance and maintenance

Verified against the working tree on 2026-07-02 (main @ c39273b). One-line
re-verification commands for facts that may drift:

```bash
# Trace redaction is still read-handle-only (TODO-030 open)
grep -n "read_handle\|redact" src/crisai/tracing.py
grep -n "TODO-030" reference/TODO.md

# policies.yaml still unread by code
grep -rn "policies" src/crisai/ --include='*.py'

# graph_version still sha1-of-file-bytes, 12 hex chars
grep -n "sha1" src/crisai/orchestration/retrieval_association_graph.py

# spend flags/source unchanged
grep -n '@app.command("spend")\|--run\|--last' src/crisai/cli/main.py | head -5

# doctor still has only --models; check groups unchanged
sed -n '491,506p' src/crisai/cli/main.py && sed -n '825,858p' src/crisai/registry_validation.py

# snapshot event cap and truncation limits
grep -n "MAX_EVENTS_PER_RUN\|MAX_EVENT_CONTENT_CHARS\|MAX_FINAL_OUTPUT_CHARS" src/crisai/apps/run_history.py

# argv[1]/.auth import bug still present (script 8.2 still needed)
sed -n '29,34p' src/crisai/servers/sharepoint_server.py

# pricing still unconfigured (spend inactive)
grep -n "pricing" registry/models.yaml

# peer planner still un-stripped (TODO-057 / parity script expectation)
grep -n "_framing_only_planner_spec" src/crisai/cli/pipelines.py

# materialised cache still lands under the visible task root
sed -n '255,262p' src/crisai/cli/pipelines.py
```
