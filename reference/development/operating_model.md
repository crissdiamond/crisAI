# hcom Development Operating Model

crisAI development can run as a small hcom team coordinated by one top-level
Codex orchestrator. Random hcom names such as `polo` or `hula` are session
handles only; stable responsibility comes from the role assigned in
`session_assignments.local.yaml`.

## Team Shape

- `orchestrator_codex`: runs from the repo root and is the main user-facing
  coordinator.
- `runtime_codex` and `runtime_claude`: run from the repo root with runtime
  role context.
- `gem_codex` and `gem_claude`: run from the repo root with Gem role context.
- `web_codex` and `web_claude`: run from the repo root with web role context.

The top-level `runtime/`, `gem/`, and `web/` directories are area context folders,
not source roots and not Codex sandbox roots. Source code stays in the existing
Python and UI locations. Area agents are launched from the repo root so their
workspace-write sandbox covers the files they own, while their role prompt and
tmux label keep the area boundary clear.

## Launching

Use `scripts/hcom_start.sh` from the repo root. The launcher writes local
session assignments to `reference/development/session_assignments.local.yaml`.

Use a fresh launch for new work:

```bash
scripts/hcom_start.sh
```

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
the source of truth.

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
`gem_claude(<hcom_name>)`, `web_codex(<hcom_name>)`,
`web_claude(<hcom_name>)`, `run_codex(<hcom_name>)`, and
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
launcher uses non-bypass modes: Codex receives `--ask-for-approval never
--sandbox workspace-write`, and Claude receives `--permission-mode auto`.
Use `--no-tool-auto-approve` or `HCOM_TEAM_TOOL_AUTO_APPROVE=0` when interactive
tool approval is required.

The launcher also sets `HCOM_HINTS` for the team. Direct hcom requests from the
orchestrator or paired agent are actionable assignments: agents should proceed
without asking the terminal user to confirm, and should not leave suggested
follow-up commands or draft prompts in the input bar. If an agent is waiting for
another agent, it should report that state through hcom and return to listening.

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
