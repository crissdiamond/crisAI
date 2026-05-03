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
- Scoped **intranet** MCP for published SharePoint **site pages** on configured sites only (`registry/intranet.yaml`; tools: `intranet_search`, `intranet_fetch`, `intranet_list_page_links`, **`intranet_list_all_pages`** for deterministic full-catalogue discovery)
- Configurable on-disk page catalogue cache (default 4 h, `INTRANET_PAGE_CACHE_TTL_HOURS`) so agents can list every available page without repeated Graph API scans
- Optional **architecture context** corpus under `workspace/context/`, with **draft staging** in `workspace/context_staging/` for human review before promotion
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
   - local workspace (including curated `context/` retrieval and draft `context_staging/`)
   - document parser
   - diagram generator
   - SharePoint / OneDrive documents via Microsoft Graph
   - SharePoint **site pages** on allowed intranet hosts via the intranet MCP

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
    intranet.yaml

  prompts/
    TEMPLATE.md
    README.md
    orchestrator.md
    retrieval_planner_agent.md
    context_retrieval_agent.md
    context_synthesizer_agent.md
    design_agent.md
    review_agent.md
    operations_agent.md
    publisher.md
    design_author.md
    design_challenger.md
    design_refiner.md
    judge.md
    _shared/  (snippet library for prompt authors)

  src/
    crisai/
      apps/
        web.py
        ui_config.py
        ui/
          index.html
          styles.css
          app.js
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
        intranet_server.py
      config.py
      model_resolver.py
      registry.py
      runtime.py
      tracing.py
      web/
        app.py

  tests/
  workspace/
    context/          # approved HE architecture corpus (retrieval default)
    context_staging/  # agent drafts; promote into context/ after review
  logs/
```

Notes:
- `src/crisai/apps/` is the canonical app-surface package (web today, mobile-ready structure for future apps).
- `src/crisai/web/app.py` is a compatibility shim.

---

## Requirements

Before getting started, make sure you have:

- **Python 3.10+** with the **`venv` standard library module available** (see installation notes below)
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

crisAI expects a project-local virtual environment at **`.venv`** in the repository root. The **`./start`** launcher sources `.venv/bin/activate` and exits with instructions if that directory is missing.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On **Debian / Ubuntu** (and many derivatives), `python3 -m venv` can fail until you install the matching OS package for your Python minor version, for example:

```bash
sudo apt install python3-venv
# or, if you use Python 3.12 specifically:
sudo apt install python3.12-venv
```

### 3. Install dependencies

With `.venv` activated:

```bash
pip install --upgrade pip
pip install -e .
```

Equivalent using the requirements file (same default dependencies as `pip install -e .`):

```bash
pip install -r requirements.txt
```

If you want Gemini or Anthropic support through LiteLLM-backed integration, install the optional extra:

```bash
pip install -r requirements-litellm.txt
```

or:

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

Optional SharePoint / intranet settings:

```dotenv
MS_TENANT_ID=your_tenant_id
MS_CLIENT_ID=your_client_id
MS_CLIENT_SECRET=your_client_secret   # optional; "Allow public client flows" must be on in Azure
MS_REDIRECT_URI=http://localhost

# Intranet page catalogue cache TTL (used by intranet_list_all_pages)
INTRANET_PAGE_CACHE_TTL_HOURS=4
```

> **WSL2 note:** crisAI uses the OAuth 2.0 **device code flow** for Microsoft Entra login in WSL2 environments. When the token is missing or expired a URL and short code are printed to the terminal — open the URL in any browser and enter the code to authenticate. No localhost redirect is required. Your Azure app registration must have **"Allow public client flows"** enabled (App registrations → Authentication → Advanced settings).

### 5. Make the launcher executable

```bash
chmod +x start
```

### 6. Start crisAI (CLI or Web)

```bash
./start cli
```

Start web mode with:

```bash
./start web
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

You can still run the direct script if needed:

```bash
crisai-web
```

### 8. Clean install verification

After a fresh install, validate both runtime surfaces:

```bash
./start cli
./start web
```

If `./start` reports a missing `.venv`, create it and install dependencies first.

Dependency note:
- `pytest` and `traced` are part of the base install and should be available after `pip install -e .`.

Microsoft Graph auth note:
- SharePoint (documents) and Intranet (site pages) each have an **independent token cache** — losing or resetting one does not affect the other
- when a token cache is missing or expired, crisAI triggers interactive Microsoft Entra login automatically (CLI and web)
- on WSL2 the **device code flow** is used: a URL and short user code are printed to the terminal; open the URL in any browser and enter the code — no localhost redirect is needed
- your Azure app registration must have **"Allow public client flows"** enabled under Authentication → Advanced settings
- for a manual login smoke test, run:

```bash
python tests/orchestration/test_graph_login.py
```

---

## Model assignment

Agents no longer need to hard-code raw provider model strings.

### `registry/agents.yaml`
Assign a logical model reference:

```yaml
- id: retrieval_planner
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

1. `retrieval_planner` → `context_retrieval` → `context_synthesizer`
2. `design`
3. optional `review`, when the routing decision says it is needed
4. `orchestrator`

### `peer`
Runs the peer-style flow:

1. optional `retrieval_planner` → `context_retrieval`, when retrieval is needed
2. `design_author`
3. `design_challenger`
4. `design_refiner`
5. `judge`
6. `orchestrator`

---

## Heuristic routing

crisAI includes a Phase 1 heuristic router.

Typical behaviour:

- pure retrieval task → `single` + `retrieval_planner`
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
/agent retrieval_planner
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
workspace/context/          # approved architecture corpus (see workspace/context/README.md)
workspace/context_staging/  # drafts for human review before promotion into context/
workspace/chat_sessions/
```

Retrieval agents search **`context/`** by default; **`context_staging/`** is for drafts only until you promote files. Workspace paths are relative to the workspace root.

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
4. Graph access through `sharepoint_server.py` (documents) and, when enabled, `intranet_server.py` (published **site pages** on configured sites)

**Documents** (libraries, drives) use the SharePoint docs MCP. **Modern intranet / Site Pages** (aspx content) use the separate **intranet** MCP so retrieval can search and fetch pages without treating them as generic file search.

SharePoint and Intranet maintain **independent token caches**; authenticating or clearing one does not affect the other.

Intranet MCP tools:
- `intranet_list_all_pages` — full page catalogue across all configured sites (cached locally for `INTRANET_PAGE_CACHE_TTL_HOURS`, default 4 h)
- `intranet_search` — keyword search against page titles and descriptions
- `intranet_fetch` — retrieve full page text by Graph site/page id
- `intranet_list_page_links` — enumerate child Site Page links from a hub or catalogue page
- `intranet_login` / `intranet_auth_status` — manual auth control

Configuration, guardrails, and prompting patterns are in **DOCUMENTATION.md**.

Operational recommendation:
- for broad discovery, call `intranet_list_all_pages` first — it is deterministic and cached
- check auth status before search; expect the device code prompt when the token is missing or expired
- for Site Pages and hub-style navigation, use intranet tools — not drive document search — unless you explicitly need library files

---

## Testing

See `TESTING.md` for the current suite structure, how to run tests, and what the test layers protect.

---

## Logs

Useful logs (all under **`CRISAI_LOG_DIR`**, default `./logs`) include:

```text
logs/agent_trace.jsonl
logs/crisai.log
logs/workspace_mcp.log
logs/document_mcp.log
logs/diagram_mcp.log
logs/sharepoint_mcp.log
logs/intranet_mcp.log
```

MCP stdio servers write next to the main app log so the **workspace** tree stays for documents and generated artefacts, not server diagnostics.

---

## Licence

crisAI is released under the MIT License. See the `LICENSE` file for details.
