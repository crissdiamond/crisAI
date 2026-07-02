---
name: crisai-validation-and-qa
description: How to prove a crisAI change is correct — exact test/lint/typecheck commands as CI runs them, the pytest argv[1]/.auth side-effect trap, coverage gate vs actual, marker and conftest-stub pitfalls, the smoke-test network guard, the golden/certified test inventory (router golden set, TestNNN eval corpus, artefact profiles), how to add a test, and the commit-body evidence ledger. Load this before running tests, writing tests, interpreting a CI failure in the test job, validating Markdown artefacts, or deciding whether a change has enough evidence to commit.
---

# crisAI validation and QA

Runbook for proving changes in this repo. Facts verified against the repo on
2026-07-02; volatile numbers are date-stamped. TESTING.md exists but is stale in
several places (see "Known documentation staleness" below) — when it disagrees
with `pyproject.toml` or `.github/workflows/ci.yml`, the config files win.

## What counts as evidence for a change

The bar, enforced by convention in every recent merged PR, is all four of:

1. **Full suite green** — `uv run pytest` from repo root, zero failures.
2. **Lint clean** — `uv run ruff check src/ tests/`.
3. **Types clean** — `uv run mypy src/`.
4. **A named reproduction** — the specific failing case the change fixes,
   ideally a TestNNN task session (see corpus below) or a new test that fails
   before the change and passes after.

Record the result in the commit body as a ledger line. Real examples from
merged commits (verify with `git log -1 --format=%B 2f41bec`):

> Tests cover the destination-scope exclusion in isolation and the Test006
> author-from-external-source case. Full suite green (862 passed; ruff + mypy clean).

> Tests: run_peer_pipeline invokes the materialiser for the confirmed read
> sources ... Full suite green (863 passed; ruff + mypy clean).

The pattern: name what the new tests assert, name the reproduction
(Test006/Test007 above), state the passed count, state ruff + mypy clean. The
passed count doubles as a regression tripwire — a reviewer seeing the count
*drop* between commits should ask why. CLAUDE.md additionally requires adding
or updating tests under `tests/` for any changed/added/removed tested
behaviour, and running the relevant tests after changing covered code.

## Exact commands, as CI runs them

CI is one workflow, `.github/workflows/ci.yml`, three jobs. The **test** job is
a matrix over Python 3.10, 3.11, 3.12, 3.13, 3.14 (`fail-fast: false`,
`timeout-minutes: 15`) and runs, in order:

```bash
uv sync --locked --extra litellm --group dev
uv run ruff check src/ tests/
uv run mypy src/
uv run crisai doctor          # registry validation gate
uv run pytest -q
```

Local canonical equivalent (drop `--locked` only if you intend to update the lockfile):

```bash
uv sync --extra litellm --group dev
uv run pytest
```

Both flags are required: the `dev` dependency group holds pytest/ruff/mypy
(PEP 735 `[dependency-groups]`, pyproject.toml:41-53); the `litellm` extra is
needed by the default multi-provider registry. Default pytest `addopts` are
`--cov=crisai --cov-report=term-missing` (pyproject.toml:60), so coverage is
always measured unless you pass `--no-cov` — but read the trap section before
passing any flag.

The **security** job (bandit, pip-audit with **zero suppressions**, gitleaks)
and the **ui** job (`npm --prefix ui ci` / `run typecheck` / `build:web` /
`build:gem`, Node 24) also gate merges; their internals belong to
crisai-change-control. What matters here: the ui job runs **no UI unit tests**
(see below), and the test job runs everything 5x, once per Python version.

Focused runs (each creates a `.auth/` dropping at the path you name — see trap):

```bash
uv run pytest tests/unit                    # 720 tests as of 2026-07-02
uv run pytest tests/unit/test_router_regression.py
uv run pytest tests/orchestration
uv run pytest tests/integration
```

Suite shape, verified by listing on 2026-07-02: 84 test files —
`tests/unit` 72, `tests/cli` 5, `tests/integration` 3, `tests/orchestration` 3,
`tests/smoke` 1. A full run on 2026-07-02 collected 904 tests: 893 passed,
11 skipped (10 smoke tests behind the network guard + 1 manual Graph login
test in `tests/orchestration/test_graph_login.py`). The suite is intentionally
network-free except `tests/smoke/`.

## TRAP: any pytest argument becomes a directory (argv[1]/.auth bug)

Live, unfixed as of 2026-07-02. All eight MCP server modules under
`src/crisai/servers/` compute, **at import time**:

```python
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
```

and `sharepoint_server.py:29-34` then does `ROOT.mkdir(...)` plus
`(ROOT / ".auth").mkdir(...)`. Unit tests import these modules (e.g.
`tests/unit/test_sharepoint_onedrive_search.py` imports
`crisai.servers.sharepoint_server`), and under pytest `sys.argv[1]` is
whatever you typed first after `pytest`. Consequences, all observed in this
working copy:

| You run | Repo mutation |
|---|---|
| `uv run pytest` (no args) | `.auth/` at repo root (cwd fallback) |
| `uv run pytest -q` (CI's own command) | `-q/.auth/` in the working dir |
| `uv run pytest tests/unit` | `tests/unit/.auth/` |
| `uv run pytest --no-cov ...` | `--no-cov/.auth/` at repo root |
| `pytest --collect-only -q` | `--collect-only/.auth/` |

The droppings are gitignored (`.auth/` matches at any depth, .gitignore:51),
so `git status` stays clean and they silently accumulate. They are safe to
delete:

```bash
rm -rf -- ./--no-cov ./-q ./--collect-only tests/unit/.auth
```

(crisai-diagnostics-and-tooling ships a cleanup script.) Until the import-time
side effect is fixed, prefer plain `uv run pytest` from the repo root, and know
that any path/flag argument litters — including in CI, where `-q/` is created
ephemerally on every run. Do not "fix" this by reordering arguments in scripts
without also cleaning up; fix the root cause (defer `ROOT` resolution past
import) through normal change control.

## Coverage: the gate is 15 points below reality

- Gate: `fail_under = 70` (pyproject.toml:70), source `crisai`, omit
  `*/tests/*`, `*/__init__.py`, `*/web/app.py` (pyproject.toml:65-67).
- Actual: **85.25% total** on a full run dated 2026-07-02.

Consequence, stated plainly: **a 15-point coverage regression can merge without
failing CI.** The gate only catches catastrophic coverage loss. Reviewers must
read the `term-missing` output for the files they touched rather than trusting
the green gate. Also note the omit pattern `*/web/app.py` matches **no file**
(the web app is `src/crisai/apps/web.py`, which IS measured, ~87%); it is
vestigial config from an older layout — do not copy the pattern as precedent.

Worst-covered areas as of 2026-07-02 (from the same run):
`apps/ui_config.py` 0% (trivial frozen dataclass), `ms_graph.py` 51% (auth
paths covered only by the always-skipped manual test), `cli/main.py` 60%
(interactive loop), `logging_utils.py` 69%, `cli/display.py` 70%,
`workspace/safety.py` 77% (security-relevant gaps).

## Markers, async, timeouts — the sharp edges

- **Only one registered marker: `smoke`** (pyproject.toml:61-63).
- `@pytest.mark.anyio` is used 84 times across the suite but is **not
  registered**, and `--strict-markers` is **off** — so a typo'd marker name
  (e.g. `@pytest.mark.aynio`) raises no error and silently changes behaviour
  (an async test without a working anyio mark can pass as a no-op coroutine).
  When adding async tests, copy the marker from an existing file, never retype it.
- The anyio pytest plugin comes from **anyio as a transitive dependency** —
  `anyio` appears nowhere in pyproject.toml (verified), only in uv.lock. A
  dependency shuffle that drops it would break every async test. Default
  asyncio backend; no `anyio_backend` fixture override exists.
- **No global test timeout is configured.** `pytest-timeout` is installed
  (dev group) but no `--timeout` appears in addopts or CI. The only
  `@pytest.mark.timeout(...)` marks live in `tests/smoke/test_smoke.py`
  (15/120/300s), and smoke tests skip in CI. CI's only hang protection is the
  job-level `timeout-minutes: 15`. TESTING.md:203 claims per-test timeouts in
  CI — that claim is false.

## TRAP: the conftest agents-SDK stub

`tests/conftest.py:15-55` installs a stub `agents` module (no-op `Agent`, a
`Runner.run` that raises `NotImplementedError`) and a stub `agents.mcp`
(`MCPServerStdio`, `create_static_tool_filter`) **whenever the real
openai-agents SDK fails to import**. Intent: optional extras must not break
collection. Side effect: in a broken or partially-synced environment the suite
can **silently run against stubs instead of the real SDK**, masking import
breakage while staying green. Before trusting a local run in a freshly
built or modified environment, verify the real SDK is in play:

```bash
uv run python -c "import agents, agents.mcp; print(agents.__file__)"
```

If that errors (or prints a path outside `.venv`), your pytest results
exercised the stubs. Re-run `uv sync --extra litellm --group dev` first.

## Smoke tests and the network guard

`tests/smoke/` (10 tests, 1 file) is the **only** part of the suite allowed to
touch the network, and the guard is a single env var:

- `CRISAI_RUN_SMOKE_TESTS=1` — without it, every smoke test skips
  (`tests/smoke/conftest.py:53-56`, `require_smoke()`).
- Per-provider keys additionally gate provider tests
  (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`,
  `DEEPSEEK_API_KEY`); missing keys skip, not fail.

```bash
set -a; . ./.env; set +a          # keys live in .env; export them to the shell
CRISAI_RUN_SMOKE_TESTS=1 uv run pytest tests/smoke
```

Know what you are opting into: `test_provider_endpoint_is_reachable` opens a
**raw TCP connection** to each provider host (`socket.create_connection`,
test_smoke.py:63), and the remaining tests make real, billed LLM calls using
the cheapest configured model ref per provider (`openai_nano`, `gemini_fast`,
`anthropic_fast`, `deepseek_fast`). The guard env var is the only thing keeping
`pytest tests/smoke` network-free. Smoke fixtures load the REAL registry with
empty `server_specs` so agents run tool-less (`smoke_registry`,
tests/smoke/conftest.py:86-98), and assert on `logs/agent_trace.jsonl` via
`read_trace`/`assert_stage_traced`. CI never sets the guard, so smoke tests
skip in CI by design.

The manual Microsoft Graph login check is separate and never runs under pytest:
`uv run python tests/orchestration/test_graph_login.py` (interactive Entra login).

## UI tests exist but do NOT run in CI

As of 2026-07-02 there are 5 UI unit-test files, all runnable, none wired into CI:

- `ui/apps/web/test/{editorRegistry,frontMatter,runDisplay,yamlLint}.test.ts`
- `ui/apps/gem/test/viewModel.test.ts`

Runner is `tsx --test` (Node's built-in test runner) via each app's `test`
script (`ui/apps/web/package.json:9`, `ui/apps/gem/package.json:13`). The root
`ui/package.json` has **no** `test` script, and CI's ui job runs only
`typecheck` + `build:web` + `build:gem`. Run them yourself:

```bash
npm --prefix ui run test --workspace @crisai/web
npm --prefix ui run test --workspace @crisai/gem
```

(`ui/` is an npm workspaces root: `packages/*`, `apps/*`.) Consequence: a UI
behaviour regression that typechecks and builds will merge with green CI. If
you change web/gem runtime behaviour, running these tests locally and saying so
in the commit body is the only evidence anyone gets. Wiring them into ci.yml is
an open improvement (tracked as a TODO-027 concern), not something to do as a
drive-by.

## Golden / certified inventory

There are no non-`.py` fixture data files under `tests/` (verified with find).
The "golden" assets are:

### 1. Router golden set — `tests/unit/test_router_regression.py`

`GOLDEN_CASES`: 28 `(query, expected_intent, expected_mode)` tuples,
parametrised, run against the **real** `registry/semantic_catalog.yaml`.
Only the deterministic source **nudge** is suppressed (monkeypatched
`_deterministic_source_nudge` + `registry_dir=None`); task contracts still
load the real `registry/semantic_graph.yaml` via the settings fallback in
`task_contract.py:_resolve_registry_dir`, so the golden set exercises catalog
terms AND graph intent emits (see crisai-semantic-registry-reference §10 —
the test file's own docstring understates this). This is the regression net
for any semantic-catalog, semantic-graph, or router edit. Per its own docstring: *adding a new routing path = append a tuple to
GOLDEN_CASES and verify it passes.* A catalog edit that flips an existing
golden case is a finding, not a test to update casually — see
crisai-semantic-registry-reference for how routing terms are owned.

### 2. Registry example alignment — `tests/unit/test_registry_examples.py`

Asserts every `registry/examples/agents.*.yaml` (openai, gemini, anthropic,
deepseek, local) carries exactly the live `registry/agents.yaml` agent IDs,
valid `model_ref`s, and matching `allowed_servers`. Adding/renaming an agent
means updating all five example files or this test fails.

### 3. The TestNNN task corpus — `workspace/tasks/Test001..Test007` (de facto)

Live eval corpus no doc names. On this machine as of 2026-07-02:
`Test001`–`Test007` (plus lowercase `test003`, `NewTest-02..05`, `NewTests-01`)
each hold `.crisai/` session state with `runs/*.json` run records, plus
`artefacts/ exports/ inputs/ scratch/`. These are the "named reproductions"
cited in commit bodies: Test006 is the reproduction behind 2f41bec (gate:
output destination leaked into source requirements), Test007 behind 841769e
(peer-mode materialisation gap). **The corpus is local-only**:
`workspace/tasks/*/` is gitignored (.gitignore:81), so it does not exist in a
fresh clone and cannot be assumed in CI — it is evidence you re-run
interactively, not an automated suite. Treat these dirs as read-only history;
building a durable, versioned eval baseline from them is exactly the
crisai-eval-baseline-campaign scope (TODO-051).

### 4. Artefact profile validation — `crisai validate-artefacts`

Declarative structural validation of Markdown artefacts against
`registry/workspace_artifact_profiles.yaml`:

```bash
uv run crisai validate-artefacts                       # scan knowledge, knowledge_staging, tasks roots
uv run crisai validate-artefacts -p workspace/knowledge_staging/patterns/foo.md   # specific file(s)
```

CLI command at `src/crisai/cli/main.py:452`; engine
`src/crisai/workspace/artefact_validation.py`
(`validate_workspace_artefact_paths`). Semantics (from the profiles file):
profiles evaluate **top-to-bottom, first full match wins**, else
`defaults.rules` (front matter `id/title/type/status` required, ≥1 H2).
`type_aliases` let authors write `type: HLD` and match `high_level_design`
rules. Notable profiles: templated task artefacts (front matter
`template_path` ⇒ required H2 sections come `from_template` and
`placeholder_policy: error`), integration pattern leaf (7 required H2 sections
+ slug dedup builtin check), option_paper/decision/strategy/etc. section
contracts. Exit code 0/1 — usable as a gate in scripts. Covered by
`tests/unit/test_artefact_validation.py` and `test_artefact_lifecycle.py`.
This command is part of the knowledge staging→promotion loop; the loop itself
is documented in the operator manual (DOCUMENTATION.md §12), not here.

## How to add a test

1. **Pick the directory by kind**, matching the existing taxonomy:
   `tests/unit/` (network-free, monkeypatch/fake-based — the default),
   `tests/cli/` (CLI main/pipelines/workflow_support), `tests/orchestration/`
   (mode sequencing), `tests/integration/` (multi-component but still
   fake-backed, no network), `tests/smoke/` (real provider APIs only —
   must carry `@pytest.mark.smoke` and call `require_smoke()` /
   `require_providers(...)` so it skips without the guard).
2. **Never open the network** outside `tests/smoke/`. The suite's design
   contract (TESTING.md §6, still accurate on this point) is
   network-free-by-default; optional extras must not break collection.
3. **Reset module-level state with autouse fixtures.** The web app keeps
   process-global dicts; existing patterns to copy:
   `_RUN_JOBS` reset (`tests/unit/test_web_app.py:46`,
   `tests/integration/test_web_integration.py:35`) and `_RATE_LIMIT_STATE`
   reset (`tests/integration/test_web_integration.py:44`). Env isolation via
   `mock.patch.dict("os.environ", {...}, clear=True)` autouse
   (`tests/unit/test_config.py:25`). If you add module-level mutable state to
   `src/`, ship the matching autouse reset fixture with the first test.
4. **Async tests**: copy `@pytest.mark.anyio` from an existing file (marker is
   unregistered and unchecked — see sharp edges above). No backend fixture;
   asyncio default.
5. **Routing behaviour change** ⇒ append to `GOLDEN_CASES`
   (test_router_regression.py). **Agent/model registry change** ⇒ update
   `registry/examples/agents.*.yaml` (test_registry_examples.py enforces).
   **Artefact shape change** ⇒ edit `registry/workspace_artifact_profiles.yaml`
   plus `tests/unit/test_artefact_validation.py`, not Python.
6. **Monkeypatch seams**: judge and evidence helpers are patched via their own
   modules (`crisai.orchestration.peer_judge` / `peer_evidence`), not via
   `pipelines` (TESTING.md §8, accurate).
7. Coverage of new code counts toward the 70% gate automatically
   (`--cov=crisai` is in addopts); aim to keep the file you touched at or
   above its current percentage, since the global gate will not catch you.

## Known documentation staleness (TESTING.md)

TESTING.md was last changed 2026-06-12 (`git log -1 -- TESTING.md` → 8beb7ce)
and is stale in several places — the full staleness inventory is owned by
**crisai-docs-and-writing §7**. The test-command consequences to remember here:

- Do NOT copy TESTING.md §4's local pip-audit command: its four
  `--ignore-vuln` suppressions run a weaker audit than CI, which has run with
  no suppressions since `a010c8f` (2026-07-01).
- Do not rely on a per-test timeout to catch hangs: despite TESTING.md:203, no
  `--timeout` is configured anywhere; the job-level `timeout-minutes` in
  ci.yml is the only hang protection.
- Treat TESTING.md §2's test-file listing as illustrative, never authoritative
  (~19 files behind the 72 on disk).

Do not propagate these claims. Fixing TESTING.md is a docs change — see
crisai-docs-and-writing for doc-of-record maintenance rules.

## When NOT to use this skill

- **Building the TODO-051 evaluation/acceptance baseline** (turning the TestNNN
  corpus into a measured quality gate) → crisai-eval-baseline-campaign.
- **Change gating, branch/PR/squash discipline, CI-as-merge-blocker policy,
  commit-message rules** → crisai-change-control (this skill only defines what
  test evidence goes in the commit body).
- **Triaging a runtime failure** (a run misbehaving, not a test failing) →
  crisai-debugging-playbook; measuring behaviour via traces/spend/run JSONLs →
  crisai-diagnostics-and-tooling (including the stray-`.auth` cleanup script).
- **Editing router terms / semantic vocabulary** the golden set exercises →
  crisai-semantic-registry-reference.
- **Environment setup, ./start & ./stop, keys, ports** → crisai-build-run-operate.
- **UI architecture and the manual Python↔TS contract sync risk** →
  crisai-ui-surfaces (this skill only covers that UI tests are not in CI and
  how to run them).
- **Proof recipes and evidence methodology beyond test mechanics** →
  crisai-proof-and-analysis-toolkit / crisai-research-methodology.

## Provenance and maintenance

All claims verified against the working tree on 2026-07-02. Re-verify before
trusting the volatile ones:

```bash
grep -n "addopts\|fail_under\|markers" pyproject.toml                          # addopts, 70% gate, smoke-only marker
grep -n "pytest -q\|ruff check\|mypy src\|crisai doctor\|python-version" .github/workflows/ci.yml   # CI commands + matrix
ls tests/unit/*.py | wc -l                                                     # unit file count (72 on 2026-07-02)
python3 -c "import ast; t=ast.parse(open('tests/unit/test_router_regression.py').read()); print([len(n.value.elts) for n in ast.walk(t) if isinstance(n, ast.AnnAssign) and getattr(n.target,'id','')=='GOLDEN_CASES'])"   # golden case count (28) — do NOT use a naive grep: two fixture lines elsewhere in the file also start with '('
sed -n '29,34p' src/crisai/servers/sharepoint_server.py                        # argv[1]/.auth bug still present?
ls -d ./--no-cov ./-q ./--collect-only .auth tests/unit/.auth 2>/dev/null      # current droppings
grep -rn "sys.argv\[1\]" src/crisai/servers/ | wc -l                           # bug spread (8 modules on 2026-07-02)
grep -n "CRISAI_RUN_SMOKE_TESTS" tests/smoke/conftest.py                       # network guard env var
grep -n '"test"' ui/apps/web/package.json ui/apps/gem/package.json            # UI test scripts exist
grep -n "run test" .github/workflows/ci.yml                                    # still absent from CI? (empty = yes)
ls workspace/tasks | grep -i "^test"                                           # TestNNN corpus presence (local-only)
git log -1 --format="%h %ad" --date=short -- TESTING.md                        # TESTING.md staleness clock
grep -n "ignore-vuln" TESTING.md .github/workflows/ci.yml                      # doc-vs-CI pip-audit drift
grep -rn "mark.anyio" tests | wc -l                                            # anyio marker usage (84 on 2026-07-02)
grep -n "anyio" pyproject.toml                                                 # still transitive-only? (empty = yes)
```

Numbers that WILL drift: test counts (904 collected / 893 passed / 11 skipped),
coverage (85.25%), unit-file count (72), golden-case count (28), anyio-mark
count (84) — all measured 2026-07-02. The structural facts (argv trap, stub
trap, guard env var, unregistered anyio marker, UI-tests-not-in-CI, 70% gate)
hold until someone fixes them; check the one-liners above before relying on
any of them in a review.
