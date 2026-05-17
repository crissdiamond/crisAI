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

## Common Commands

Fresh team launch:

```bash
scripts/hcom_start.sh
```

Stop and save resumable session information:

```bash
scripts/hcom_stop.sh
```

Continue the same team context:

```bash
scripts/hcom_start.sh --resume
```

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

See [development-team/README.md](../../development-team/README.md) for the
packaged-team form.
