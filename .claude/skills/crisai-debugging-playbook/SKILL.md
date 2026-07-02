---
name: crisai-debugging-playbook
description: Symptom-to-cause triage runbook for crisAI runtime failures. Load when a run dies with "Policy gate failed" (title/scope/source-fit/content-read), retrieval returns the wrong file or a ~$ Office lock stub, the retrieval planner emits empty output, a peer run raises WorkflowValidationError, an MCP tool hangs or times out (240 s), SharePoint/Graph auth fails (AADSTS7000218, device code, expired token), the browser shows CORS-looking 401/429 errors, streaming stops working, DeepSeek agents lose thinking or tools, registry model extras seem ignored, stray "--no-cov"/".auth" directories appear at the repo root, or `crisai doctor` fails.
---

# crisAI debugging playbook

Active triage for runtime failures: symptom → likely cause → discriminating experiment → fix.
Every entry below was verified against the repo on 2026-07-02 (branch `main`). Line numbers
drift; the Provenance section at the end has one-line re-verification commands.

Jargon used once and defined here:

- **Policy gate** — a deterministic post-stage check that raises `WorkflowPolicyViolation` /
  `WorkflowValidationError` and kills the run (it does not filter and continue).
- **Evidence bundle** — the schema-backed JSON contract (`evidence_bundle_v1`) that context
  retrieval must emit; parsed out of the model's text, one repair retry, then hard fail.
- **Lock stub** — the tiny `~$Name.pptx` / `.~lock.Name` companion file Microsoft Office
  creates while a document is open; not valid OOXML, unreadable, lingers as an orphan.
- **Mode parity** — the same fix must exist in all three run paths (`run_single`,
  `run_pipeline`, `run_peer_pipeline` in `src/crisai/cli/pipelines.py`); historically the
  dominant regression pattern (PRs #29, #39, #44).

## 30-second triage

1. Read the exact failure string. Almost every hard failure here has a distinctive message;
   the table below is keyed on those strings.
2. Check `logs/agent_trace.jsonl` (JSONL; one event per line). Grep for
   `POLICY_VIOLATION`, `RETRIEVAL_PLANNER FALLBACK`, `EVIDENCE_CONTRACT_REPAIR`,
   `PEER_FINAL_DECISION`, `SOURCE_MATERIALISED`, `SOURCE_MATERIALISE_ERROR`.
3. For tool-level failures, read the per-server log: `logs/sharepoint_mcp.log`,
   `intranet_mcp.log`, `document_mcp.log`, `document_export_mcp.log`, `diagram_mcp.log`,
   `workspace_mcp.log`, `session_memory_mcp.log`, `vision_mcp.log`, plus `logs/crisai.log`.
4. Web-run history persists per task at `workspace/tasks/<session>/.crisai/runs/*.json`.
5. Know which mode ran (single / pipeline / peer) — many fixes exist in only some modes.

For trace anatomy, `crisai spend`, and measurement tooling, use
**crisai-diagnostics-and-tooling** — this skill only tells you *what to look for*.

## Master symptom table

| Symptom (exact or near-exact message) | Likely cause | Discriminating experiment | Fix / detail |
|---|---|---|---|
| `Policy gate failed: this request requires content-read evidence...` | No source achieved `evidence_level='content_read'` — often a failed read of the intended file | In `agent_trace.jsonl`, find the evidence bundle: is the intended source present with `read_failed`? | § A |
| `Policy gate failed: required source read failed and was not recovered...` | A non-workspace source read failed and no matching content-read exists for the *same identity* | Compare failed vs succeeded source identities — a v3 read never recovers a v2 failure | § A, § B |
| `Policy gate failed: retrieved content does not match the user's source constraints.` | Wrong file read, or spurious inferred title phrase / scope | The message lists required phrases + scopes + read titles — check which side is wrong | § A |
| `Policy gate failed: source inventory contains item(s) outside the user's source constraints.` | Inventory listed off-title/off-scope rows | Same as above; check `Rejected source title(s)` in the message | § A |
| Retrieval found the wrong file entirely | Word-order-reformulated Graph query, lock stub, or dropped anchor | Check the search terms logged in `logs/sharepoint_mcp.log` vs the user's phrase | § B |
| `Stage retrieval_planner returned empty output` (or silent planner fallback) | Reasoning model emitted only reasoning tokens, empty final message | Grep trace for `RETRIEVAL_PLANNER FALLBACK` with `fallback_reason: empty_output` | § C |
| `Peer quality gate failed: judge did not accept the refined draft.` | Judge returned revise/rework/unknown after budgets exhausted | Grep trace for `PEER_FINAL_DECISION`, read `decision` + `reason_excerpt` | § D |
| MCP tool call hangs then dies at 240 s (or 60/120/600 s) | Server blocked on interactive auth, or genuinely slow work vs client timeout | Sub-second failure with "call login_sharepoint" = fixed path; a full-timeout hang = a new silent-auth gap | § E |
| `AADSTS7000218 ... client_assertion or client_secret` | Azure AD app registration disallows public client flows | This is not a code bug — check the Azure portal setting | § F |
| 404 on a SharePoint drive id / "policy violation" after handover | Model transcribed/invented a long raw Graph drive id | Does the failing handle start with `spdoc-`? If not, the model bypassed the ref registry | § F |
| Browser console shows CORS errors against the API | It is actually a 401 or 429 — CORS headers were historically stripped by middleware ordering | `curl -i` the same endpoint: if you get a clean 401/429, it is auth/rate-limit, not CORS | § G |
| Streaming output stops / falls back to completion-only | Python ≥ 3.14 with openai SDK ≤ 1.109.1 | Grep trace for `streaming_fallback` observability events | § H |
| DeepSeek agent stops using tools, or thinking disappears | Deliberate: thinking is disabled for tool-enabled agents when the LiteLLM adapter cannot replay reasoning content | Enable debug logging; look for "Disabling DeepSeek thinking for tool-enabled agent" | § I |
| A `registry/models.yaml` extra has no effect | LiteLLM adapter constructor does not accept it — dropped with only a DEBUG log | Log at DEBUG and look for "Ignoring unsupported LiteLLM model registry option(s)" | § J |
| Stray repo-root dirs named `--no-cov/`, `-q/`, `--collect-only/`, each holding `.auth/` | Every MCP server module treats `sys.argv[1]` as a workspace root at import time | `ls -a <dir>` — if it contains only `.auth/`, it is a dropping | § K |
| `crisai doctor --models` fails: `Missing required API key for provider 'openai'` | Shipped models set an explicit `base_url`, forcing eager client construction | Unset key + `--models` always fails; without `--models` it passes | § L |

## A. Run fails at a policy gate (content-read / title / scope / source-fit)

**The gates** (all in `src/crisai/cli/pipelines.py` as of 2026-07-02):

- `_validate_evidence_bundle` (line 582): when the task contract demands
  `required_evidence_level == "content_read"` (decided by
  `request_requires_content_read`, `orchestration/evidence_contract.py:346`, from the
  semantic registries — not hardcoded), the bundle must contain a content read, every
  non-workspace `read_failed` must be recovered by a content read of the **same source
  identity** (`_unresolved_required_read_failures`, line 671), and reads must satisfy
  inferred title-phrase AND source-scope constraints.
- `_enforce_source_inventory_fit` (line 642): inventory outputs must not list off-title
  rows. Mode-independent since PR #29 (`a49593c`) — it originally lived only in
  `run_single` and pipeline-routed inventory asks bypassed it.
- Constraints come from `infer_source_fit_constraints`
  (`orchestration/source_constraints.py`) — **message scraping**, a known precision risk.

**Triage order** when a gate fires:

1. **Was the right file even read?** If not, this is a retrieval failure — go to § B. The
   gate is the messenger, not the disease (Test001's real root cause was wrong-source
   continuation, not the lock stub the gate reported).
2. **Is a constraint spurious?** The failure message prints
   `Required title phrase(s): ...` and `Required source scope(s): ...`. Known trap classes:
   - *Output path became an input scope* (Test006, fixed in `2f41bec` #43): "save under
     workspace/…" used to make `workspace` a required **input** scope, rejecting a
     correctly-read OneDrive deck. `_output_destination_scope`
     (`source_constraints.py:74`) now filters the destination scope. If you see this
     again, check `output_path` is actually threaded into the inference call.
   - *Instruction words scraped as title phrases* (TODO-055, **open P1** as of
     2026-07-02): words like "linkable" can appear in `Required title phrase(s)`. When the
     user explicitly quotes the phrase, only the quote is trusted (`_quoted_phrases`,
     fixed in `b386a17` #42); unquoted messages can still produce noise.
3. **Discriminating experiment**: re-run with the title phrase in explicit quotes
   (`'...'` or `"..."`) in the user message. If the run now passes, the failure was
   constraint-inference noise (TODO-055 territory), not retrieval.
4. A completed run killed as `publish_artifact` when the user merely *referenced* a
   `.pptx`/`.docx` is the old bare-file-extension routing trap — fixed in `822a2fa`
   (`publication_terms` now holds produce-context phrases). If it recurs, the fix is a
   registry edit (`registry/semantic_catalog.yaml`), never Python.

**Do not** weaken or bypass a gate to make a run pass; the gates fail hard by design
(wrong-source continuation is named the top waste source in `reference/VISION.md`). Fix
the retrieval or the constraint inference instead, through change control
(**crisai-change-control**).

## B. Wrong source retrieved

Four distinct mechanisms — identify which one before touching anything:

| Trap | Story in one line | Discriminating test |
|---|---|---|
| Office lock stubs | `~$Deck.pptx` orphans impersonate the real deck once it drops out of the live Graph index; unreadable, so the gate kills the run (Test001/test003 defect C) | Any surfaced filename starting `~$` or `.~lock.` — should be impossible since `2455c1c` (#28): `_is_office_lock_stub` filters at the connector, **before** the result cap (`servers/sharepoint_server.py:257`). Seeing one means a new unfiltered code path. |
| Word-order sensitivity | OneDrive/Graph search is word-order sensitive: the model reformulated "UCL integration strategy" into "Integration UCL" and got unrelated files (Test005) | Compare the query string logged in `logs/sharepoint_mcp.log` with the user's phrase. Fixed in `b386a17` (#42): prompts instruct verbatim title-phrase queries. A reordered query in the log means the instruction is being ignored → needs a structural fix, not more prompt text. |
| Anchor starvation / wrong-source continuation | Turn 2 "compare the 2 versions" scored below the anchor resolver's title-restatement threshold, dropped the v2 anchor, and live-re-searched OneDrive from scratch (Test001; ADR-015) | Did turn 1 resolve the source and turn 2 re-search anyway? Check trace for a fresh search where a session anchor existed. Mitigations: logical-document dedup (`0cdd086` #26) and source materialisation (below). Restating more of the full title in the follow-up message is the operator-level workaround. |
| Peer planner competing search | In peer mode the retrieval planner still holds the source-search servers and can run its own competing (often wrong) search | **Known open gap, TODO-057 (P1) as of 2026-07-02**: pipeline mode strips `sharepoint_docs`/`documents`/`intranet` from the planner (`_framing_only_planner_spec`, `pipelines.py:1207`), peer mode uses the raw spec (`pipelines.py:1676`). A planner-stage SharePoint search in a peer trace is this gap, not a new bug. |

**Source materialisation** (ADR-015 2b): confirmed content-read sources are fetched once
and cached under `workspace/tasks/<session>/sources/` so later turns read a stable copy.
Opt-in via `CRISAI_MATERIALISE_SOURCES` (default **off** in code and `.env.example`;
**true in this machine's local `.env`** as of 2026-07-02 — behaviour observed locally is
not the shipped default). Best-effort: failures trace `SOURCE_MATERIALISE_ERROR` /
`SOURCE_MATERIALISE_SKIPPED` and never abort the run. If a follow-up turn re-queried live
OneDrive despite a prior read, first check the flag, then grep the earlier run's trace for
`SOURCE_MATERIALISED` — zero events in peer mode was exactly the Test007 finding fixed by
`841769e` (#44). Note the cache deliberately does **not** live under `.crisai/` — that
tree is invisible to agents by design; agent-consumable data must never be written there.

## C. Planner empty output

One line: reasoning-capable planner models (observed with the `openai_fast` ref) sometimes
generate hundreds of reasoning tokens but commit an **empty final message** (Test004);
this is valid model behaviour, not a crisAI bug.

- Both pipeline and peer paths now catch `Stage retrieval_planner returned empty output`
  and substitute a deterministic handoff: `_build_retrieval_planner_fallback`
  (`pipelines.py:322`; call sites 1222 pipeline, 1696 peer — peer parity from `0b63dbf` #39).
- **Discriminating test**: grep the trace for `RETRIEVAL_PLANNER FALLBACK` with
  `fallback_reason: empty_output`. Present → the run continued fine and needs no action.
  An *aborted* run with the empty-output message means a **different stage** hit the same
  behaviour — check which `Stage <agent_id> returned empty output` and note that only the
  planner has a fallback; other stages fail hard by design.
- If it happens constantly for one agent, the durable fix is a model assignment change in
  `registry/models.yaml` / `registry/agents.yaml` (user configuration), not code.

## D. Peer run hard-fails

`run_peer_pipeline` raises `WorkflowValidationError("Peer quality gate failed: judge did
not accept the refined draft. Run stopped before final recommendation.")`
(`pipelines.py:2126`) when the judge does not return `accept` after the refinement loop
(default max 2 rounds, `CRISAI_PEER_MAX_REFINEMENT_ROUNDS`) and escalation loop (default
max 1, `CRISAI_PEER_MAX_ESCALATIONS`) are exhausted. This is intended behaviour — peer
mode never returns a best-effort unaccepted draft.

Triage:

1. Grep trace for `PEER_FINAL_DECISION`: `decision` is one of
   `accept|revise|rework|unknown` (parsed in `orchestration/peer_judge.py`).
   `unknown` means the judge output could not be parsed as a decision — inspect the judge
   stage output text itself before blaming the draft.
2. `revise`/`rework` with sensible `reason_excerpt` → a genuine quality rejection; the
   input task or source grounding is the problem, not the machinery.
3. A *later* failure at `enforce_peer_final_deliverable_verification`
   (`orchestration/peer_verifier.py`) means the judge accepted but written workspace
   files failed grounding/placeholder checks (regex patterns such as
   `pattern_gap_line` and `leaf_file_pattern` live in
   `registry/semantic_catalog.yaml` under `peer_verifier:`; note the
   `[grounded details to be added` placeholder marker is currently hardcoded in
   `orchestration/peer_verifier.py:109`, not in the catalog).
   One repair round is attempted first.
4. Peer runs that fail at *retrieval* rather than judging: remember mode parity (§ B
   peer-planner gap; evidence repair and materialisation are present in peer since #39/#44).

## E. MCP tool hangs and timeouts

One line: an MCP stdio server that falls back to *interactive* auth blocks the whole agent
run until the client timeout fires — historically 240 s of dead silence (May 2026,
`f00411f`).

Current structure (as of 2026-07-02):

- Read tools use **silent-only** Graph auth and fail in under a second with a
  "call `login_sharepoint`" / "call `intranet_login`" hint (`sharepoint_server.py` wraps
  every `graph_get` with `silent_only=True`; `ms_graph.acquire_token_silent_only`).
  Interactive login is confined to the explicit login tools.
- Client session timeouts: default 60 s via `CRISAI_MCP_CLIENT_TIMEOUT_SECONDS`,
  **silently clamped to a minimum of 10 s** (`src/crisai/runtime.py:29` —
  `max(value, 10.0)`; you cannot set it lower). Per-server overrides in
  `registry/servers.yaml`: `documents` 120 s, `sharepoint_docs` 240 s, `intranet` 600 s.
- Changes to server code or timeouts take effect only after restarting the API
  (`./stop` then `./start api`) — the MCP subprocesses are respawned by the runtime.

Discriminating experiments:

| Observation | Meaning |
|---|---|
| Tool fails in <1 s with "call login_sharepoint" | Working as designed: token expired. Run the login tool (or the web UI SharePoint connect flow) and retry. |
| Tool hangs for the full per-server timeout | Either a genuinely long operation (e.g. scanned-PDF vision fallback — pages are processed in parallel but a big scan can still exceed the document server's budget, cf. `2d39490`) or a **new** code path that reached interactive auth without `silent_only` — grep the server module for a Graph call not going through the silent wrappers. |
| First tool call of a run times out at exactly the default | Heavy import stack (SharePoint + MSAL) beat the session timeout on `list_tools`; raise `CRISAI_MCP_CLIENT_TIMEOUT_SECONDS` or the server's `client_timeout_seconds`. |

## F. SharePoint / Graph auth failures

- **`AADSTS7000218` ("must contain client_assertion or client_secret")**: one line — three
  increasingly RFC-literate code fixes (ConfidentialClientApplication, raw RFC 8628 device
  flow, client_secret in both devicecode and token polling) were all dead ends; Azure AD
  does not support confidential-client device-code flow in this tenant at all. **The fix
  is the Azure portal, not code**: App registration → Authentication → Advanced settings →
  enable *"Allow public client flows"*. `ms_graph._build_app` always returns
  `PublicClientApplication` since `da4f4bd`; do not reintroduce client-secret auth paths
  for delegated flows. Discriminating test: the error appearing at all means the portal
  toggle is off for the app registration in use.
- **WSL2**: interactive localhost-redirect auth is broken under WSL2; device-code flow is
  used instead (`ms_graph.py` checks `WSL_DISTRO_NAME`). The device code is printed to
  stderr / surfaced in-terminal; the web UI has a non-blocking connect flow
  (`/api/v1/auth/sharepoint/start` + `/status`).
- **404 on a drive id / invented placeholder ids**: models corrupt ~66-char opaque base64
  Graph drive ids when transcribing them across handovers. Every search/list result now
  carries a short server-minted ref `spdoc-XXXXXXXX` resolved in a session-scoped registry
  (`sharepoint_server.py:_mint_ref`); legacy base64 handles still decode. Discriminating
  test: a failing handle that does **not** start with `spdoc-` means the model
  reconstructed a raw id from a link or prose — a prompt-contract violation the server is
  supposed to absorb; check `_decode_read_handle`'s placeholder rejection.
- Token caches live under `.tokens/` / `.auth/` (0600 files, 0700 dirs); both are
  deny-listed from workspace access. Never point `MS_TOKEN_CACHE_PATH` inside the
  workspace (`crisai doctor` warns).

## G. Browser 401/429 that look like CORS failures

One line: Starlette runs the most-recently-added middleware outermost; CORS was once
registered *before* the decorator-registered auth/rate-limit middleware, so 401/429
responses lost their `Access-Control-Allow-Origin` header and surfaced in the browser as
opaque CORS errors (`65389d3`).

- Current order (correct, `src/crisai/apps/web.py:226` `app.add_middleware(CORSMiddleware, ...)`
  registered last = outermost; the comment above it explains why): CORS answers preflight
  at the edge; auth (`_auth_middleware`, web.py:184) runs before rate limit
  (`_rate_limit_middleware`, web.py:151). **Do not reorder middleware** in `web.py`.
- Discriminating experiment: `curl -i -X POST http://127.0.0.1:8000/api/v1/runs ...` from
  the terminal. A clean JSON 401 (`WWW-Authenticate: Bearer`) → missing/wrong
  `CRISAI_API_KEY` bearer token (note: server checks only `CRISAI_API_KEY`; auth is a
  **no-op when it is unset**). A 429 with `Retry-After` → rate limit
  (`CRISAI_RATE_LIMIT_RPM`, default 0 = disabled; single global fixed window over
  `/api/run`, `/api/run/start`, `/api/v1/runs` POSTs only). A genuine CORS problem only
  exists if curl succeeds while the browser fails — then check `CRISAI_CORS_ORIGINS`
  (default allows only the two localhost:5173 origins).
- Note when a key is set, even OPTIONS is authenticated by the inner middleware — but
  browser preflight never reaches it because outermost CORS answers first. That is why
  the ordering matters.

## H. Streaming failures (Python 3.14)

One line: on Python ≥ 3.14 with openai SDK ≤ 1.109.1, streamed-response parsing is
known-broken, so the runtime silently falls back to non-streamed execution
(`_openai_streaming_construct_type_incompatible`, `src/crisai/cli/pipeline_display.py:179`).

- The repo pins Python 3.13 (`.python-version`) precisely to avoid the fallback, and has
  been on the openai 2.x SDK line since `a010c8f` (2026-07-01) — so as of 2026-07-02 the
  detector should never fire on a correctly bootstrapped environment.
- Discriminating test: stage output arriving only at completion (no deltas) + a
  `streaming_fallback` observability event (`fallback_reason:
  openai_streaming_construct_type_incompatible`) in the trace / UI events. If you see it,
  check `python --version` inside the venv (`uv run python --version`) — someone is
  running a 3.14 interpreter with an old openai package, i.e. a broken environment, not a
  code bug. Re-bootstrap (see **crisai-build-run-operate**).
- Streamed-vs-completion delivery is declared per stage in the `ui_stage_observability_v1`
  metadata, so the web UI degrades gracefully either way.

## I. DeepSeek thinking vs tools

One line: DeepSeek thinking mode and tool calls conflict unless the installed LiteLLM
adapter can replay `reasoning_content`, so the factory deliberately disables thinking for
tool-enabled DeepSeek agents when replay is unsupported (`agents/factory.py:136-170`).

- Mechanics: `deepseek_reasoner` in `registry/models.yaml` sets `thinking: enabled`,
  `reasoning_effort: max`, `should_replay_reasoning_content: always`. At build time, if
  the agent has MCP servers (tools) and the adapter lacks
  `should_replay_reasoning_content`, thinking is forced to `{"type": "disabled"}` and
  `reasoning_effort` is dropped — logged only at DEBUG.
- Discriminating test: a DeepSeek agent behaving as a plain non-reasoning model → run with
  debug logging and look for "Disabling DeepSeek thinking for tool-enabled agent because
  the installed LiteLLM adapter cannot replay reasoning_content." Present → upgrade the
  `openai-agents`/LiteLLM extra, or accept the trade-off; absent → check the model ref
  actually points at `deepseek_reasoner` (not `deepseek_fast`, which pins
  `thinking: disabled`).
- History: `226956e`/`c093052`/`43cd760` are the original thinking-vs-tool-calls fix
  train if you need the archaeology (→ **crisai-failure-archaeology**).

## J. Registry model extras silently dropped

One line: any extra key on a `registry/models.yaml` entry for a LiteLLM-routed provider
(gemini/anthropic/deepseek/local) is passed to the adapter **only if its constructor
signature accepts it**; unsupported keys are dropped with a DEBUG-level log
(`_supported_litellm_kwargs`, `agents/factory.py:93-114`; `724106d`/`be5dccb`).

- Discriminating test: set `CRISAI_LOG_LEVEL=DEBUG` (or the logging config equivalent) and
  look for "Ignoring unsupported LiteLLM model registry option(s): <keys>". At default
  INFO level you will see nothing — hence "silently".
- `thinking` and `reasoning_effort` are *not* constructor extras; they travel via
  ModelSettings (§ I). `api_key`, `base_url`, `model` are handled explicitly and cannot be
  overridden via extras.

## K. Stray `<flag>/.auth` directories at the repo root

One line: every MCP server module resolves `ROOT = Path(sys.argv[1])` **at import time**
(all eight modules under `src/crisai/servers/`, e.g. `sharepoint_server.py:29-34`) and
`sharepoint_server` then mkdirs `ROOT/.auth`, so importing the module under
`pytest <flag> ...` creates `<flag>/.auth/` at the repo root.

- Live, recurring, unfixed as of 2026-07-02. Existing droppings: `--no-cov/`, `-q/`,
  `--collect-only/`. They are safe to delete (each contains only an empty `.auth/`).
- Discriminating test: `ls -a <weird-dir>` → contains only `.auth/` → dropping.
- Avoidance: put the test path *before* flags, or better, avoid invoking pytest in ways
  that import server modules with a flag as `argv[1]`. Do not "fix" this ad hoc during an
  unrelated change — it is a real bug that deserves its own gated change
  (→ **crisai-change-control**).

## L. `crisai doctor` failures

- `doctor --models` dry-builds every agent (`factory.build_agent(agent, mcp_servers=[])`,
  `registry_validation.py:683-712`) and **requires `OPENAI_API_KEY` even though no API
  call is made**: every shipped OpenAI entry in `registry/models.yaml` sets an explicit
  `base_url` (`https://api.openai.com/v1`), which routes model resolution through the
  eager-credential path (`model_resolver.py:94-99`) instead of the SDK's lazy default
  client. Failure string: `Agent '<id>' model dry-build failed: Missing required API key
  for provider 'openai'`. Fix: put the key in `.env` (and remember `./start` sources
  `.env`, but a bare `uv run crisai doctor` relies on `load_dotenv()` in `config.py`).
- The same applies per provider: gemini/anthropic/deepseek refs require their
  `api_key_env`; only the `local` provider key is optional.
- `CRISAI_API_KEY is not set. All API endpoints are unprotected.` is a **warning**, not a
  failure — the deliberate local single-user default.
- Doctor also validates registry cross-references (tools in `allow` vs `internal`
  overlap, capability enums, session-memory strategy values, token-cache paths inside the
  workspace). A doctor failure after a registry edit is almost always the edit, not the
  environment.

## When NOT to use this skill

- You want to *measure* behaviour (trace anatomy, `crisai spend`, run JSONL
  interpretation, log-summarising scripts) → **crisai-diagnostics-and-tooling**.
- You want the full incident history — every investigation, dead end, and revert with
  commit evidence → **crisai-failure-archaeology**.
- You need the catalogue of env vars/flags with defaults and guards →
  **crisai-config-and-flags**.
- Setup/bootstrap problems, ports, `./start`/`./stop`, recreating the environment →
  **crisai-build-run-operate**.
- Test mechanics, exact pytest commands, coverage-gate quirks →
  **crisai-validation-and-qa** (and note the § K warning before running pytest at all).
- Turning a diagnosis into a landed fix (branch/PR/CI gating) → **crisai-change-control**.
- Tuning routing/intent classification via the registries →
  **crisai-semantic-registry-reference**.

## Provenance and maintenance

All claims verified against the working tree on 2026-07-02 (main @ `c39273b`). Line
numbers are the most drift-prone facts; re-verify with:

```bash
# Policy gates and planner scoping (§ A, § B, § C)
grep -n "_validate_evidence_bundle\|_unresolved_required_read_failures\|_enforce_source_inventory_fit\|_framing_only_planner_spec\|_build_retrieval_planner_fallback" src/crisai/cli/pipelines.py
grep -n "_output_destination_scope\|_quoted_phrases" src/crisai/orchestration/source_constraints.py
grep -n "TODO-055\|TODO-057" reference/TODO.md   # still open?
# Materialisation flag and cache location (§ B)
grep -n "CRISAI_MATERIALISE_SOURCES" src/crisai/cli/pipelines.py .env.example
# Peer hard gate (§ D)
grep -n "Peer quality gate failed" src/crisai/cli/pipelines.py
grep -n "CRISAI_PEER_MAX" src/crisai/orchestration/peer_judge.py
# Timeouts and silent auth (§ E)
grep -n "max(value, 10.0)" src/crisai/runtime.py
grep -n "client_timeout_seconds" registry/servers.yaml
grep -n "silent_only" src/crisai/servers/sharepoint_server.py
# Lock stubs and short refs (§ B, § F)
grep -n "_is_office_lock_stub\|_REF_PREFIX" src/crisai/servers/sharepoint_server.py
# AADSTS7000218 story (§ F)
git show da4f4bd -s   # revert body documents the Azure portal fix
# Middleware ordering (§ G)
grep -n "_auth_middleware\|_rate_limit_middleware\|add_middleware" src/crisai/apps/web.py
# Streaming fallback (§ H)
grep -n "_openai_streaming_construct_type_incompatible" src/crisai/cli/pipeline_display.py
cat .python-version
# DeepSeek and litellm extras (§ I, § J)
grep -n "Disabling DeepSeek thinking\|Ignoring unsupported LiteLLM" src/crisai/agents/factory.py
# argv[1] import-time bug (§ K)
grep -rn "sys.argv\[1\]" src/crisai/servers/
# Doctor model dry-build (§ L)
grep -n "_validate_model_dry_build" src/crisai/registry_validation.py
grep -n "base_url" registry/models.yaml
```

If a grep comes back empty or on a different line, trust the repo over this file and
update the entry.
