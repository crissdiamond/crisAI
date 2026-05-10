# crisAI Coding Instructions

These instructions apply when working in this repository.

- crisAI is intended to be a workstation of agents, each with separate roles and responsibilities.
- Keep each agent scope as limited as possible. Avoid responsibility overlap between agents.
- Prefer more narrowly scoped agents over fewer broad agents when adding agent capability.
- The user must be able to associate each agent with a specific model through configuration settings.
- Work on one improvement at a time.
- The user may write in English or Italian; always respond in English.
- Apply solid software engineering practices.
- Do not assume code behaviour. Inspect and validate against the codebase before changing it.
- Add or update tests under `tests/` when changing, adding, or removing tested behaviour.
- Run relevant tests after changing code covered by tests.
- Add code comments only when needed for clarity, following Google-style conventions.
- Add comments to existing code when clarity is needed.
- Update `README.md` and `DOCUMENTATION.md` whenever the change affects usage, architecture, setup, or behaviour.
- At the end of each improvement or change, create a commit using Conventional Commits.
- Do not add a `Made-with: Cursor` trailer in commit messages.
- Do not push unless specifically asked.
