# crisAI

crisAI is a local AI tool platform for architecture, design, documentation, and research work.

It combines:
- a registry-driven catalogue of MCP servers
- a set of specialist agents
- an interactive CLI
- local and external document retrieval
- optional peer-style critique workflows

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

---

## Architecture at a glance

crisAI is built around four layers:

1. **CLI and orchestration**
   - `src/crisai/cli/main.py`
   - command routing
   - chat loop
   - mode switching
   - review toggling
   - session history

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
