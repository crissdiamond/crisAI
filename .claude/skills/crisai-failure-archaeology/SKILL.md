---
name: crisai-failure-archaeology
description: The verified incident chronicle for crisAI — every major investigation, dead end, rejected fix, and revert, as symptom → root cause → evidence (commit hashes) → status. Load this before re-investigating a failure that smells familiar (auth AADSTS errors, wrong-source retrieval, policy-gate false failures, empty planner output, CORS-masked 401/429, MCP timeouts, Gem paste bugs), before reverting or re-attempting a previously rejected approach, when a commit body references Test001–Test007 or a "defect A/B/C", or when git history looks rewritten, squash-lossy, or stash-stale.
---

# crisAI failure archaeology

This is the repo's institutional memory of failure: what broke, what was tried and
abandoned, what actually fixed it, and what is still open. Every commit hash below was
verified against this repository on 2026-07-02 with read-only `git show`/`git log`.
Use it to avoid re-running dead-end investigations that already consumed days.

How to read an entry: **Symptom** (what was observed) → **Root cause** (the verified
mechanism) → **Evidence** (commits/files you can re-check) → **Status** (settled or
open) → a closing "Do not re-fight this" line stating the settled conclusion.

Repo context: single-author history, 2026-04-18 → 2026-07-01, three eras —
direct-to-main Cursor commits (April–early May), the hcom multi-agent dev-team era
(May), solo PR + squash-merge era (mid-June onward). "TestNNN" names live evaluation
sessions run against the real system; their task directories live locally (gitignored)
under `workspace/tasks/Test001`–`Test007` as of 2026-07-02.

## When NOT to use this skill

- You are actively triaging a live failure and need a symptom→experiment table →
  **crisai-debugging-playbook**.
- You need to *prove* a fix (router golden set, TestNNN reproduction, trace-based
  proof) → **crisai-proof-and-analysis-toolkit**.
- You need the change process, commit conventions, or squash discipline as rules →
  **crisai-change-control** (this skill only records the incidents behind them).
- You need to operate the hcom dev-team apparatus → **crisai-devteam-operations**.
- You need measurement tooling (traces, spend, run JSONs) → **crisai-diagnostics-and-tooling**.

---

## 1. The AADSTS7000218 auth saga (2026-05-03, Cursor era)

**Symptom.** MSAL delegated auth against Azure AD kept failing with
`AADSTS7000218: The request body must contain the following parameter:
'client_assertion' or 'client_secret'` during device-code flow. Preceding context the
same day: WSL2 broke localhost-redirect interactive auth (`cbbc30a` switched to
device-code flow in WSL2), expired tokens made MCP stdio tools hang the full 240 s
client timeout (`f00411f` added fail-fast `require_silent_token()`), the device code
had to be surfaced in-terminal (`76afc2f`), and token caches were split per provider
(`a878b27`).

**Three dead ends, in order (all real commits, all abandoned):**

| # | Attempt | Commit | Why it died |
|---|---------|--------|-------------|
| 1 | `ConfidentialClientApplication` when `MS_CLIENT_SECRET` is set | `2fbd2e8` | Same AADSTS7000218 |
| 2 | Raw-requests device flow (MSAL 1.36.0 `ConfidentialClientApplication` has no `initiate_device_flow` → `AttributeError`) | `5c5ec96` | Same error, now hand-rolled |
| 3 | `client_secret` in BOTH `/devicecode` initiation and `/token` polling, per RFC 8628 §3.1 | `c11eb8f` | Same error — increasingly RFC-literate, still wrong layer |

Plus debug-print commits `18e36d0`/`88d299f` to trace `MS_CLIENT_SECRET` into the MCP
subprocess (the secret WAS propagating — that was never the problem).

**Root cause** (from the `da4f4bd` commit body, the best documentation of this
anywhere in the repo): Azure AD in this tenant does not support device-code flow for
confidential clients **regardless of whether client_secret is sent**. The fix was a
portal checkbox, not code: enable **"Allow public client flows"** on the Azure AD app
registration (Authentication → Advanced settings).

**Evidence.** `git show da4f4bd` — removes all `ConfidentialClientApplication` paths;
`_build_app` always returns `PublicClientApplication`. Later hardening: `aab7c47`
(lazy site resolution), `d431b96` (silent-only Graph auth for read tools), `4b75b70`
(device-code popup from web UI), `1f88959` (token-cache file permissions).

**Status.** Settled.

**Do not re-fight this:** delegated auth is `PublicClientApplication`-only. If
AADSTS7000218 reappears, fix the Azure app registration ("Allow public client flows"),
never re-add confidential-client code paths.

## 2. The Gemini/Antigravity 7-minute revert and proper redesign (2026-05-22/23)

**Symptom.** `ceb38c9` (2026-05-22 12:01) "feat: support running review agents via
Gemini/Antigravity" hacked a `REVIEWER_TOOL` env substitution directly into
`scripts/hcom_start.sh` and the duplicated copies under `development-team/scripts/`
(widened a `claude` case-arm to `*`, swapped the binary everywhere `claude` launched).

**Root cause.** Quick provider swap with no abstraction. Reverted **7 minutes later**
by `01d3654` (12:08) — the only literal `Revert` commit in the entire history.

**Resolution.** Redesigned properly within the hour: `1fe2388` (12:09) design doc
`reference/development/review_provider_design.md`, then `7d6d7f3` review provider
launcher, `bb9266a` persistent antigravity reviewers, `2f538cd` "keep antigravity
review experimental", `230ec69` split reviewer lifecycle/provider, `3026d89`
antigravity reviewer modes, and a fix train ending `5ccd937` (isolated antigravity
sessions, 05-23). `scripts/hcom_antigravity_{home,model,preflight}.sh` exist on main
as of 2026-07-02.

**Epilogue — the archive-tag convention.** `a3ddee0` "feat(dev): support gemini
antigravity reviewers" (2026-05-23) is NOT on main; local main diverged from
origin/main once and the divergent commit was preserved as annotated tag
`archive/a3ddee0-gemini-reviewers` ("superseded local-main commit … functionality
present in fuller form on origin/main") instead of being merged. That convention is
documented nowhere else.

**Status.** Settled (antigravity reviewers remain labelled experimental per `2f538cd`;
no later commit promotes them).

**Do not re-fight this:** provider support in the hcom review layer goes through the
review-provider abstraction (`reference/development/review_provider_design.md`), never
a direct binary swap in launch scripts. Reverts in this repo mean "wrong approach",
not "broken build" — both revert events were followed within hours by a better design.

## 3. The 955dcda squash-loss (2026-06-14)

**Symptom.** Commit `955dcda` "docs(todo): prioritize source trust follow-ups" was
pushed to the PR #31 branch **after** the working agent's last push. The squash merge
of #31 (`bbd3c00`) silently excluded it — no error, no conflict, content just gone
from main.

**Root cause.** Squash-merging from a stale view of the branch: whoever squashes sees
the diff they last reviewed, not necessarily the branch tip.

**Evidence.** `git cat-file -t 955dcda` → `commit` (still a dangling object;
`git merge-base --is-ancestor 955dcda main` fails). Recovery: `7abad51` (#32)
"restore source-trust priority refinement (recovers commit 955dcda)" restored the
content byte-for-byte (TODO-055 → P1, TODO-057 → P1, sequencing note).

**Status.** Settled (content recovered); the trap itself is permanent GitHub
squash-merge behaviour.

**Do not re-fight this:** before squash-merging any PR, re-check the remote branch tip
against what was reviewed (`git fetch && git log origin/<branch> -1`); a late push is
silently dropped by squash otherwise.

## 4. The April history rewrite (refs/replace, unverifiable content)

**Symptom.** 27 `refs/replace/*` refs (a git-filter-repo signature) map old
2026-04-18/19 hashes to current commits (targets include `44fb491` "Initial commit",
`17aec4e`, and the duplicate pair `f0375bb`/`47cbb99`, both titled "feat(orchestration):
add phase 1 heuristic router…").

**Root cause.** The first ~2 days of history were rewritten during an April cleanup
wave: `395132a` "removed unnecessary files", `bf2dd60` "removed .old files",
`fd10c4a` "repo cleaning", `53d395f` "Forced sync" (04-24), `435fef2` "stop tracking
cursor and runtime artifacts", `12a6704` "Vs code test". The pre-rewrite objects are
garbage-collected: `git --no-replace-objects cat-file -t 234ef8a2346…` →
`fatal: could not get object info`. **What was purged is unverifiable locally**; only
the owner knows (candidates: `.old` files, Cursor/runtime artefacts).

**Evidence.** `git for-each-ref refs/replace | wc -l` → 27 (2026-07-02).

**Status.** Settled as history; the replace refs are local-only state, and whether
they should be shared is an open question.

**Do not re-fight this:** do not attempt to recover or reason about pre-rewrite April
content — it is gone. Treat any old hash that resolves only via `refs/replace` as
rewritten, and do not trust commit archaeology before 2026-04-20 as complete.

## 5. The ADR-015 source-grounding arc (2026-06-14 → 2026-07-01, PRs #25–#44)

The flagship campaign. One live evaluation session (Test001) exposed the missing
"find → then act" backbone; the fix arrived as an ADR plus ~20 slice PRs merged on
2026-06-14, interleaved with fixes for six more numbered test-session defects. Read
`reference/decisions/CRISAI-ADR-015-source-grounding-backbone.md` (Status: accepted,
2026-06-14) for the design; the entries below are the failure record. Materialisation
(fetching a confirmed source into `workspace/tasks/<id>/sources/<source-id>/<revision>/`)
remains opt-in behind `CRISAI_MATERIALISE_SOURCES` (shipped default false) as of
2026-07-02; checkpoint pin/retire controls are still open per the ADR (tracked as
TODO-048/TODO-003, both P0 in-progress).

### 5.1 Test001 — wrong-source continuation (the trigger)

**Symptom.** Turn 1 ("find files with 'UCL integration strategy' in title, rank by
authority") worked perfectly. Turn 2 ("compare the 2 versions … author a knowledge
artefact", peer mode) failed at the policy gate: retrieval live-searched OneDrive,
matched only the Office lock stub `~$UCL Integration Strategy_Full Presentation v2
(cd).pptx`, could not read it, run killed before authoring.

**Root cause** (two layers, both verified in the `0cdd086` body and the ADR):
1. Named at design level as **wrong-source continuation** — a source resolved in a
   prior turn is persisted but not durably bound on reference, so a follow-up
   re-resolves against live, mutable OneDrive state. "The 2 versions"/"v2" scored
   below the resolver's near-full-title threshold. The ADR is explicit: "The root
   cause is **not** the lock file"; the user "explicitly rejected workarounds"
   (score tuning) for this backbone.
2. Mechanically, **anchor-slot starvation by GUID duplicates**: the same v3 deck
   rediscovered under three different provider GUIDs consumed all three resolution
   slots, starving the distinct v2 source. "It was never a score problem and never
   really the lock file."

**Evidence.** `git show f4c873b` (ADR PR #25); `git show 0cdd086` (#26, phase 1: one
logical document = one anchor — dedup by stable provider id OR normalised
title+family+scope); the ADR file itself carries the full two-turn reproduction.

**Status.** Settled for the reproduced failure (phase 1 + materialisation slices);
the end-to-end backbone (pin/retire, multi-turn regression test) is open under
TODO-048/TODO-003.

**Do not re-fight this:** anchors are keyed by stable provider identity, never title;
duplicate GUIDs must collapse to one logical document before resolution; do not tune
title-match scores as a fix for follow-up-turn source loss.

### 5.2 Test003 defect A — gate existed in only one mode

**Symptom.** An inventory ask ("files with 'UCL integration strategy' in the title")
over-routed to the pipeline (mixed_complexity) and presented off-title files
(Integration-strategy.pdf, Integration UCL.pptx, an unrelated paper) as matches.

**Root cause.** The source-inventory title/scope fit gate lived only in `run_single`;
the pipeline path bypassed it entirely.

**Evidence.** `git show a49593c` (#29) — adds `_enforce_source_inventory_fit()` called
on `run_pipeline`'s final output; reproduction confirmed the existing gate raises on
test003's actual output. The body also flags the follow-up that became **TODO-055**
(spurious title phrases like "linkable" scraped from instruction words — still open
P1 at `reference/TODO.md:116` as of 2026-07-02).

**Status.** Settled (first recorded instance of the mode-parity class, §13).

**Do not re-fight this:** output gates must be mode-independent — validate the
deliverable, not the path that produced it.

### 5.3 Test003 defect B — the model ignored "do not retrieve"

**Symptom.** The framing-only retrieval planner ran its own competing OneDrive search
and returned a separate, wrong file list that context_retrieval then discarded —
wasted tokens/latency and a misleading intermediate table.

**Root cause.** The planner spec carried the same source-search MCP servers
(sharepoint_docs, documents, intranet) as context_retrieval, and **the model ignored
the prompt-level instruction** "Do **not** retrieve or read source documents in this
stage" — that sentence lives in the runtime-built planner prompt
(`src/crisai/orchestration/prompt_generation.py`, line 309 as of 2026-07-02), not in
the standing prompt file; `prompts/retrieval_planner_agent.md` states the framing
contract differently ("Leave source lookup to **Context Retrieval** in pipeline/peer
framing mode").

**Evidence.** `git show 9c9ee2e` (#30) — strips source-search servers from the
pipeline planner spec (`_framing_only_planner_spec`, applied at
`src/crisai/cli/pipelines.py:1207` as of 2026-07-02), keeping framing tools
(session_memory, workspace_read). The commit body explicitly scopes the fix to the
pipeline path and defers peer.

**Status.** Settled for pipeline mode; **open for peer mode** — `run_peer_pipeline`
still runs the planner with the raw spec (`specs["retrieval_planner"]` at
`pipelines.py:1676` as of 2026-07-02), tracked as **TODO-057** (P1, todo, TODO.md:117).
This is the known open mode-parity instance (§13).

**Do not re-fight this:** prompt text is not a contract here — enforcement is
structural (strip the tools, gate the output, put vocabulary in the registry). This
commit is the doctrinal origin of that rule.

Defect C from the same assessment (Office lock stubs) has its own entry, §6.

### 5.4 Test004 — empty planner output killed peer runs

**Symptom.** A peer "author a knowledge artefact" run died at the retrieval_planner
stage with "returned empty output".

**Root cause.** The planner (a fast reasoning model, `gpt-5.4-mini` at the time)
generated 449 output tokens of valid reasoning but committed an **empty final
message**; `run_pipeline` already fell back to a deterministic handoff on this, but
the peer path treated it as fatal. Commit body: "Not caused by recent work … it is a
model/engine behaviour the peer path failed to tolerate."

**Evidence.** `git show 0b63dbf` (#39) — applies `_build_retrieval_planner_fallback`
to `run_peer_pipeline`, traces `RETRIEVAL_PLANNER FALLBACK`, continues to
context_retrieval.

**Status.** Settled (second mode-parity instance, §13).

**Do not re-fight this:** an empty final message from a reasoning model is valid model
behaviour, not a code bug; advisory stages must degrade to deterministic fallbacks in
every mode, never abort the run.

### 5.5 Test005 — OneDrive/Graph search is word-order sensitive

**Symptom.** "Find files with 'UCL integration strategy' in the title" returned only
unrelated "Integration UCL v.1.x" files; the inventory gate then (correctly) failed
the run.

**Root cause.** The model reformulated the user's quoted title into the reordered
query "Integration UCL"; **OneDrive/Graph search is word-order sensitive** (live-check
confirmed: the verbatim phrase returns the real decks; the reordered one does not).
Secondary: `infer_source_fit_constraints` scraped instruction/formatting words
("linkable name", "authoritative version. Present …") into spurious title phrases.

**Evidence.** `git show b386a17` (#42) — retrieval prompts now instruct querying the
required title phrase verbatim (same words, same order); explicitly-quoted phrases
skip the relation/object heuristics (TODO-055 partial). Per the user's recorded call
in the body, the inventory gate keeps its **hard** failure: a wildly wrong search
should fail loudly, not present wrong files.

**Status.** Settled; TODO-055 (extraction precision generally) still open P1.

**Do not re-fight this:** query external search with the user's constrained phrase
verbatim; never let a model paraphrase a quoted title. Gate hard-failure on
off-constraint results is a deliberate decision, not a bug.

### 5.6 Test006 — output destination became an input source requirement

**Symptom.** "Author a strategy artefact from ‹OneDrive deck›, save under
workspace/knowledge_staging/…" was rejected by the source-fit gate: the correctly-read
OneDrive deck failed for "not being in the workspace".

**Root cause.** The gate re-scraped the raw message with
`infer_source_fit_constraints`, so the **output path** inferred a `workspace` **input
source scope** — even though the structured request contract already separated
`named_sources` from `output_path`.

**Evidence.** `git show 2f41bec` (#43) — `output_path` threaded into
`infer_source_fit_constraints`; the destination's scope is excluded from inferred
source scopes ("a write destination is never a source requirement"). Registry Tier-1
cleanup: workspace `source_scope_markers` in `registry/semantic_catalog.yaml` now
require read/fetch phrasing; bare "workspace" and write phrasings excluded.

**Status.** Settled. The body defers a **Tier-2** registry tightening (peer_contract
"fix"/"source"/"review", operations "bug" — mis-classify but do not fail runs); as of
2026-07-02 no TODO entry tracks it — open and untracked.

**Do not re-fight this:** when a structured contract already separates source from
destination, gates must honour that separation — never re-scrape prose the contract
has already parsed.

### 5.7 Test007 — peer mode materialised nothing

**Symptom.** A Test007 peer run read its source live and authored a strong artefact,
yet **zero `SOURCE_MATERIALISED` events fired** and no cache was written — the
read-through cache silently did not exist on the main authoring path.

**Root cause.** Slice 3b (`2ed10bd`, #38) wired checkpoint-time materialisation into
`run_pipeline` only; knowledge authoring runs in peer mode.

**Evidence.** `git show 841769e` (#44) — wires the same
`_materialise_confirmed_sources` call into `run_peer_pipeline` after evidence
validation: same opt-in (`CRISAI_MATERIALISE_SOURCES`), best-effort, traces
`SOURCE_MATERIALISED`/`SOURCE_CACHE_HIT`, never aborts on per-source failure.

**Status.** Settled (third mode-parity instance, §13).

**Do not re-fight this:** "silently absent feature" is a failure mode — verify a new
cross-cutting mechanism by observing its trace events on **every** mode, not by the
run succeeding.

### 5.8 Arc-internal trap — the cache was written where agents cannot read

**Symptom.** Mid-arc, materialised sources were cached under the task's `.crisai/`
metadata directory — which workspace safety deliberately blocks agents from reading —
so agents could not read their own cached sources.

**Evidence.** `git show 1749a65` (#41, slice 4b) — relocates the cache to the visible
`workspace/tasks/<id>/sources/` tree and adds anchor-first read-through; ADR-015
Consequences records the readable-location rationale.

**Status.** Settled.

**Do not re-fight this:** agent-consumable data must never be written under
`.crisai/`; dot-prefixed workspace entries are invisible to agents by design.

## 6. Office lock stubs impersonating real documents (Test001/test003 defect C)

**Symptom.** OneDrive/SharePoint search returned orphaned Office owner-lock stubs
(`~$Name.pptx`, `.~lock.…`) — tiny hidden companion files Office writes while a
document is open, lingering for years after crashes. In the Test001 and test003
traces they polluted every result set and, once the real deck dropped out of the live
index, **impersonated it under the same base name**, driving a wrong "authoritative"
ranking and an unreadable required read.

**Root cause.** No connector-level junk filtering; stubs are indistinguishable from
documents to downstream ranking.

**Evidence.** `git show 2455c1c` (#28) — `_is_office_lock_stub`
(`src/crisai/servers/sharepoint_server.py:257` as of 2026-07-02) filters stubs in
every search/list tool **before** the per-call result cap, so a genuine file ranked
just below a stub still surfaces instead of being pushed out by junk.

**Status.** Settled.

**Do not re-fight this:** junk filtering belongs at the connector, before result caps
— and per ADR-015 it is hardening, not the fix for wrong-source continuation (§5.1).

## 7. publication_terms bare-extension misroute

**Symptom.** Read/list/summarise asks that merely *referenced* a source `.pptx`/`.md`
(directly or folded in from a prior turn) were mis-tagged `publish_artifact`, and the
policy gate then killed completed runs.

**Root cause.** `publication_terms` in the semantic registry mixed produce phrases
with bare file-extension tokens (`.doc`/`.docx`/`.ppt`/`.pptx`/`.xls`/`.xlsx`/`.txt`/`.md`);
a type token matches a referenced file as if it were a publish request.

**Evidence.** `git show 822a2fa` — replaces bare extensions with produce-context
phrases ("into a …", "as a …", "export …"); genuine publication asks preserved;
regression tests cover both directions and the continuation-fold path. ADR-014
explicitly deprecates file-type tokens as action signals.

**Status.** Settled.

**Do not re-fight this:** never add bare file-extension tokens to intent term lists —
mention ≠ intent. Intent vocabulary must be produce-context phrases.

## 8. Starlette middleware ordering — CORS-masked 401/429

**Symptom.** Browser clients saw opaque CORS errors instead of real 401/429 statuses;
the rate limiter's `Retry-After` was unreadable.

**Root cause.** `CORSMiddleware` was registered at app creation, before the
`@app.middleware` auth/rate-limit decorators. **Starlette runs the most recently
added middleware outermost**, so CORS ended up innermost: 401/429 responses
short-circuited before reaching it and carried no `Access-Control-Allow-Origin`.

**Evidence.** `git show 65389d3` — re-registers CORS last (outermost). Side effect:
preflight is answered at the edge, which removed the OPTIONS auth bypass — OPTIONS is
now authenticated like any other method when a key is set.

**Status.** Settled.

**Do not re-fight this:** register CORS last; never reintroduce an OPTIONS auth
bypass. A "CORS error" in the browser against this API is usually a masked 401/429 —
check the server side first.

## 9. Vision-PDF read blew the MCP client timeout

**Symptom.** A pipeline run reading a 16-page scanned PDF failed with
"read_document: Timed out … Waited 60.0 seconds", aborting the whole run.

**Root cause.** The TODO-044 image-PDF vision fallback described pages sequentially at
~8–9 s/page; the default 12 pages needed ~100 s against the document MCP server's
60 s client timeout.

**Evidence.** `git show 2d39490` — parallelised page description (ThreadPoolExecutor,
≤5 concurrent), default `CRISAI_PDF_VISION_MAX_PAGES` 12→8, document server
`client_timeout_seconds: 120`. Body notes the fix "takes effect after restarting the
API (which respawns the document MCP subprocess)".

**Status.** Settled.

**Do not re-fight this:** per-item LLM work inside an MCP tool call must be budgeted
against the *client* timeout, and MCP server config changes need an API restart to
respawn the stdio subprocess.

## 10. The Gem paste-bug tail

**Symptom.** The Ink terminal client ("Gem", `ui/apps/gem/`) had a long tail of
prompt-input defects: pasted prompt text lost or duplicated, startup paste not
replayed, backspace semantics broken, plus a `TypeError: reading 'length' of
undefined` after run completion and cumulative stage deltas appended instead of
replaced.

**Root cause.** Ink/terminal paste handling delivers input as fragments with no
paste boundary; each fix exposed the next edge case.

**Evidence.** Fix train: `b80c33c` (preserve pasted text + backspace), `2bc3960`
(prompt panel editing), `b1cf3c8` (replay startup paste), `ba931f4` (preserve paste
prefix), `9e47b80` (append paste fragments to live prompt); related `e3ab824`
(post-run TypeError), `bd195a3` (show latest cumulative stage delta, not append).

**Status.** Settled — no open paste defects known as of 2026-07-02.

**Do not re-fight this:** Gem's paste/prompt input handling is scar tissue — read the
`fix(gem)` train above before touching the prompt component, and test paste (including
paste-at-startup and multi-fragment paste) on any input change.

## 11. Bilingual registry removal

**Symptom.** The semantic registries were bilingual (English + Italian) until
2026-06-13; leftover Italian assertions in converted tests caused failures during the
cleanup.

**Root cause.** Initial test artefacts seeded Italian vocabulary into
`registry/semantic_catalog.yaml` and `registry/semantic_graph.yaml`.

**Evidence.** `git show 379615b` (#21) "chore(registry): remove Italian semantic
vocabulary (initial test artefacts)" — 158 deletions across registries and tests. No
ADR documents the English-only convention; the commit is the record.

**Status.** Settled.

**Do not re-fight this:** registries and tests are English-only. The user may write
prompts in Italian (per project instructions), but that is a runtime input concern —
never re-add Italian terms to registry vocabulary.

## 12. hcom-era single-writer breach (tolerated once, not precedent)

**Symptom.** During the May multi-agent dev-team era, the operating model gave the
orchestrator **exclusive** git write authority — yet commits `e36be9c` (preserve
sanitized source evidence) and `cc21f45` (cover sanitized evidence transport) were
created by the runtime area agent directly.

**Root cause.** Process breach by an area agent; recorded, not reverted.

**Evidence.** `reference/development/newtest-04-restart-handoff.md` (2026-05-19,
lines 20–23): "created by the runtime area agent despite the single Git-writer rule.
The orchestrator noted the process breach and did not revert because the commits were
already on `main`/`origin/main`, in scope, and CI was green."

**Status.** Settled as record. The hcom apparatus is dormant-but-live as of
2026-07-02 (see crisai-devteam-operations).

**Do not re-fight this:** the single-writer rule stands whenever hcom runs; the one
tolerated breach was a pragmatic exception (in-scope, CI green, already pushed), not a
precedent for area agents committing.

## 13. Mode-parity — the named recurring failure class

**Symptom pattern.** A fix or feature lands on `run_pipeline`/`run_single` and
silently misses `run_peer_pipeline` (or vice versa). Peer mode is the highest-cost,
judgement-critical authoring path, so the gap surfaces later as a live failure.

**Confirmed instances (all verified):**

| Instance | Landed on | Missed | Caught by | Fix |
|----------|-----------|--------|-----------|-----|
| Source-inventory fit gate | run_single | run_pipeline | test003 defect A | `a49593c` (#29) |
| Empty-planner deterministic fallback | run_pipeline | run_peer_pipeline | Test004 | `0b63dbf` (#39) |
| Checkpoint-time materialisation | run_pipeline | run_peer_pipeline | Test007 | `841769e` (#44) |

**Known open instance (2026-07-02):** peer mode still runs the retrieval planner with
full source-search servers (raw spec, `src/crisai/cli/pipelines.py:1676`) while
pipeline mode strips them (`_framing_only_planner_spec`, `:1207`) — **TODO-057**, P1.
Given the pattern, this is the most predictable next live failure.

**Status.** Open as a class; each instance settled individually.

**Do not re-fight this:** every change touching pipeline execution must be explicitly
checked against all three paths (`run_single`, `run_pipeline`, `run_peer_pipeline`)
before merge, and cross-cutting mechanisms must be verified by their trace events in
each mode (§5.7).

## 14. The Jul 1 stash on superseded history

**Symptom.** `refs/stash` holds `b89e552` — "WIP on local-openai-compatible-provider"
(2026-07-01) — whose parent `11c2a73` is a **superseded pre-rebase commit** of the
local-provider branch (chain `a311a26`→`17bcb1d`→`11c2a73`, same subjects as the final
`4d62977`→…, which merged as PR #45 squash `c39273b`). `11c2a73` is not reachable from
main; the stash is the only thing keeping that chain alive.

**Root cause.** The branch was rebased/redone before merge; the stash was taken on the
old line and never resolved.

**Evidence.** `git stash list` → `stash@{0}: WIP on local-openai-compatible-provider:
11c2a73 …`; `git merge-base --is-ancestor 11c2a73 main` fails and
`git branch -a --contains 11c2a73` prints nothing (only `refs/stash` keeps the
chain alive), whereas `git branch -a --contains 4d62977` prints
`origin/feat/local-openai-compatible-provider`, whose content merged into main as
squash `c39273b` (#45). (Note `git merge-base --is-ancestor 4d62977 main` also
fails — squash merges leave NO branch commit an ancestor of main; reachability
from a surviving ref is what discriminates the two chains.)

**Status.** **Open** as of 2026-07-02 — whether the stash holds un-landed work is
unverified; only the owner can say.

**Do not re-fight this:** do not apply this stash blindly onto main — its baseline no
longer exists there. Inspect with `git stash show -p stash@{0}` and diff any real
content against the merged `c39273b` before deciding to land or drop it.

---

## Cross-cutting lessons the chronicle supports

- **Structural enforcement beats prompt text** — §5.3 (`9c9ee2e`) is the origin; the
  registry-vocabulary and schema-contract rules in the project instructions are scar
  tissue from real incidents (hardcoded-vocab leaks `ef7ff0c`/`da29d33` moved terms
  into the semantic registries).
- **Reverts here signal "wrong approach", not "broken build"** — both revert events
  (§1, §2) produced better designs within hours.
- **External systems lie**: Graph search is word-order sensitive (§5.5), returns
  lock-stub impostors (§6), and tenants can reject RFC-correct flows (§1).
- **Commit bodies are the primary incident documentation** — PR-era bodies are full
  post-mortems (symptom, TestNNN reproduction, root cause, rejected alternatives,
  test-count ledger). When investigating, `git log --grep` before anything else.

## Provenance and maintenance

All hashes verified 2026-07-02 against this clone. Re-verify with:

- Any entry's commit: `git show -s --format='%H %ad %s' <hash>` then `git show -s --format='%B' <hash>`
- Auth saga chain: `git log --oneline --grep='AADSTS7000218'`
- The only revert: `git log --oneline --grep='^Revert'`
- Archive tag: `git tag -l 'archive/*'` and `git for-each-ref refs/tags/archive --format='%(contents)'`
- Squash-loss object still dangling: `git cat-file -t 955dcda && git merge-base --is-ancestor 955dcda main; echo $?`
- History rewrite: `git for-each-ref refs/replace | wc -l` (expect 27)
- Stash on superseded history: `git stash list` and `git merge-base --is-ancestor 11c2a73 main; echo $?`
- Mode-parity open instance: `grep -n '_framing_only_planner_spec' src/crisai/cli/pipelines.py` (one call site = still open) and `grep -n 'TODO-057' reference/TODO.md`
- TODO-055 status: `grep -n 'TODO-055' reference/TODO.md`
- Lock-stub filter: `grep -n '_is_office_lock_stub' src/crisai/servers/sharepoint_server.py`
- hcom breach record: `grep -n 'single Git-writer' reference/development/newtest-04-restart-handoff.md`
- ADR-015 text: `sed -n '1,50p' reference/decisions/CRISAI-ADR-015-source-grounding-backbone.md`
- Local TestNNN corpus: `ls workspace/tasks/ | grep -i test` (gitignored, machine-local)
- Materialisation flag default: `grep -n 'CRISAI_MATERIALISE_SOURCES' .env.example`
