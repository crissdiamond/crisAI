---
name: crisai-devteam-operations
description: Operating the hcom multi-agent development team that builds crisAI itself (dormant but live, intended for revival). Load when the task mentions hcom, scripts/hcom_*.sh, ./start hcom, the tmux session crisai-hcom, development-team/ or reference/development/, agent_roster.yaml, Codex/Claude/Antigravity dev agents or reviewers (cris/lina/luke/bili/alex/lori/alle), the single-git-writer rule, review leases, or reviving/attaching/stopping/resuming the dev team. NOT for the product's runtime agents (registry/agents.yaml) or the solo PR flow.
---

# crisai-devteam-operations

Runbook for the **hcom multi-agent development team** — the tmux-orchestrated
apparatus of Codex/Claude coding agents that built much of this repository
during May 2026. Status as of 2026-07-02, owner-confirmed: **DORMANT BUT
LIVE** — no team session has run since 2026-05-24, but the owner intends to
revive it. This skill documents how to operate it today, alongside (not
instead of) the current solo branch→PR→squash flow owned by
`crisai-change-control`.

**Critical disambiguation — two unrelated agent systems share this repo:**

| System | Roster | Purpose |
|---|---|---|
| Runtime product agents (~15: orchestrator, retrieval_planner, design, judge, …) | `registry/agents.yaml` + `prompts/` | What crisAI *does* for its users. See `crisai-architecture-contract`. |
| hcom development team (this skill) | `reference/development/agent_roster.yaml` + `reference/development/roles/` | How crisAI *gets built*: Codex/Claude dev agents in tmux |

A newcomer grepping "agents" or "orchestrator" will conflate them. The hcom
team never appears in README.md, DOCUMENTATION.md, or CLAUDE.md (verified
2026-07-02: zero mentions) — it is documented only under
`reference/development/` and `development-team/`, and now here.

## 1. What hcom is

`hcom` is an **external CLI** (installed on this machine at
`~/.local/bin/hcom`, present as of 2026-07-02; not part of this repo) that
launches provider coding CLIs — `codex` (OpenAI Codex), `claude` (Claude
Code), `agy` (Antigravity) — as named, tagged agent sessions, and gives them a
shared coordination layer: short messages on threads, file/event "bundles",
session listing/killing/resume, and terminal placement. Repo scripts drive it
with calls like `hcom <provider> --tag <t> --dir <d> --hcom-prompt <p> --go`,
`hcom list --json`, `hcom r <session-id>` (resume), and
`hcom kill "tag:<t>"`. Its state lives in `HCOM_DIR` (default `./.hcom`,
gitignored). hcom's own behaviour may have changed since the scripts were
last touched (2026-05-24) — see the revival fence in §8.

The team shape (default `codex-dev` profile):

- **One orchestrator** (Codex) — the only role with git write authority.
- **Three area developers** (Codex): runtime, gem, web.
- **Paired reviewers** (Claude Code by default) — ephemeral, launched on
  demand by the orchestrator as **mandatory gates** for review-required work.
- **Claude memory MCP** as the shared durable context layer (writes are
  best-effort; on denial, agents put the intended summary in their hcom
  handoff and continue).
- **tmux** session `crisai-hcom` as the managed terminal default.

An alternate profile `claude-dev-codex-review` inverts providers: Claude Code
orchestrator + area developers, persistent Codex reviewers.

## 2. Roster, names, and ownership

Source of truth: `reference/development/agent_roster.yaml` (roles, providers,
launch dirs, tags, ownership, shared rules) and
`reference/development/roles/*.md` (14 role bootstrap prompts). Stable base
names come from `reference/development/team_names.yaml`; hcom combines them
with tags (e.g. `crisai-gem-lina`).

| Role (codex-dev profile) | Provider | Name | Tag | Owns (writes) |
|---|---|---|---|---|
| orchestrator_codex | codex | cris | crisai-orchestrator | cross-area integration, `reference/`, README/DOCUMENTATION/TESTING, `registry/`, `scripts/`; ALL git metadata writes |
| runtime_codex | codex | bili | crisai-runtime | `src/crisai/`, `registry/`, `prompts/`, `tests/` |
| gem_codex | codex | lina | crisai-gem | `ui/apps/gem/`, `ui/packages/contracts/` when assigned, tests |
| web_codex | codex | luke | crisai-web | `ui/apps/web/`, `ui/packages/contracts/` when assigned, tests |
| runtime_claude (reviewer, ephemeral) | claude | alle | crisai-runtime-review | small focused patches only when requested |
| gem_claude (reviewer, ephemeral) | claude | alex | crisai-gem-review | ditto |
| web_claude (reviewer, ephemeral) | claude | lori | crisai-web-review | ditto |

Alternate `claude-dev-codex-review` profile: `orchestrator_claude` (cris),
`runtime_claude_dev` (alle), `gem_claude_dev` (alex), `web_claude_dev` (lori)
as developers via Claude Code (`HCOM_TEAM_CLAUDE_CODE_MODEL`, default
`claude-sonnet-4-6`), plus **persistent** `runtime_codex_review` (bili),
`gem_codex_review` (lina), `web_codex_review` (luke).

Shared rules (`agent_roster.yaml` `shared_rules:`): commit/git-write owner is
`orchestrator_codex` (alternate profile: `orchestrator_claude`); area agents
have **read-only git access**; `push_policy: explicit-user-request-only`;
reviewers are mandatory gates for review-required work — if a required
reviewer cannot launch, the task pauses unless the user explicitly overrides.

Shared files (`registry/*`, `prompts/*`, README.md, DOCUMENTATION.md,
`ui/packages/contracts/*`) need explicit orchestrator ownership per task.
Role prompts also enforce the repo's registry-owned-semantics and
structured-contract rules (see `crisai-change-control`).

### The single-git-writer rule, and its one recorded breach

Only the orchestrator may run git commands that write `.git` metadata
(`add`, `commit`, `fetch`, `pull`, `push`, branch/merge/rebase/tag). Area
agents hand off changed files + checks + a suggested Conventional Commit
message. The orchestrator launches with sandbox `danger-full-access`
(`HCOM_TEAM_ORCHESTRATOR_CODEX_SANDBOX`) precisely so `.git` is writable;
area Codex agents get `workspace-write`.

Recorded breach (`reference/development/newtest-04-restart-handoff.md`,
2026-05-19): the runtime area agent committed `e36be9c` and `cc21f45` to main
despite the rule. The orchestrator noted the process breach and **did not
revert** because the commits were already on `main`/`origin/main`, in scope,
and CI was green. Precedent: the rule is a process control, not a technical
one — enforcement is the sandbox profile plus review, and a breach with green
CI was tolerated rather than rewritten.

## 3. The two diverged copies — which is live

Two copies of the operating model exist. **Verified by diff and git log,
2026-07-02:**

| Copy | Role | Last commit touching it |
|---|---|---|
| `reference/development/` | **LIVE.** The root `scripts/hcom_*.sh` hardcode its paths (role files, `team_names.yaml`, `session_assignments.local.yaml`) | 34c71ab, 2026-05-24 |
| `development-team/` | **PACKAGED, STALE.** Self-contained copy meant to be extracted into its own repo; its scripts take `--target-repo /path/to/crisAI` | 16b7f64, 2026-05-22 |

Divergence (from `diff -rq development-team/reference/development
reference/development`): the live copy has 7 extra role files (the whole
`claude-dev-codex-review` profile: `orchestrator_claude.md`, `*_claude_dev.md`,
`*_codex_review.md`), plus live-only `README.md`, `team_names.yaml`,
`review_provider_design.md`, `newtest-04-restart-handoff.md`, and the
gitignored `session_assignments.local.yaml`. `agent_roster.yaml`,
`operating_model.md`, `review_providers.yaml`, and shared role files all
differ in content. Of the 13 scripts in `development-team/scripts/`, 10
differ from their `scripts/` twins (only `hcom_attach.sh`,
`hcom_tmux_command.sh`, `hcom_tmux_terminal.sh` are byte-identical), and
`scripts/` has two extras (`hcom_antigravity_home.sh`,
`hcom_antigravity_model.sh`).

**Rule: operate from `scripts/hcom_*.sh` + `reference/development/`. Treat
`development-team/` as a packaging artefact** — never launch from it inside
this repo without `--target-repo /home/diamond/crisAI` (without that flag the
packaged script treats its own checkout as the target).

## 4. Context folders: gem/, web/, runtime/ are NOT source roots

Top-level `gem/`, `web/`, `runtime/` are **hcom context folders** — each
holds only a README (plus stray `logs/` residue in `runtime/` and `web/`)
that states the area's ownership and pointers. Agents launch **from the repo
root** (roster `launch_dir: "."`) so the Codex workspace-write sandbox covers
the files they own; the context folder is labelling only. The real code:

- Gem terminal client → `ui/apps/gem/` (Ink)
- Web client → `ui/apps/web/` (React/Vite)
- Runtime → `src/crisai/` (+ `registry/`, `prompts/`)

Do not put source in these folders and do not go looking for the Gem app in
`gem/`.

## 5. Launch, attach, status, stop

> **Unverified-runnable:** every command in §5–§7 was verified against the
> script text on 2026-07-02 but **not executed** — no team session has run
> since 2026-05-24 and the scripts predate the June repo/process changes
> (§8). Do a `--dry-run` first and read §8 before a real launch.

Via the `./start` helper (parses `.env` first, then dispatches):

```bash
./start hcom                     # start or resume the default codex-dev team
./start hcom all-up              # + persistent reviewers (lifecycle=persistent)
./start hcom agy                 # reviewers via Antigravity (Claude model profile)
./start hcom agy gemini          # reviewers via Antigravity, Gemini model profile
./start hcom all-up agy          # persistent Antigravity reviewers
./start hcom claude-dev          # inverted profile: Claude devs + persistent Codex reviewers
./start hcom -- --dry-run        # everything after -- goes to hcom_start.sh
./start hcom-attach              # attach to the crisai-hcom tmux session
```

`./start hcom` resumes only when `session_assignments.local.yaml` contains
all roles of the *requested profile*; otherwise it launches fresh. As of
2026-07-02 the saved file (stopped_at 2026-05-24T11:51Z) holds the 7
**claude-dev profile** roles — so `./start hcom` (codex-dev) will start
fresh, while `./start hcom claude-dev` will try to `--resume` five-week-old
sessions (missing sessions fall back to a fresh launch per role).

Direct script invocation (for flags `./start` doesn't expose):

```bash
scripts/hcom_start.sh --dry-run              # print launch commands, launch nothing — do this first
scripts/hcom_start.sh                        # fresh codex-dev team
scripts/hcom_start.sh --resume               # resume saved sessions (same context only)
scripts/hcom_start.sh --headless             # no terminal panes
scripts/hcom_start.sh --no-tool-auto-approve # keep interactive permission prompts
scripts/hcom_start.sh --terminal 'wt.exe -w 0 new-tab --title hcom -- wsl.exe -d <distro> bash {script}'
scripts/hcom_status.sh                       # assignments file + `hcom list -v`
scripts/hcom_attach.sh                       # attach to tmux (prints key help)
scripts/hcom_stop.sh                         # snapshot resumable session IDs, kill all team tags + tmux session
```

`hcom_start.sh` writes generated assignments to
`reference/development/session_assignments.local.yaml` (gitignored).
`hcom_stop.sh` re-snapshots that file (session IDs, transcript paths,
`status: stopped`) *before* killing tags — that snapshot is what makes
`--resume` work later. `./stop` (repo root) is unrelated: it kills only the
product API/web dev processes, never hcom.

tmux: session `crisai-hcom` (override `HCOM_TEAM_TMUX_SESSION`); prefix is
`Ctrl-\` (`Ctrl-b` secondary): `Ctrl-\ 0..6` jump to an agent window,
`Ctrl-\ w` window list, `Ctrl-\ n/p` next/previous, `Ctrl-\ d` detach without
stopping. Default window order: `orchestrator(cris)`, `gem_codex(lina)`,
`web_codex(luke)`, `run_codex(bili)`; persistent-reviewer mode adds
`gem_claude(alex)`, `web_claude(lori)`, `run_claude(alle)`.

### Environment variables (all read by `scripts/hcom_start.sh` unless noted)

| Variable | Default | Effect |
|---|---|---|
| `HCOM_DIR` | `./.hcom` | hcom state dir (gitignored) |
| `HCOM_TEAM_PROFILE` | `codex-dev` | or `claude-dev-codex-review` |
| `HCOM_TEAM_REVIEW_LIFECYCLE` | `ephemeral` | `persistent` launches standing reviewers. `HCOM_TEAM_CLAUDE_MODE` is a deprecated alias |
| `HCOM_TEAM_REVIEW_PROVIDER` | `claude-code` | `claude-code` \| `antigravity` \| `codex` |
| `HCOM_TEAM_CLAUDE_CODE_MODEL` | `claude-sonnet-4-6` | Claude Code model for claude-launched agents (stale tag — see §8) |
| `HCOM_TEAM_TOOL_AUTO_APPROVE` | `1` | 0 = interactive tool approval. When 1: Codex gets `--ask-for-approval never --sandbox <profile>`, Claude gets `--permission-mode auto`, agy gets `--dangerously-skip-permissions` |
| `HCOM_TEAM_ORCHESTRATOR_CODEX_SANDBOX` | `danger-full-access` | so the orchestrator can write `.git` |
| `HCOM_TEAM_AREA_CODEX_SANDBOX` | `workspace-write` | area agents cannot write `.git` |
| `HCOM_TEAM_TMUX_SESSION` | `crisai-hcom` | tmux session name |
| `HCOM_TEAM_TERMINAL` | tmux when available | terminal preset/command override |
| `HCOM_TEAM_NAMES_REGISTRY` | `reference/development/team_names.yaml` | stable base-name registry |
| `HCOM_TEAM_HINTS` | short "requests are assignments" line | appended by hcom to EVERY delivered message — keep it tiny |
| `HCOM_TEAM_CLAUDE_VISIBILITY` | `headless` | reviewer visibility: `headless` or `tmux` (review scripts) |
| `HCOM_TEAM_CLAUDE_MAX_LEASE_MINUTES` / `HCOM_TEAM_REVIEW_LEASE_MINUTES` | `180` | reviewer lease safety caps (claude / generic review scripts) |
| `HCOM_TEAM_CLAUDE_PROMPT_SUGGESTIONS` | `false` | keep idle reviewer panes quiet |
| `HCOM_TEAM_MEMORY_WRITE_POLICY` | degrade-gracefully text | injected into role bootstrap |
| `HCOM_DEVELOPMENT_DIR` | `./.hcom-development` | review-lease state dir (review scripts) |
| `HCOM_TEAM_ANTIGRAVITY_MODEL` | `Claude Sonnet 4.6 (Thinking)` | persisted agy model (preflight sets it) |
| `HCOM_TEAM_ANTIGRAVITY_MODEL_FRAGMENT` | model minus parenthetical | probe-match fragment |
| `HCOM_TEAM_ANTIGRAVITY_TOKEN_PATH` | `~/.gemini/antigravity-cli/antigravity-oauth-token` | reusable OAuth token (preflight requires it) |
| `HCOM_TEAM_ANTIGRAVITY_SETTINGS_PATH` | `~/.gemini/antigravity-cli/settings.json` | agy persisted settings |
| `HCOM_TEAM_ANTIGRAVITY_MODEL_PROBE_TIMEOUT` | `60s` | `agy --print` model probe timeout |

## 6. The review gate and its providers

Reviewers are **ephemeral to avoid idle cost, not optional**. The
orchestrator must launch the relevant reviewer *before commit* for
review-required work: runtime behaviour changes, security/auth changes,
routing or retrieval changes, shared UI contracts, hcom/dev-team tooling,
and larger UI changes. If the reviewer cannot launch or exits during startup,
that is **no review** — pause before commit, report the exact provider error,
and proceed only on explicit user override. Low-risk docs-only/mechanical
changes may skip review, stated explicitly in the handoff.

Provider-neutral entry points (provider capability registry:
`reference/development/review_providers.yaml`):

```bash
scripts/hcom_review.sh --role runtime_review --thread runtime-review --task "Review the runtime diff and report risks."
scripts/hcom_review.sh --role gem_review --thread gem-ui-review --provider antigravity --task "..."
scripts/hcom_review_status.sh
scripts/hcom_review_close.sh --thread runtime-review        # or --name / --role / --expired
```

Roles: `runtime_review` | `gem_review` | `web_review`. Options:
`--provider claude-code|antigravity`, `--lease-minutes N` (default 180),
`--visibility headless|tmux`, `--dry-run`; task text may also be piped on
stdin. Claude-provider requests delegate to the Claude-specific lifecycle
scripts, which can also be called directly:

```bash
scripts/hcom_claude_review.sh --role runtime_claude --thread T --task "..."
scripts/hcom_claude_status.sh
scripts/hcom_claude_close.sh --expired      # or --name/--role/--thread
```

Leases (recorded under `.hcom-development/*.local.yaml`) are stale-session
safety caps, not schedulers — the orchestrator still decides when to close a
reviewer.

### Provider status (verified against `review_providers.yaml` + git history)

| Provider | hcom tool | Registry status | Reality check |
|---|---|---|---|
| claude-code | `claude` | default; managed; ephemeral + persistent | The exercised path |
| antigravity | `agy` | `experimental: false`, preflight-gated | **Treat as experimental in practice** — see history below |
| codex | `codex` | `experimental: true`; persistent only; inverted-profile only | Only exists to review in the claude-dev profile |

Antigravity/Gemini history (all 2026-05-22/23): the first attempt (ceb38c9)
hacked a `REVIEWER_TOOL` substitution straight into `hcom_start.sh` and was
**reverted 7 minutes later** (01d3654). It was redesigned properly
(`review_provider_design.md`, 1fe2388), marked
experimental/manual-smoke-test-only by 2f538cd ("keep antigravity review
experimental"), then promoted the same day (3026d89) to a managed,
preflight-gated path and hardened over a fix train through 5ccd937 (isolated
reviewer sessions). So the registry flag was flipped to `experimental: false`
within 48 hours of the "keep experimental" commit, and the path has not run
since May — label any use of it experimental until re-proven. Preflight
mechanics (`hcom_antigravity_preflight.sh`): requires an existing reusable
OAuth token (no interactive login; if agy prompts for OAuth, run `agy` once
manually first), writes the requested model into agy's persisted settings
(`hcom_antigravity_model.sh` — `agy` has no `--model` launch flag), and
verifies with an `agy --print` probe. Role-scoped isolated HOMEs under
`.hcom/antigravity-homes/` are seeded separately by `scripts/hcom_start.sh`
(via `hcom_antigravity_home.sh`, called at `hcom_start.sh:569` and applied
with `env HOME=…`; auth/settings only, no conversations/brain artefacts) —
i.e. only for agy agents the standing-team starter launches (persistent
Antigravity reviewers). Ephemeral agy reviewers launched via
`scripts/hcom_review.sh` run with the user's real HOME and are NOT
isolated. Model profiles wired by `./start hcom agy
[claude|gemini]`: "Claude Sonnet 4.6 (Thinking)" / "Gemini 3.5 Flash
(Medium)" — persisted-settings display names that may have drifted (§8).

## 7. Normal working flow (when the team is up)

1. User asks the orchestrator (window 0, `cris`) for the next task; it reads
   `reference/TODO.md`, repo state, roster, memory.
2. Orchestrator assigns scoped work over hcom threads: scope, paths, expected
   checks, memory/bundle refs. One improvement per area at a time.
3. Area agent implements; orchestrator launches a reviewer for
   review-required work (§6).
4. Area agent hands off: role, area, task, status, changed files, checks,
   suggested Conventional Commit message, open questions. **No prose-only
   handoffs for machine-critical state** — reviewers must reject them.
5. Orchestrator integrates, runs final checks, updates docs, commits.
   Pushes only on explicit user request.
6. `scripts/hcom_stop.sh` to end the session with resumable state.

UI work must satisfy `reference/development/ui_engineering_contract.md`
(shared style contracts before local values; fixed regions stable during
runs; no overflow into prompts/status bars; checkpoints presented as user
decisions, not errors; handoffs state viewports tested and residual UX risk).

## 8. Revival checklist — the scripts predate the current repo state

Everything hcom was last committed 2026-05-24 (`git log` verified); the repo
then went through the June era: PR-based delivery from ~Jun 12, squash merges
from ~Jun 13, CI security gate as a hard merge blocker, the ADR-015 backbone,
and the ui/ redesign. Before a real (non-dry-run) launch:

1. **Dry-run first**: `scripts/hcom_start.sh --dry-run` and read every
   printed command. Nothing is launched and no assignments file is written.
2. **Binaries**: `command -v hcom tmux codex claude agy` — all five were on
   PATH 2026-07-02, but hcom/codex/claude/agy versions have moved since May;
   flags the scripts pass (`--permission-mode auto`,
   `--dangerously-skip-permissions`, `--ask-for-approval never`,
   `--sandbox`, `--hcom-prompt`, `--hcom-name`, `--go`) must still exist.
   Check `hcom --help` against the calls in `scripts/hcom_start.sh`.
3. **Reconcile git authority with the current change flow.** The operating
   model has the orchestrator committing directly (it predates the PR era).
   Current change control (see `crisai-change-control`) is feature branch →
   Conventional Commit with post-mortem body → PR → CI green (security gate
   is a hard blocker) → squash merge. A revived orchestrator must adopt
   branch/PR/squash, re-checking the branch tip before squashing (a
   late-pushed commit was once silently dropped by a squash). The role docs
   do not say this; you must.
4. **Model tags are stale**: `claude-sonnet-4-6`,
   "Claude Sonnet 4.6 (Thinking)", "Gemini 3.5 Flash (Medium)" are May-2026
   values baked into `./start`, `hcom_start.sh`, and the preflight defaults.
   Override via env rather than editing scripts until a deliberate refresh.
5. **Stale resume state**: `session_assignments.local.yaml` holds stopped
   claude-dev-profile sessions from 2026-05-24 (with
   `provider_session_id`s and transcript paths). `./start hcom claude-dev`
   will attempt to resume them; missing sessions fall back to fresh per
   role, but for new work prefer a fresh `scripts/hcom_start.sh` and stop
   the old profile's state from mixing in (the docs say: stop the team
   before switching profiles).
6. **Security posture is deliberate but sharp**: tool auto-approval defaults
   ON and the orchestrator runs `danger-full-access`. Use
   `--no-tool-auto-approve` when you want prompts back. Never widen the area
   sandboxes to full access — that is what makes the single-writer rule
   real.
7. **AGENTS.md is gitignored** (byte-identical to CLAUDE.md/GEMINI.md). Role
   bootstraps and context-folder READMEs tell agents to read it; on a fresh
   clone it does not exist. Ensure it is present locally before launch.
8. **Role ownership paths still match the tree** (verified 2026-07-02:
   `ui/apps/gem/`, `ui/apps/web/`, `src/crisai/` all exist), but role docs
   know nothing about post-May additions (ADR-015 materialisation modules,
   the eval corpus, the local model provider). Brief the orchestrator with
   current `reference/TODO.md` state at kickoff.

Current dormant state on this machine, as of 2026-07-02: `.hcom/` last
modified 2026-05-24 (contains `hcom.db` ~9.4 MB, `antigravity-homes/`,
launch scripts); `.hcom-development/` holds one Claude review lease file from
2026-05-22; no `crisai-hcom` tmux session assumed running.

## When NOT to use this skill

- **Solo change flow** (branches, PRs, squash discipline, commit-body
  conventions, CI gates, the non-negotiables) → `crisai-change-control`.
- **The product's runtime agents** (registry/agents.yaml roster, modes,
  pipelines, contracts) → `crisai-architecture-contract`; routing vocabulary
  → `crisai-semantic-registry-reference`.
- **Running the product** (`./start api|web|gem`, `./stop`, setup) →
  `crisai-build-run-operate`.
- **Test commands and evidence standards** → `crisai-validation-and-qa`.
- **History of product incidents** (auth saga, gate defects, ADR-015 arc) →
  `crisai-failure-archaeology`; active triage → `crisai-debugging-playbook`.
- **UI implementation standards** for `ui/apps/*` → `crisai-ui-surfaces`
  (this skill only covers *who* may edit them under the team model).

## Provenance and maintenance

Facts verified 2026-07-02 against the working tree and git history. One-line
re-verification commands:

```bash
# Which copy is live vs packaged, and divergence
diff -rq development-team/reference/development reference/development
git log -1 --format='%h %ad %s' --date=short -- development-team/   # 16b7f64 2026-05-22
git log -1 --format='%h %ad %s' --date=short -- reference/development/ scripts/hcom_start.sh  # 34c71ab 2026-05-24
git log --oneline --since=2026-05-25 -- scripts/ development-team/ reference/development/  # empty = still dormant

# Scripts, flags, env vars
scripts/hcom_start.sh --help
grep -n 'HCOM_TEAM_' scripts/hcom_start.sh scripts/hcom_review.sh scripts/hcom_claude_review.sh start

# ./start hcom profile grammar
sed -n '/^  hcom)/,/^  hcom-attach)/p' start

# Roster, names, shared rules
grep -n 'git_write_owner\|push_policy\|commit_owner' reference/development/agent_roster.yaml
cat reference/development/team_names.yaml

# Review provider status (experimental flags)
grep -n 'experimental\|default_provider' reference/development/review_providers.yaml
git log --oneline -- reference/development/review_providers.yaml   # 2f538cd → 3026d89 flip

# Recorded single-writer breach
grep -n 'single Git-writer' reference/development/newtest-04-restart-handoff.md

# Dormant-state and tooling presence
ls -la .hcom .hcom-development 2>/dev/null; head -5 reference/development/session_assignments.local.yaml
command -v hcom tmux codex claude agy

# Context folders are README-only mount points
ls gem web runtime
```
