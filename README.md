# crisAI

> **A local AI workstation for architecture, design, documentation, research, and controlled multi-agent critique.**

crisAI combines specialist agents, MCP tools, local and Microsoft Graph-backed retrieval, structured workflow modes, and provider-aware model assignment. Use it to find source material, reason over it, draft architecture or documentation outputs, challenge those outputs through peer-style critique, and keep generated artefacts grounded in inspectable sources.

This README is the quick start. The full operator manual is [DOCUMENTATION.md](DOCUMENTATION.md).

## What It Provides

- React web and Ink Gem terminal clients backed by the same runtime API.
- Shared UI event contracts for routing, task contracts, streamed stages, checkpoints, final answers, and run state.
- Specialist agents with separate responsibilities and configurable model assignment.
- Local workspace, document, diagram, vision, SharePoint document, scoped intranet, and read-only session memory MCP servers.
- Three workflow modes: `single`, `pipeline`, and `peer`.
- Retrieval checkpoints, source-fit validation, deterministic retrieval expansion, and task-backed sessions.
- Native DOCX/PPTX export from reviewed Markdown task artefacts via template manifests.

## Requirements

- Linux, macOS, or WSL on Windows.
- [uv](https://docs.astral.sh/uv/) for Python environment and dependency management.
- Node.js and npm for the React web and Ink Gem clients.
- Provider keys matching the selected registry models. The default registry expects `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `DEEPSEEK_API_KEY`.
- Optional: Microsoft Entra app registration for SharePoint document retrieval and SharePoint-backed intranet retrieval.

The repository tracks `.python-version` as `3.13` for local development. The package supports Python 3.10+. Python 3.14 is not the default local runtime while OpenAI streaming support remains incompatible with the current locked SDK versions.

## Clean Install

Install uv first if needed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Clone the repository and run bootstrap:

```bash
git clone https://github.com/crissdiamond/crisAI
cd crisAI
scripts/bootstrap.sh
```

The supported office install path is clone plus bootstrap. Wheel and `uv tool install` packaging is not a standalone deployment target yet because the repository supplies the default registry, prompts, runbooks, UI workspace, and starter workspace files.

`scripts/bootstrap.sh` installs the runtime, installs UI dependencies when `npm` is available, creates `.env` from `.env.example` when missing, and creates the standard workspace folders. uv creates and manages the project `.venv`; do not create or activate a virtual environment manually.

## Configure

Edit `.env` and set the keys used by your registry:

```dotenv
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
CRISAI_DEFAULT_MODEL=gpt-5.4-mini
CRISAI_WORKSPACE_DIR=./workspace
CRISAI_LOG_DIR=./logs
CRISAI_REGISTRY_DIR=./registry
```

The default registry mixes providers. To run with one provider, copy one of the mono-provider examples over `registry/agents.yaml`, then set only that provider's key:

```bash
cp registry/examples/agents.openai.yaml registry/agents.yaml
```

To use a **local / self-hosted model** (Qwen, etc.) served behind an
OpenAI-compatible endpoint such as Ollama, vLLM, or LM Studio, assign the
`qwen_local` model in `registry/agents.yaml` (or copy
`registry/examples/agents.local.yaml`). See the "Local and self-hosted models"
section of [DOCUMENTATION.md](DOCUMENTATION.md) for setup, including running
Ollama on WSL2.

Check the installation after editing `.env` or registry files:

```bash
uv run crisai doctor
```

For a team-member first run, follow the onboarding checklist in
[runbooks/01-setup.md](runbooks/01-setup.md). It covers prerequisites, provider
keys, `doctor`, optional provider smoke tests, and a short example run.

## Start

Run the FastAPI backend first, then attach a client:

```bash
./start api          # FastAPI backend on http://127.0.0.1:8000
./start gem          # Ink terminal client, separate terminal
# or
./start web          # React/Vite web client at http://127.0.0.1:5173
./start knowledge    # sync workspace/knowledge from CRISAI_KNOWLEDGE_REPO
./start knowledge-pr "desc"   # submit your knowledge edits as a PR for review
./stop               # stop the running api and web processes
```

If bootstrap skipped UI dependencies because `npm` was unavailable, run this once before starting Gem or web:

```bash
npm --prefix ui install
```

## Repository Map

```text
registry/     Agent, server, model, routing, policy, and retrieval dictionaries
prompts/      Agent prompt files and prompt-authoring guidance
src/crisai/   CLI, runtime API, orchestration, MCP servers, schemas, and validation code
tests/        Network-free unit, CLI, and orchestration regression tests
workspace/    Knowledge base, task workspaces, staged knowledge, outputs, sessions, and caches
runbooks/     Operational setup, security, registry, policy, and observability notes
ui/           React web and Ink Gem clients plus shared TypeScript UI contracts
```

## Development Checks

Install the dev group before running the full suite:

```bash
uv sync --extra litellm --group dev
uv run pytest
npm --prefix ui run typecheck
npm --prefix ui run build:web
npm --prefix ui run build:gem
```

See [TESTING.md](TESTING.md) for the suite layout and manual Graph login smoke test.

## Local Cleanup

To inspect rebuildable local disk usage without deleting anything:

```bash
scripts/clean_local.sh
```

Add `--apply` to remove selected rebuildable artefacts. Use `--deps --apply` only when you want to remove `.venv` and UI `node_modules`; bootstrap can recreate them.

## Documentation

- [DOCUMENTATION.md](DOCUMENTATION.md): full operator manual.
- [DOCUMENTATION_DETERMINISTIC_RETRIEVAL.md](DOCUMENTATION_DETERMINISTIC_RETRIEVAL.md): deterministic retrieval architecture.
- [TESTING.md](TESTING.md): test suite and development checks.
- [reference/VISION.md](reference/VISION.md): product vision and guiding principles.
- [reference/TODO.md](reference/TODO.md): maintainable backlog of future improvements.
- [reference/decisions/](reference/decisions/): product and engineering design decisions.
- [runbooks/](runbooks): setup, registry, policies, observability, and security.
- [prompts/README.md](prompts/README.md): prompt authoring guidance.

## Licence

crisAI is released under the MIT License. See [LICENSE](LICENSE).
