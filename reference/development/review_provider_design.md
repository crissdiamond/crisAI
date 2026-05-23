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

- hcom has native launchers for `claude`, `gemini`, `codex`, `opencode`, and
  `agy`;
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
scripts/hcom_review.sh --provider claude-code --role runtime_review --thread <id> --task <text>
scripts/hcom_review_status.sh
scripts/hcom_review_close.sh --thread <id>
```

Provider configuration should live in a development-team config file, for
example:

```yaml
providers:
  claude-code:
    hcom_tool: claude
    managed: true
    ephemeral_supported: true
    persistent_supported: true
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
    hcom_tool: agy
    managed: true
    ephemeral_supported: true
    persistent_supported: true
    mode: hcom_managed_with_reusable_oauth
    requires_existing_oauth: true
    requires_preflight: true
    model_selection_verified: persisted_model_probe
    default_model_env: HCOM_TEAM_ANTIGRAVITY_MODEL
    default_model: Claude Sonnet 4.6
    required_gate: true
```

The implementation supports `claude-code` through the generic entrypoint while
delegating internally to the existing Claude scripts. The old provider spelling
`claude` remains accepted as a compatibility alias. Antigravity is available
through `hcom agy` when the preflight confirms reusable local OAuth and an
active model matching the requested reviewer profile. OpenCode can be added
after its review lifecycle behaviour is verified.

## Antigravity Position

Antigravity CLI is available locally as `agy`. Current `agy` releases do not
accept a public model-selection launch flag, so the launcher does not pass one.
Instead, hcom sets the default model in Antigravity's persisted settings before
launch. Antigravity stores that choice in
`~/.gemini/antigravity-cli/settings.json`; hcom preflight updates the `model`
key atomically and verifies it with a short `agy --print` probe before creating
reviewer sessions.

Persistent reviewer sessions run with role-scoped isolated homes under
`.hcom/antigravity-homes/`. Each home copies only reusable auth, settings,
keybindings, installation id, and onboarding state from the user's real
Antigravity config. Conversations, implicit state, history, and brain artifacts
are not copied, so reviewers start from their role prompt and wait for hcom
assignments.

The OAuth token must already exist and be private; if Antigravity would prompt
for OAuth, the launch fails before creating reviewer sessions.

Antigravity reviewers may run in ephemeral or persistent lifecycle mode. Because
`agy` does not support Claude Code's `--permission-mode auto`, the launchers use
`--dangerously-skip-permissions` only when team tool auto-approval is enabled.

## Implementation Plan

1. Keep `.antigravitycli/` ignored because it is local tool state.
2. Keep existing `hcom_claude_*` scripts Claude-specific.
3. Keep provider capability config under `reference/development/`.
4. Route generic `hcom_review*` scripts through provider-specific preflight and
   launch arguments.
5. Add shell tests for provider validation, dry-run launch construction, status,
   close, and fail-closed required-gate behaviour.
6. Add Gemini/OpenCode providers only after real hcom dry-run and smoke tests.
