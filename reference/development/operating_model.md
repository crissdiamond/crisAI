# hcom Development Operating Model

crisAI development can run as a small hcom team coordinated by one top-level
Codex orchestrator. Random hcom names such as `polo` or `hula` are session
handles only; stable responsibility comes from the role assigned in
`session_assignments.local.yaml`.

## Team Shape

- `orchestrator_codex`: runs from the repo root and is the main user-facing
  coordinator.
- `runtime_codex` and `runtime_claude`: run from `runtime/`.
- `gem_codex` and `gem_claude`: run from `gem/`.
- `web_codex` and `web_claude`: run from `web/`.

The top-level `runtime/`, `gem/`, and `web/` directories are launch folders,
not source roots. Source code stays in the existing Python and UI locations.

## Launching

Use `scripts/hcom_start.sh` from the repo root. The launcher writes local
session assignments to `reference/development/session_assignments.local.yaml`.

In WSL, the launcher opens shells in Windows Terminal when `wt.exe` is
available, otherwise it falls back to `tmux`. Override this with
`--terminal PRESET_OR_COMMAND` or `HCOM_TEAM_TERMINAL` when a different hcom
terminal backend is preferred.

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
- Claude area agents challenge, review, and may make small focused patches
  inside their area when useful.
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
- The orchestrator may run metadata-writing Git commands through the approved
  outside-sandbox path when `.git` is mounted read-only in normal agent
  sandboxes.
- Pushes remain an explicit user-controlled action. The orchestrator must not
  push unless the user has asked for a push or the active task instructions
  clearly include pushing.

## Shared Memory

All agents should use the Claude memory MCP server as the durable task context
layer. hcom messages should stay concise and point to memory entries, bundles,
or files instead of replaying long context.

Store in memory:

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
3. The orchestrator records task intent and assignments in memory.
4. Area agents receive short hcom requests with scope, paths, expected checks,
   and memory/bundle references.
5. Area Codex implements or plans; area Claude reviews or makes small patches
   when requested.
6. Area Codex resolves review feedback and records a concise memory update.
7. The orchestrator integrates, verifies, updates docs if needed, commits, and
   records the final outcome in memory.

## Communication Rules

- Use hcom threads for task coordination.
- Use hcom bundles for file/event/transcript-heavy handoffs.
- Use memory for durable cross-stream context.
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
