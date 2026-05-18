# crisAI Development Model

This area documents how crisAI is developed. It is intentionally separate from
the product README and operator documentation because crisAI itself also uses
multi-agent workflows at runtime. The development team described here is for
building the repository, not for using crisAI as an architecture workstation.

## Purpose

crisAI can be developed by a small hcom-coordinated team:

- one Codex orchestrator from the repository root;
- paired Codex and Claude agents for runtime, Gem, and web work;
- Claude memory MCP as the durable project context layer;
- hcom for short coordination messages, bundles, events, and terminal sessions.

Codex remains the main implementation agent. Claude agents review, challenge,
and make small focused patches when requested. The orchestrator owns planning,
cross-area coordination, final integration, and Git metadata writes.

## Architecture At A Glance

```mermaid
flowchart TB
    User[User] --> Orchestrator[Codex Orchestrator]

    Orchestrator --> Runtime[Runtime Pair]
    Orchestrator --> Gem[Gem Pair]
    Orchestrator --> Web[Web Pair]

    Runtime --> RuntimeCodex[Codex]
    Runtime --> RuntimeClaude[Claude Review]
    Gem --> GemCodex[Codex]
    Gem --> GemClaude[Claude Review]
    Web --> WebCodex[Codex]
    Web --> WebClaude[Claude Review]

    Orchestrator --> Git[Git Integration]
    Orchestrator --> Hcom[hcom Coordination]
    Runtime --> Hcom
    Gem --> Hcom
    Web --> Hcom

    Hcom --> Memory[Claude Memory MCP]
    Runtime --> Repo[crisAI Repository]
    Gem --> Repo
    Web --> Repo
    Git --> Repo
```

## Claude Memory MCP

Claude memory MCP is a required part of the development-team operating model.
It is the shared memory layer for all hcom streams, so agents do not need to
replay long transcripts or rely only on their current provider session.

Use memory for:

- user goals, constraints, and success criteria;
- active task assignments and ownership boundaries;
- design decisions and their rationale;
- implementation summaries and changed areas;
- review conclusions, risks, and unresolved blockers.

Do not store secrets, API keys, auth tokens, or private credential material.
hcom should carry short coordination messages and bundle references; Claude
memory should carry durable project context.

## Registry-Owned Semantics

Semantic behaviour must be configured, not hardcoded. Development agents should
treat this as a design principle, not as a preference.

- Runtime code may implement loaders, validators, and mechanics.
- Semantic vocabulary belongs in `registry/semantic_catalog.yaml` or
  `registry/semantic_graph.yaml`.
- Do not hardcode routing terms, intent patterns, verifier regexes, prompt
  lexicon terms, retrieval constraints, retrieval expansion terms, deliverable
  names, or source-family vocabulary in Python.
- If a change needs new task language, retrieval language, contract markers, or
  classification terms, update the registry and tests around registry loading or
  behaviour.
- If an agent proposes hardcoded semantic lists in Python, reviewers should send
  it back for registry-driven implementation before integration.

## Start Here

- [Operating model](operating_model.md): responsibilities, launch flow,
  session resume, Git authority, memory use, and UI definition of done.
- [Agent roster](agent_roster.yaml): stable roles, ownership boundaries, and
  shared rules.
- [Role prompts](roles/): bootstrap instructions for each hcom-launched agent.
- [UI engineering contract](ui_engineering_contract.md): expectations for Gem,
  web, and shared UI contract work.
- [Handoff template](handoff_template.md): compact area handoff format.
- [Review template](review_template.md): review format for Claude reviewers.

Default development-team terminal management requires `tmux`. Windows Terminal
can still be used by overriding `--terminal`, but the managed default is tmux.

## Common Commands

Fresh team launch:

```bash
scripts/hcom_start.sh
```

By default, launched Codex and Claude agents use non-bypass tool auto-approval
so they can proceed without repeated permission prompts. Disable this when you
want interactive tool approval:

```bash
scripts/hcom_start.sh --no-tool-auto-approve
```

Stop and save resumable session information:

```bash
scripts/hcom_stop.sh
```

The launcher uses `tmux` by default when available, so hcom can close managed
team panes without touching unrelated WSL or Windows Terminal sessions. The
default tmux session is `crisai-hcom`; override it with
`HCOM_TEAM_TMUX_SESSION`.

The tmux windows are created in this order:

1. `orchestrator(<hcom_name>)`
2. `gem_codex(<hcom_name>)`
3. `gem_claude(<hcom_name>)`
4. `web_codex(<hcom_name>)`
5. `web_claude(<hcom_name>)`
6. `run_codex(<hcom_name>)`
7. `run_claude(<hcom_name>)`

Attach to the team session with the helper:

```bash
scripts/hcom_attach.sh
```

Or attach directly with:

```bash
tmux attach -t crisai-hcom
```

Inside tmux, switch between agent windows with `Ctrl-\` then the window number,
`Ctrl-\` then `n` or `p` for next/previous, or `Ctrl-\` then `w` for the window
list. Detach without stopping agents with `Ctrl-\` then `d`. `Ctrl-b` remains a
secondary prefix if needed. The tmux status bar uses cyan labels for Codex
windows, purple labels for Claude windows, and green for the orchestrator/other
windows.

Continue the same team context:

```bash
./start hcom
```

`./start hcom` is a convenience wrapper for `scripts/hcom_start.sh --resume`.
Use `scripts/hcom_start.sh` directly when you want a fresh team launch or
advanced flags such as `--dry-run`, `--headless`, or `--no-tool-auto-approve`.

Show hcom state and local role assignments:

```bash
scripts/hcom_status.sh
```

Use `--resume` only when continuing the same development context. For new work,
prefer a fresh launch and rely on Claude memory plus the role documents for
shared context.

## Packaged Team Repository

The `development-team/` directory is a reusable copy of the same operating
model. It can be copied into its own repository and launched against a target
crisAI checkout:

```bash
scripts/hcom_start.sh --target-repo /path/to/crisAI
scripts/hcom_start.sh --target-repo /path/to/crisAI --resume
scripts/hcom_stop.sh --target-repo /path/to/crisAI
```

When running the packaged scripts from this repository's embedded
`development-team/` directory, pass `--target-repo /home/diamond/crisAI` or run
the root scripts under `scripts/`. Without `--target-repo`, the packaged script
treats its own `development-team/` checkout as the target repository.

See [development-team/README.md](../../development-team/README.md) for the
packaged-team form.
