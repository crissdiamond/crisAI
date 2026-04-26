# crisAI

> **A local AI workstation for architecture, design, documentation, research, and controlled multi-agent critique.**

crisAI combines a registry-driven catalogue of MCP servers, a set of specialist agents, an interactive CLI, local and external document retrieval, optional peer-style critique workflows, and provider-aware model assignment.

The aim is to create a personal AI workstation that can retrieve source material, reason over it, draft outputs, critique them, and connect to tools such as local files, document readers, diagram generators, and SharePoint / OneDrive.

---

## Features

- Interactive CLI for one-off or ongoing sessions
- Web interface mirroring CLI routing and workflows
- Local workspace retrieval
- Document reading for common formats:
  - `.txt`
  - `.md`
  - `.csv`
  - `.docx`
  - `.pdf`
  - `.pptx`
  - `.xlsx`
- Mermaid diagram generation support
- SharePoint / OneDrive retrieval via delegated Microsoft Graph access
- Multi-agent orchestration with three execution modes:
  - `single`
  - `pipeline`
  - `peer`
- Phase 1 heuristic router for task-to-agent selection
- Explicit chat-state visibility for routing and agent pinning
- Persistent chat sessions
- Command history in the CLI
- In-chat slash commands for agent and server introspection
- Provider-aware model registry with per-agent model assignment
- Support-ready provider layer for OpenAI, Gemini, and Anthropic

---

## Architecture at a glance

crisAI is built around six layers:

1. **CLI and orchestration**
   - `src/crisai/cli/main.py`
   - command routing
   - chat loop
   - mode switching
   - review toggling
   - session history
   - heuristic task routing

2. **CLI support modules**
   - `src/crisai/cli/chat_context.py`
   - `src/crisai/cli/chat_controller.py`
   - `src/crisai/cli/commands.py`
   - `src/crisai/cli/display.py`
   - `src/crisai/cli/pipelines.py`
   - `src/crisai/cli/prompt_builders.py`
   - `src/crisai/cli/session_store.py`
   - `src/crisai/cli/status_views.py`
   - `src/crisai/cli/workflow_support.py`

3. **Agents**
   - configured in `registry/agents.yaml`
   - prompts stored in `prompts/`
   - created by `src/crisai/agents/factory.py`

4. **Model registry**
   - configured in `registry/models.yaml`
   - resolved by `src/crisai/model_resolver.py`
   - assigns provider-specific models to agents through logical `model_ref` values

5. **MCP servers**
   - configured in `registry/servers.yaml`
   - built and managed by `src/crisai/runtime.py`

6. **Sources**
   - local workspace
   - document parser
   - diagram generator
   - SharePoint / OneDrive via Microsoft Graph

---

## Project structure

```text
crisAI/
  start
  README.md
  DOCUMENTATION.md
  TESTING.md
  .env.example

  registry/
    servers.yaml
    agents.yaml
    models.yaml
    policies.yaml

  prompts/
    orchestrator.md
    discovery_agent.md
    design_agent.md
    review_agent.md
    operations_agent.md
    publisher.md
    design_author.md
    design_challenger.md
    design_refiner.md
    judge.md

  src/
    crisai/
      cli/
        main.py
        chat_context.py
        chat_controller.py
        commands.py
        display.py
        peer_transcript.py
        pipelines.py
        prompt_builders.py
        session_store.py
        status_views.py
        workflow_support.py
      agents/
        factory.py
      orchestration/
        router.py
      servers/
        workspace_server.py
        document_server.py
        diagram_server.py
        sharepoint_server.py
      config.py
      model_resolver.py
      registry.py
      runtime.py
      tracing.py

  tests/
  workspace/
  logs/
```

---

## Requirements

Before getting started, make sure you have:

- **Python 3.10+**
- **Linux, macOS, or WSL on Windows**
- **OpenAI API key** for OpenAI-backed agents
- **Optional:** Gemini and Anthropic keys if you assign those providers to any agents
- **Optional:** Microsoft Entra app registration for SharePoint access

---

## Installation

### 1. Clone the repository

```bash
git clone <https://github.com/crissdiamond/crisAI> 
cd crisAI
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -e .
```

If you want Gemini or Anthropic support through LiteLLM-backed integration, install the optional extra:

```bash
pip install -e ".[litellm]"
```

### 4. Create your environment file

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```dotenv
OPENAI_API_KEY=your_openai_api_key
CRISAI_DEFAULT_MODEL=gpt-5.4-mini
CRISAI_WORKSPACE_DIR=./workspace
CRISAI_LOG_DIR=./logs
CRISAI_REGISTRY_DIR=./registry
```

Provider keys when needed:

```dotenv
GEMINI_API_KEY=your_gemini_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

Optional SharePoint settings:

```dotenv
MS_TENANT_ID=your_tenant_id
MS_CLIENT_ID=your_client_id
MS_TOKEN_CACHE_PATH=.tokens/msal_token_cache.json
MS_GRAPH_SCOPES=User.Read,Files.Read.All,Sites.Read.All
```

### 5. Make the launcher executable

```bash
chmod +x start
```

### 6. Start crisAI

```bash
./start
```

### 7. Start the web interface

```bash
crisai-web
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## Model assignment

Agents no longer need to hard-code raw provider model strings.

### `registry/agents.yaml`
Assign a logical model reference:

```yaml
- id: discovery
  model_ref: openai_fast

- id: judge
  model_ref: gemini_strong
```

### `registry/models.yaml`
Define the real provider and model name:

```yaml
models:
  - id: openai_fast
    provider: openai
    model_name: gpt-5.4-mini
    api_key_env: OPENAI_API_KEY

  - id: gemini_strong
    provider: gemini
    model_name: gemini/gemini-2.5-pro
    api_key_env: GEMINI_API_KEY
```

This allows per-agent model assignment regardless of provider.

---

## Quick start

Once inside the interactive CLI, try:

```text
/status
/list servers
/list agents
/help
```

Typical first prompt:

```text
Search my personal OneDrive, not SharePoint sites, and find all documents related to the integration strategy.
```

Example one-off invocation:

```bash
python -m crisai.cli.main ask -m "Find the most relevant document for integration strategy and summarise it."
```

---

## CLI modes

### `single`
Runs one selected agent directly.

### `pipeline`
Runs the main structured flow:

1. Discovery
2. Design
3. optional Review, when the routing decision says it is needed
4. Orchestrator

### `peer`
Runs the peer-style flow:

1. Discovery, when retrieval is needed
2. Design Author
3. Challenger
4. Refiner
5. Judge
6. Orchestrator

---

## Heuristic routing

crisAI includes a Phase 1 heuristic router.

Typical behaviour:

- pure retrieval task → `single` + `discovery`
- retrieval + drafting task → `pipeline`
- proposal + critique task → `pipeline` with review
- critique-only task → `single` + `review`
- platform/debug task → `single` + `operations`
- peer-style debate request → `peer`
- vague or mixed task → `single` + `orchestrator`

Explicit user instructions always win:
- `/mode ...` and `/agent ...` pin behaviour
- `/mode auto` and `/agent auto` clear pins

---

## Chat commands

Inside the interactive CLI:

```text
/help
/status
/list servers
/list agents
/mode auto
/mode single
/mode pipeline
/mode peer
/review on
/review off
/verbose on
/verbose off
/agent auto
/agent discovery
/agent design
/agent review
/agent operations
/agent orchestrator
/history
/session architecture
/clear
/exit
```

---

## Retrieval discipline

crisAI is designed around retrieval discipline:

- never guess file paths, site names, drive IDs, or item IDs
- always list or search before reading
- only read a path or item returned in the current run
- report exact tool errors when retrieval fails

This matters for architecture and documentation work because trustworthy source handling is more important than sounding clever.

---

## Workspace usage

Recommended local source locations:

```text
workspace/inputs/
workspace/reference/
workspace/outputs/
workspace/scratch/
workspace/chat_sessions/
```

Workspace paths are relative to the workspace root.

Correct examples:

```text
inputs/strategy.md
reference/integration-principles.pdf
```

Incorrect examples:

```text
workspace/inputs/strategy.md
```

---

## SharePoint / OneDrive

SharePoint access is delegated and tied to the signed-in user.

The expected flow is:

1. Microsoft Entra app registration
2. delegated Microsoft Graph permissions
3. MSAL token caching
4. Graph access through `sharepoint_server.py`

Operational recommendation:
- check auth status before search
- avoid triggering interactive login unless explicitly required
- prefer predictable auth checks over surprise browser popups during discovery

---

## Testing

See `TESTING.md` for the current suite structure, how to run tests, and what the test layers protect.

---

## Logs

Useful logs include:

```text
logs/agent_trace.jsonl
workspace/workspace_mcp.log
workspace/document_mcp.log
workspace/sharepoint_mcp.log
```

---

## Licence

crisAI is released under the MIT License. See the `LICENSE` file for details.
