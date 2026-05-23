# hcom Development Operating Model

crisAI development can run as a small hcom team coordinated by one top-level
Codex orchestrator. Random hcom names such as `polo` or `hula` are session
handles only; stable responsibility comes from the role assigned in
`session_assignments.local.yaml`.

## Team Shape

- `orchestrator_codex`: runs from the repo root and is the main user-facing
  coordinator.
- `runtime_codex`, `gem_codex`, and `web_codex`: run from the repo root with
  area role context.
- `runtime_claude`, `gem_claude`, and `web_claude`: ephemeral reviewers
  launched by the orchestrator as mandatory gates for review-required work.

The top-level `runtime/`, `gem/`, and `web/` directories are area context folders,
not source roots and not Codex sandbox roots. Source code stays in the existing
Python and UI locations. Standing area Codex agents are launched from the repo
root so their workspace-write sandbox covers the files they own, while their
role prompt and tmux label keep the area boundary clear.

## Launching

Use `scripts/hcom_start.sh` from the repo root. The launcher writes local
session assignments to `reference/development/session_assignments.local.yaml`.

Use a fresh launch for new work:

```bash
scripts/hcom_start.sh
```

By default this starts the standing Codex team only: orchestrator, runtime,
Gem, and web. Set `HCOM_TEAM_REVIEW_LIFECYCLE=persistent` only when
intentionally debugging or running a long paired session with always-on
reviewer agents. `HCOM_TEAM_CLAUDE_MODE` still works as a deprecated
compatibility alias for the lifecycle setting.

Choose the reviewer provider independently with
`HCOM_TEAM_REVIEW_PROVIDER=claude-code|antigravity`. Claude Code is the default.
Antigravity is allowed for the same reviewer lifecycle only after preflight
confirms reusable local OAuth, native `hcom agy` launch support, and an active
persisted Claude model selection. Set the Antigravity default once with `agy`,
enter `/model`, choose `Claude Sonnet 4.6 (Thinking)`, and confirm it appears in
the footer. The current `agy` CLI does not expose a public `--model` launch
flag, so hcom verifies the persisted model before launch instead of passing a
model argument. If the preflight fails, no reviewer has run and the orchestrator
must pause before commit.

Use resume only when continuing the same team context:

```bash
scripts/hcom_start.sh --resume
```

Resume reads the previous assignment file before overwriting it. If a role has a
`provider_session_id`, the launcher resumes that Codex or Claude session through
hcom; otherwise it resumes the previous hcom session name. Missing previous
sessions fall back to a fresh launch for that role. After launch, the assignment
file records both the hcom session name and the provider session UUID when hcom
exposes one. Claude memory remains the durable project memory layer, so resumed
provider sessions should be used for continuity on active work rather than as
the source of truth. Ephemeral Claude reviewers are normally launched fresh for
the task thread that needs them.

Use `scripts/hcom_stop.sh` to end the team. The stop script snapshots the active
hcom/provider session IDs, transcript paths, and stopped status before killing
the team tags, so `scripts/hcom_start.sh --resume` has the information needed to
restore the previous sessions.

The launcher uses `tmux` by default when available. That keeps hcom team shells
inside a managed terminal session and avoids force-closing Windows Terminal tabs
from WSL. Override this with `--terminal PRESET_OR_COMMAND` or
`HCOM_TEAM_TERMINAL` when a different hcom terminal backend is preferred. The
default tmux session is `crisai-hcom`, configurable with
`HCOM_TEAM_TMUX_SESSION`. Default tmux windows are named and ordered as:
`orchestrator(<hcom_name>)`, `gem_codex(<hcom_name>)`,
`web_codex(<hcom_name>)`, and `run_codex(<hcom_name>)`. Persistent Claude mode
adds `gem_claude(<hcom_name>)`, `web_claude(<hcom_name>)`, and
`run_claude(<hcom_name>)`. Attach with `scripts/hcom_attach.sh` or
`tmux attach -t crisai-hcom`, switch windows with `Ctrl-\` then the window
number, `Ctrl-\` then `n` or `p`, or `Ctrl-\` then `w`, and detach without
stopping the team with `Ctrl-\` then `d`. `Ctrl-b` remains a secondary prefix if
needed. The tmux status area uses two fixed bottom lines: the first lists
agents, and the second shows command help. The orchestrator is dark purple,
Codex area agents are blue, and Claude area agents are dark grey; the selected
window is bold.

Tool auto-approval is enabled by default for launched agents so routine
development work does not block on repeated provider permission prompts. The
launcher gives the orchestrator Codex a Git-writer profile
(`--ask-for-approval never --sandbox danger-full-access` by default) so `.git`
metadata is writable for commit and push operations. Area Codex agents receive
`--ask-for-approval never --sandbox workspace-write`, and Claude receives
`--permission-mode auto` when they are launched.
Antigravity reviewers receive `--dangerously-skip-permissions` when auto
approval is enabled because `agy` does not use Claude Code's
`--permission-mode auto` flag.
Use `--no-tool-auto-approve` or `HCOM_TEAM_TOOL_AUTO_APPROVE=0` when interactive
tool approval is required. Override `HCOM_TEAM_ORCHESTRATOR_CODEX_SANDBOX` or
`HCOM_TEAM_AREA_CODEX_SANDBOX` when a different Codex sandbox profile is needed.

Launch ephemeral Claude reviewers with `scripts/hcom_claude_review.sh`. The
orchestrator must choose the role, thread, expected output, lease cap, and
whether the reviewer should run headless or in tmux.
`HCOM_TEAM_CLAUDE_VISIBILITY` defaults to `headless`; use `tmux` only when a
visible temporary reviewer pane is worth the UI noise. Use
`scripts/hcom_claude_status.sh` to inspect active reviewers and
`scripts/hcom_claude_close.sh` to close them by name, role, thread, or expired
lease. Leases are stale-session safety caps; the orchestrator still decides
when to close or keep Claude alive for sequential related tasks.
If a reviewer exits immediately during startup, the review script marks its
local lease inactive and reports the transcript-level failure, such as provider
rate limiting. Treat that as no review having occurred.

### Review Gate

Reviewers are ephemeral to avoid idle cost, not optional substitutes for review.
The orchestrator must launch the relevant Claude-model reviewer before commit
for review-required work, including runtime behaviour changes,
security/authentication changes, routing or retrieval changes, shared UI
contracts, hcom/development-team tooling, and larger UI changes.

Claude Code is the default reviewer provider. Antigravity may satisfy the same
review role when `HCOM_TEAM_REVIEW_PROVIDER=antigravity` and preflight confirms
reusable OAuth plus an active Claude model. If a required reviewer cannot
launch, exits during startup, or reports a provider error such as rate limiting,
the task pauses before commit. The orchestrator must report the reviewer role, provider,
thread, exact error, reset time when available, current changed files, completed
checks, and the retry command. It must not replace reviewer challenge with
orchestrator self-review unless the user explicitly says to proceed without
review for that task.

For low-risk docs-only or mechanical changes, the orchestrator may skip Claude
review, but should state why in the handoff or final task note.

The launcher also sets `HCOM_HINTS` for the team. Direct hcom requests from the
orchestrator or paired agent are actionable assignments: agents should proceed
without asking the terminal user to confirm. Area agents should not monitor or
ask status questions about unrelated agents. They should query another agent
only when it is directly required by the assigned task; otherwise they should
report their own waiting state through hcom and return to listening.

Claude Code prompt suggestions are disabled for Claude reviewer sessions by
default through `CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false`. Override with
`HCOM_TEAM_CLAUDE_PROMPT_SUGGESTIONS=true` only when actively debugging Claude
Code suggestions.

## Responsibilities

- The orchestrator plans work, assigns tasks, integrates results, runs final
  checks, and creates commits.
- The orchestrator is not the primary implementation worker for area-owned
  code. Runtime, Gem, and web implementation belongs to the relevant area Codex
  agent.
- The orchestrator may inspect, coordinate, integrate, and make small glue or
  documentation edits, but should not directly implement area feature work
  unless delegation is not practical and the exception is explicit.
- Area Codex agents are primary implementers and local coordinators.
- Claude area agents are ephemeral reviewers. The orchestrator launches them
  for review-required work, may keep them alive across related sequential work,
  and closes them after push, abandonment, or when follow-up is unlikely.
- Shared files such as `registry/*`, `prompts/*`, `README.md`,
  `DOCUMENTATION.md`, and `ui/packages/contracts/*` need explicit orchestrator
  ownership for the task.
- UI work must follow `reference/development/ui_engineering_contract.md`.
- No agent should revert another agent's edits. If there is a conflict, stop and
  ask the orchestrator.

## Git Authority

The development team uses a single Git writer model.

- The orchestrator is the only role allowed to run Git commands that write
  repository metadata, including `git add`, `git commit`, `git fetch`,
  `git pull`, `git push`, branch switching, merge, rebase, and tag commands.
- Area agents may use read-only Git commands such as `git status`, `git diff`,
  `git log`, and `git show` to understand their work.
- Area agents must hand off changed files, checks, and a suggested Conventional
  Commit message to the orchestrator instead of committing or pushing.
- The orchestrator is launched with a Git-writer sandbox profile so it can write
  `.git` metadata directly. Area agents keep their normal workspace-write
  profile and must not write Git metadata.
- Pushes remain an explicit user-controlled action. The orchestrator must not
  push unless the user has asked for a push or the active task instructions
  clearly include pushing.

## Registry-Owned Semantics

Semantics are product configuration, not implementation shortcuts.

- Runtime code may provide registry loading, validation, and deterministic
  mechanics, but semantic vocabulary must live in the registry.
- Keep routing terms, intent patterns, verifier regexes, prompt lexicon terms,
  retrieval constraints, retrieval expansion terms, deliverable names, and
  source-family vocabulary out of Python source.
- Use `registry/semantic_catalog.yaml` for router term lists, peer-verifier
  regex patterns, peer-contract markers, shared prompt lexicon terms, retrieval
  source-fit constraints, and generic session-anchor vocabulary.
- Use `registry/semantic_graph.yaml` for task-intent vertices, deliverable
  types, source-family vocabulary, source-resolution vocabulary, and
  deterministic retrieval expansion.
- Standalone function words belong in `lexicon.function_words`, not scattered
  across feature-specific vertices or local constants.
- Any handoff or review that includes hardcoded semantic lists in Python should
  be treated as incomplete until the behaviour is registry-driven.

## Structured Workflow Contracts

Machine-critical workflow state must move between agents as structured,
schema-backed contracts. Prose is acceptable for user-facing summaries and brief
human context, but runtime behaviour must not depend on prose parsing when a
contract can represent the state.

- Use JSON schemas or typed runtime objects for routing decisions, task/request
  contracts, source identities, evidence, retrieval handoffs, gates, retries,
  and checkpoint decisions.
- Keep raw machine contracts out of normal user-facing panels unless the surface
  is explicitly verbose/debug-oriented.
- Do not replace structured handoffs with prompt-only or prose-only shortcuts
  because they are faster to implement.
- Reviewers must challenge prose-only inter-stage handoffs, missing schema
  validation, and any implementation that asks downstream agents to infer source
  identity or policy state from narrative text.

## Shared Memory

All agents should use the Claude memory MCP server as the durable task context
layer. hcom messages should stay concise and point to memory entries, bundles,
or files instead of replaying long context.

Memory write access is best-effort. Some Claude worker sessions run with
Claude memory in read-only mode. If a memory write is denied, the agent must not
block, retry indefinitely, or ask the terminal user to fix it. The agent should
include the intended memory summary in its hcom handoff or final report and
continue the task.

Store in memory when write access is available:

- user goals and success criteria;
- active task assignments;
- important design decisions;
- implementation summaries;
- review conclusions;
- unresolved questions and blockers.

Do not store secrets, API keys, auth tokens, or private credential material.

## Normal Flow

1. The user asks the orchestrator for the next task or a specific change.
2. The orchestrator reads `reference/TODO.md`, current repo state, hcom roster,
   and relevant memory.
3. The orchestrator records task intent and assignments in memory when write
   access is available, otherwise it includes the intended memory summary in the
   hcom task thread.
4. Area agents receive short hcom requests with scope, paths, expected checks,
   and memory/bundle references.
5. Area Codex implements or plans; the orchestrator launches an ephemeral Claude
   reviewer when review/challenge is useful.
6. Area Codex resolves review feedback and records a concise memory update when
   write access is available, otherwise it includes the intended memory summary
   in the handoff.
7. The orchestrator integrates, verifies, updates docs if needed, commits, and
   records the final outcome in memory when write access is available.

## Communication Rules

- Use hcom threads for task coordination.
- Use hcom bundles for file/event/transcript-heavy handoffs.
- Use memory for durable cross-stream context when available; use hcom handoffs
  as the fallback when memory is read-only.
- Lead handoffs with the role, area, task, status, changed files, checks, and
  open questions.
- Keep one improvement active per area unless the orchestrator explicitly splits
  independent work.

## UI Definition Of Done

For Gem, web, or shared UI contract changes:

- shared styles and semantic UI states are used before local hardcoded values;
- fixed layout regions remain stable during active runs;
- variable output cannot overflow into prompts, status bars, or neighbouring
  panels;
- checkpoint and gate states are presented as user decisions with clear actions,
  not as internal runtime errors;
- tests or manual checks cover at least one constrained viewport and one normal
  viewport;
- handoff notes describe overflow handling, style contract usage, and residual
  UX risks.
