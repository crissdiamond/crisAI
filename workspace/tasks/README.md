# Task workspaces (`workspace/tasks`)

Each task session has its own folder under `workspace/tasks/<task-slug>/`.
Agents use that folder as the working context for the task and can retrieve
previous artefacts from the same task without replaying the whole chat history.

## Standard task layout

| Path | Purpose |
|------|---------|
| `.crisai/` | Task manifest, chat history, compact memory, and CLI history. |
| `artefacts/` | Markdown/Mermaid source artefacts generated for the task. |
| `inputs/` | User-provided files or extracted source material for this task. |
| `scratch/` | Temporary notes that should not be treated as approved output. |
| `exports/` | Native documents generated later from reviewed Markdown sources. |

Markdown in `artefacts/` is the source of truth for generated architecture
work. Word, PowerPoint, Excel, email, JSON payload, and diagram exports should
be created as follow-on tasks from reviewed Markdown and organisation templates.

## Promotion to knowledge

Task artefacts are not automatically approved knowledge. When a user explicitly
asks for promotion, agents should transform the artefact into a concise,
machine-readable knowledge-base file under `workspace/knowledge_staging/`.
Humans can then review and promote it into `workspace/knowledge/`.
