# Agent prompts (crisAI)

Markdown instructions loaded by `AgentFactory.load_prompt()` from paths in
`registry/agents.yaml`. Paths are **relative to the repository root**.

## Canonical structure

Every agent prompt should follow the section order in **`TEMPLATE.md`**:

1. **Identity** — Registry id, display name, one-line role.
2. **Mission** — What this agent optimizes for.
3. **Inputs** — Conceptual inputs from the workflow.
4. **Authority** — Allowed decisions and outputs.
5. **Boundaries** — Forbidden overlap with other stages.
6. **Tooling and data** — Tools, scopes, links; may reference `prompts/_shared/`.
7. **Output contract** — Required headings or formats.
8. **Quality bar** — Tone, locale, evidence rules.

Use the same `##` headings so humans can skim any file predictably.

## Naming files

- Prefer **`prompts/{registry_id}_agent.md`** for role agents (e.g. `discovery_agent.md`).
- Short ids may use **`prompts/{registry_id}.md`** when it reads naturally (`orchestrator.md`, `judge.md`, `publisher.md`).
- The **registry `id`** and the **Identity** section must agree (e.g. `context_synthesizer` → `context_synthesizer_agent.md`).

## Registering a new agent

1. Copy `TEMPLATE.md` to a new file under `prompts/`.
2. Fill all sections; remove the top comment block.
3. Add an entry to `registry/agents.yaml` with `id`, `name`, `model_ref`, `prompt_file`, `allowed_servers`.
4. Run tests: `pytest tests/unit/test_prompt_scaffolding.py` (and full suite before merge).

## Tests

`tests/unit/test_prompt_scaffolding.py` checks that:

- `TEMPLATE.md` contains all required section headings.
- Every `prompt_file` in `registry/agents.yaml` exists on disk.
