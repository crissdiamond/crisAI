# Review Provider Design

This note defines how crisAI development should support non-Claude review
providers without weakening the review gate or overloading Claude-specific
scripts.

## Current Baseline

The stable development-team path is:

- `scripts/hcom_claude_review.sh`
- `scripts/hcom_claude_status.sh`
- `scripts/hcom_claude_close.sh`

Those scripts are intentionally Claude-specific. They launch hcom-managed
Claude reviewers, track leases, detect failed startup, surface provider errors,
and preserve the mandatory Claude review gate for review-required work.

## Problem To Solve

Other review-capable tools may become useful, including Gemini, OpenCode, and
Antigravity. They should not be added by making Claude scripts accept arbitrary
tool names. That creates a false abstraction because provider capabilities
differ:

- hcom has native launchers for `claude`, `gemini`, `codex`, and `opencode`;
- hcom does not currently have a native `agy` or `antigravity` launcher;
- provider flags differ, for example Claude supports `--permission-mode auto`
  while other tools may not;
- session lifecycle, hooks, transcripts, and resume support differ;
- role names, prompts, and gate language should reflect the actual reviewer
  provider.

## Design Principles

- Keep the current Claude gate stable until a replacement is proven.
- Do not treat a provider as hcom-managed unless hcom can launch, track, message,
  and close it reliably.
- Do not hide provider differences behind a single environment variable.
- Keep required-review behaviour fail-closed: if the configured required
  reviewer cannot run, pause before commit unless the user explicitly overrides.
- Prefer explicit provider capability declarations over inferred shell command
  behaviour.

## Proposed Shape

Add a generic review entrypoint without renaming the existing Claude scripts:

```bash
scripts/hcom_review.sh --provider claude --role runtime_review --thread <id> --task <text>
scripts/hcom_review_status.sh
scripts/hcom_review_close.sh --thread <id>
```

Provider configuration should live in a development-team config file, for
example:

```yaml
providers:
  claude:
    hcom_tool: claude
    managed: true
    supports_system_prompt: true
    supports_permission_mode_auto: true
    supports_resume: true
    required_gate: true
  gemini:
    hcom_tool: gemini
    managed: true
    supports_system_prompt: true
    supports_permission_mode_auto: false
    supports_resume: true
    required_gate: false
  opencode:
    hcom_tool: opencode
    managed: true
    supports_system_prompt: false
    supports_permission_mode_auto: false
    supports_resume: true
    required_gate: false
  antigravity:
    command: agy
    managed: false
    mode: one_shot_experimental
    required_gate: false
```

The first implementation supports `claude` through the generic entrypoint while
delegating internally to the existing Claude scripts. Antigravity is available as
an experimental managed provider only when the local hcom build supports
`hcom agy`; it remains unsuitable for mandatory gates until launch, message
delivery, transcript, and close behaviour have been smoke-tested in real team
runs. Gemini and OpenCode can be added after their review lifecycle behaviour is
verified.

## Antigravity Position

Antigravity CLI is available locally as `agy`. It can be treated as an
hcom-managed reviewer only with a local hcom build that exposes native
`hcom agy` launch support. The crisAI generic review launcher fails closed if
that support is not present.

Until the managed path is proven, Antigravity must not satisfy mandatory Claude
review gates.

## Implementation Plan

1. Add `.antigravitycli/` to `.gitignore` because it is local tool state.
2. Keep existing `hcom_claude_*` scripts Claude-specific.
3. Add provider capability config under `reference/development/`.
4. Add generic `hcom_review*` scripts that delegate to Claude and can launch
   experimental Antigravity reviewers when `hcom agy` is available.
5. Add shell tests for provider validation, dry-run launch construction, status,
   close, and fail-closed required-gate behaviour.
6. Add Gemini/OpenCode providers only after real hcom dry-run and smoke tests.
7. Promote Antigravity from experimental only after repeated team runs prove the
   review lifecycle is reliable.
