# crisAI

> **A local AI workstation for architecture, design, documentation, and research work.**

crisAI combines a registry-driven catalogue of MCP servers, a set of specialist agents, an interactive CLI, local and external document retrieval, and optional peer-style critique workflows.

The aim is to create a personal AI workstation that can retrieve source material, reason over it, draft outputs, critique them, and connect to tools such as local files, document readers, diagram generators, and SharePoint.

---

## Features

- Interactive CLI for one-off or ongoing sessions
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
- Persistent chat sessions
- Command history in the CLI
- In-chat slash commands for agent, mode, review, session, history, and registry inspection

---

## Architecture at a glance

crisAI is built around four layers:

1. **CLI and orchestration**
   - `src/crisai/cli/main.py`
   - `src/crisai/cli/chat_session.py`
   - `src/crisai/cli/commands.py`
   - `src/crisai/cli/pipelines.py`
   - `src/crisai/cli/prompt_builders.py`
   - `src/crisai/cli/display.py`
   - command routing
   - chat loop
   - mode switching
   - review toggling
   - session history
   - in-chat slash commands

2. **Agents**
   - configured in `registry/agents.yaml`
   - prompts stored in `prompts/`
   - created by `src/crisai/agents/factory.py`

3. **MCP servers**
   - configured in `registry/servers.yaml`
   - built and managed by `src/crisai/runtime.py`

4. **Sources**
   - local workspace
   - document parser
   - diagram generator
   - SharePoint / OneDrive via Microsoft Graph

---

## Current components

### MCP servers
Typical servers include:

- `workspace_server.py`
  - local file listing
  - text reads
  - note writes
  - workspace search

- `document_server.py`
  - extracts text from common document formats

- `diagram_server.py`
  - Mermaid generation and validation

- `sharepoint_server.py`
  - delegated Microsoft Graph authentication
  - SharePoint / OneDrive site, drive, and document access

### Agents
Typical agent set:

- `orchestrator`
- `discovery`
- `design`
- `review`
- `operations`
- `design_author`
- `design_challenger`
- `design_refiner`
- `judge`

---

## Project structure

```text
crisAI/
  start
  README.md
  requirements.txt
  .env.example

  registry/
    servers.yaml
    agents.yaml

  prompts/
    orchestrator.md
    discovery_agent.md
    design_agent.md
    review_agent.md
    design_author.md
    design_challenger.md
    design_refiner.md
    judge.md

  src/
    crisai/
      cli/
        main.py
        chat_session.py
        commands.py
        display.py
        pipelines.py
        prompt_builders.py
      agents/
        factory.py
      servers/
        workspace_server.py
        document_server.py
        diagram_server.py
        sharepoint_server.py
      config.py
      registry.py
      runtime.py
      tracing.py

  workspace/
    inputs/
    reference/
    outputs/
    scratch/
    chat_sessions/

  logs/
```

---

## Requirements

Before getting started, make sure you have:

- **Python 3.10+**
- **Linux, macOS, or WSL on Windows**
- **OpenAI API key**
- **Optional:** Microsoft Entra app registration for SharePoint access

---

## Installation

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd crisAI
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
```

### 3. Activate the virtual environment

**Linux / macOS / WSL:**

```bash
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Create your environment file

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

Optional SharePoint settings:

```dotenv
MS_TENANT_ID=your_tenant_id
MS_CLIENT_ID=your_client_id
MS_TOKEN_CACHE_PATH=./workspace/.auth/msal_token_cache.json
MS_TOKEN_INFO_PATH=./workspace/.auth/msal_token_info.json
```

### 6. Make the launcher executable

```bash
chmod +x start
```

### 7. Start crisAI

```bash
./start
```

This opens the interactive CLI directly.

---

## What the `start` script should do

The `start` launcher is expected to:

- activate `.venv`
- load `.env`
- set `PYTHONPATH=./src`
- open the crisAI interactive CLI

---

## Quick start

Start crisAI:

```bash
./start
```

Once inside the interactive CLI, you can use slash commands such as:

```text
/list-servers
/list-agents
/mode pipeline
/mode peer
/review on
/review off
/session architecture
/history
/help
```

Then type your prompt directly in the CLI.

Example prompts:

```text
Find the most relevant document for integration strategy and summarise it.
```

```text
Use the workspace tools first. Find documents related to integration strategy in inputs and reference, identify the best match, and summarise it.
```

```text
Use SharePoint tools first. Find the IT Architecture site and identify the most relevant document related to integration strategy.
```

---

## CLI modes

### `single`
Runs one selected agent directly.

### `pipeline`
Runs the main structured flow:

1. Discovery
2. Design
3. optional Review
4. Orchestrator

### `peer`
Runs the peer-style flow:

1. Discovery
2. Design Author
3. optional Challenger
4. optional Refiner
5. optional Judge
6. Orchestrator

---

## Review behaviour

Review is **off by default**.

Inside the CLI:

```text
/review on
/review off
```

You can also switch between modes while staying in the same chat session:

```text
/mode single
/mode pipeline
/mode peer
```

---

## Chat commands

Inside the interactive CLI:

```text
/help
/list-servers
/list-agents
/mode single
/mode pipeline
/mode peer
/review on
/review off
/agent discovery
/history
/session architecture
/clear
/exit
```

Notes:
- `/list-servers` shows the registered MCP servers available to the platform
- `/list-agents` shows the registered agents and their configured model/server access
- these are available directly inside the CLI, without leaving the chat session

---

## Persistent chat history

crisAI stores chat history by session in:

```text
workspace/chat_sessions/
```

Typical usage is through the interactive CLI started with:

```bash
./start
```

Then switch or create sessions from within chat:

```text
/session architecture
/session sharepoint-debug
```

---

## Workspace usage

Recommended local source locations:

```text
workspace/inputs/
workspace/reference/
```

Generated material:

```text
workspace/outputs/
workspace/scratch/
```

Workspace paths are always relative to the workspace root.

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

## Engineering guidance

### Registry-driven design

MCP servers and agents are configured through:

```text
registry/servers.yaml
registry/agents.yaml
```

### Prompts

Agent behaviour is controlled through prompt files in `prompts/`.

For CLI orchestration and mode behaviour, the interactive layer may also use dedicated prompt-building helpers under:

```text
src/crisai/cli/prompt_builders.py
```

### Retrieval discipline

The system should follow these rules:

- never guess file paths, site names, drive IDs, or item IDs
- always list or search before reading
- only read a path or item returned in the current run
- report exact tool errors when retrieval fails

---

## SharePoint auth

SharePoint access is delegated and tied to the signed-in user.

The expected flow is:

1. Microsoft Entra app registration
2. delegated Microsoft Graph permissions
3. MSAL token caching
4. Graph access through `sharepoint_server.py`

---

## Logs

Useful logs include:

```text
logs/agent_trace.log
workspace/workspace_mcp.log
workspace/document_mcp.log
workspace/sharepoint_mcp.log
```

---

## Example prompts

### Local retrieval

> Use the workspace tools first. Find documents related to integration strategy in inputs and reference, identify the best match, and summarise it.

### SharePoint retrieval

> Use SharePoint tools first. Find the IT Architecture site and identify the most relevant document related to integration strategy.

### Design task

> Use the available tools first. Identify the most relevant source for federated data architecture operating model work, summarise it, and draft a one-page HLD skeleton based on that material.

---

## SharePoint setup summary

To enable SharePoint access, you typically need:

- a Microsoft Entra app registration
- a public client / localhost redirect setup
- delegated Microsoft Graph permissions such as:
  - `User.Read`
  - `Sites.Read.All`
  - `Files.Read.All`
- tenant consent where required

The SharePoint MCP server then uses delegated auth and Microsoft Graph to list sites, drives, items, search documents, and read supported file content.

---

## Licence

crisAI is released under the MIT License. See the LICENSE file for details.
