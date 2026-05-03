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

- Prefer **`prompts/{registry_id}_agent.md`** for role agents (e.g. `retrieval_planner_agent.md`).
- Short ids may use **`prompts/{registry_id}.md`** when it reads naturally (`orchestrator.md`, `judge.md`, `publisher.md`).
- The **registry `id`** and the **Identity** section must agree (e.g. `context_synthesizer` → `context_synthesizer_agent.md`).

## Registering a new agent

1. Copy `TEMPLATE.md` to a new file under `prompts/`.
2. Fill all sections; remove the top comment block.
3. Add an entry to `registry/agents.yaml` with `id`, `name`, `model_ref`, `prompt_file`, `allowed_servers`.
4. Run tests: `pytest tests/unit/test_prompt_scaffolding.py` (and full suite before merge).

## Shared snippets (`prompts/_shared/`)

Small, reusable fragments for **human maintainers** (copy into an agent’s
**Tooling and data** section when needed). The runtime loader currently reads
**one file per agent** from `registry/agents.yaml`—it does **not** auto-include
`_shared` files; keep critical rules duplicated in the agent prompt until a
compose step exists.

- `_shared/link-formatting.md` — workspace and Graph markdown links.
- `_shared/locale-tone.md` — British English and tone.
- `_shared/sharepoint-vs-onedrive.md` — retrieval scope for SharePoint vs OneDrive.
- `_shared/context-staging.md` — agent drafts under `workspace/context_staging/` vs canonical `context/`.

## Tests

`tests/unit/test_prompt_scaffolding.py` checks that:

- `TEMPLATE.md` contains all required section headings.
- Every `prompt_file` in `registry/agents.yaml` exists on disk.
- Every registry agent prompt uses the canonical `##` sections **in order**.
- Each `_shared/*.md` snippet exists and is non-empty.
