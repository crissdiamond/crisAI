# Knowledge staging (`workspace/knowledge_staging`)

**Draft** architecture-knowledge files land here for **human review** before promotion to the canonical tree under **`workspace/knowledge/`**.

- **Agents** (Publisher, intranet-to-knowledge workflows, etc.) should write new curated artefacts here, mirroring the folder names you expect in `knowledge/` (`patterns/`, `standards/`, …).
- **Humans** review, edit, set `status: approved` when appropriate, then **move or copy** files into `workspace/knowledge/...` (or merge into an existing file).
- **Retrieval** in normal runs uses **`knowledge/`** only; staging is not part of the approved corpus until promoted.

See **`prompts/_shared/knowledge-staging.md`** and **`workspace/knowledge/README.md`** (staging section).

Example request prompts (not executed automatically):

- **`_prompt_example.md`** — integration **patterns** catalogue and leaf pages.
- **`_prompt_integration_principles.md`** — integration **principles** from intranet Site Pages (mandatory **producer and consumer flows** page as primary evidence where relevant).
