# Agent prompt template (crisAI)

Copy this file when adding a new agent. Replace every `TODO` and remove this
instruction block before saving as `prompts/<name>.md`.

## Identity

**Registry id:** `TODO` (must match `registry/agents.yaml` `id`)

**Display name:** TODO (should match `name` in the registry)

You are the TODO for crisAI.

## Mission

TODO: One short paragraph — the outcome this agent optimizes for (not a list of tools).

## Inputs

TODO: What this stage receives (user message, named upstream outputs). Keep conceptual; runtime may inject extra sections from code.

## Authority

TODO: What this agent may decide, produce, or conclude.

## Boundaries

TODO: What this agent must not do — especially responsibilities owned by neighbouring stages.

## Tooling and data

TODO: Preferred tools, scopes (workspace vs Graph), link/citation rules. Reuse or
copy from `prompts/_shared/` (`link-formatting.md`, `sharepoint-vs-onedrive.md`,
etc.) when the same guidance applies; the loader does not merge files automatically.

## Output contract

TODO: Required structure (headings, tables, sections). Keep labels stable if the UI or trace parsers depend on them.

## Quality bar

TODO: Tone, locale (e.g. British English), handling weak evidence, ambiguity.
