# NewTest-04 Restart Handoff

Last updated: 2026-05-19

## Current Status

NewTest-04 assessment is complete across runtime, Gem, and web. The work is being
implemented one improvement slice at a time.

Slice 1, runtime source/evidence/security correctness, is complete locally.

Commits:

- `e36be9c fix(runtime): preserve sanitized source evidence`
- `cc21f45 test(runtime): cover sanitized evidence transport`
- `8cf6444 fix(runtime): redact bare SharePoint read handles`

Notes:

- `e36be9c` and `cc21f45` were created by the runtime area agent despite the
  single Git-writer rule. The orchestrator noted the process breach and did not
  revert because the commits were already on `main`/`origin/main`, in scope, and
  CI was green.
- `8cf6444` is local only at this handoff. Do not push unless the user asks.
- Worktree was clean except unrelated untracked
  `runtime/continue-regression-NewTests-01.patch`.
- Claude memory writes were unavailable in this worker runtime, so this file is
  the durable restart context.

Verification already run:

- `pytest --no-cov tests/unit/test_tracing.py tests/unit/test_evidence_contract.py tests/unit/test_chat_context.py tests/cli/test_pipelines.py -q`
  - Result: `82 passed`
- `ruff check src/crisai/tracing.py tests/unit/test_tracing.py`
  - Result: passed
- `gh run list --branch main --limit 3`
  - Prior pushed runtime commits were green.
  - No CI run exists for local commit `8cf6444` because it was not pushed.

## Slice 1 Implemented

- Single-mode retrieval planner output persists source candidates in
  `session_memory.source_candidates`.
- Follow-up request contracts resolve candidates from session memory and merge
  source families/named sources.
- Sanitized `evidence_bundle_v1` is used in trace/checkpoint/UI-snapshot
  metadata.
- `read_handle` is removed from sanitized evidence bundles and recursively
  redacted from traces.
- Bare `sharepoint_doc:*` tokens are redacted in trace text.
- Evidence levels are promoted after successful reads.
- Evidence/source candidate dedupe uses stable identity including `content_id`,
  SharePoint `sourcedoc` GUID, and `open_url`.
- Source type normalization uses registry `source_type_markers`.

## Next Slice

Next planned work: runtime UI event contract correctness.

Assign to `runtime_codex`; ask `runtime_claude` to review if available.

Scope:

- Runtime/UI event production and tests under `src/crisai/`, `tests/`, and shared
  UI contracts if needed.
- Do not edit Gem or web app implementation in this slice unless only tests are
  needed to confirm contract behavior.
- Do not touch unrelated `runtime/continue-regression-NewTests-01.patch`.

Goals:

1. Emit `stage_started` for single-mode runs so web/Gem never show a frozen
   pending stage during active work.
2. Generate `expected_stages` from the actual execution path.
   - Discovery/single: `retrieval_planner`, `final_output`.
   - Summary pipeline: `retrieval_planner`, `context_retrieval`,
     `context_synthesizer` skipped, `summary`, `orchestrator` skipped,
     `final_output`.
   - Design pipeline: current design/review/orchestrator path.
3. Emit `stage_skipped` for every expected stage intentionally bypassed.
4. Prevent checkpoint events from becoming stage rail items.
5. Use stable snake_case stage keys and separate human labels.
6. Keep `routing_decision` and `task_contract` out of normal progress content;
   retain structured metadata for verbose/debug surfaces.

Expected tests:

- Single-mode run emits a running stage event before final completion.
- Summary fast path expected stages include `summary` and do not include stale
  `design`.
- Skipped stages show as `skipped`, not permanent `pending`.
- Checkpoint events do not create a phantom `retrieval_checkpoint` stage.
- Normalized UI events expose stable keys and human-readable labels.
- Existing runtime source/evidence/security tests still pass.

## Later Slices

After runtime event contract correctness:

1. Web UX fixes:
   - Markdown rendering for final answers.
   - Checkpoint decision/actions before long evidence detail.
   - Expandable evidence detail.
   - Bounded transcript and stage rail scrolling.
   - Hide internal routing/task-contract events in normal mode.
   - Narrow `aria-live`.
2. Gem guard/polish:
   - Keep bounded rendering behavior.
   - Add regression guard that checkpoint metadata is not expanded into normal
     terminal panels.
   - Prefer concise source rows over raw long URLs where possible.
3. Observability:
   - Structured streaming fallback metadata.
   - History flush after each run.
   - Token/cost fields only when provider data exists.

