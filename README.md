# crisAI

> **A local AI workstation for architecture, design, documentation, research, and controlled multi-agent critique.**

crisAI is a registry-driven local workstation that combines specialist agents, MCP tools, local and Microsoft Graph-backed retrieval, structured workflow modes, and provider-aware model assignment.

Use it to find source material, reason over it, draft architecture or documentation outputs, challenge those outputs through peer-style critique, and keep generated artefacts grounded in inspectable sources.

## What It Provides

- CLI and web app surfaces for the same routed workflows.
- Specialist agents with separate responsibilities and configurable model assignment.
- Local workspace, document, diagram, SharePoint document, and scoped intranet content MCP servers.
- Three workflow modes: `single`, `pipeline`, and `peer`.
- Task contracts that preserve the user’s main ask across retrieval, summary, design, review, and final stages.
- Deterministic retrieval expansion from registry dictionaries.
- Runtime policy gates for intranet-grounded work and file-producing workflows.
- Peer judge/verifier controls for higher-effort architecture work.
- Persistent chat sessions, route visibility, logs, and validation commands.

For the full operator manual, see [DOCUMENTATION.md](DOCUMENTATION.md). For deterministic retrieval internals, see [DOCUMENTATION_DETERMINISTIC_RETRIEVAL.md](DOCUMENTATION_DETERMINISTIC_RETRIEVAL.md).

## High-Level Architecture

```mermaid
flowchart TB
    User[User] --> Surfaces[CLI and Web App]
    Surfaces --> Router[Router and Chat State]
    Router --> Workflows[Workflow Modes]

    Workflows --> Single[Single Agent]
    Workflows --> Pipeline[Pipeline]
    Workflows --> Peer[Peer Critique]

    Single --> Agents[Specialist Agents]
    Pipeline --> Agents
    Peer --> Agents

    Registry[Registry YAML] --> Router
    Registry --> Agents
    Registry --> Runtime[MCP Runtime]
    Registry --> Models[Model Resolver]

    Agents --> Runtime
    Models --> Providers[OpenAI / Gemini / Anthropic]
    Runtime --> Sources[Workspace / Documents / Diagrams / SharePoint / Intranet]

    Workflows --> Trace[Trace and Logs]
    Workflows --> Policy[Workflow Policy and Verifiers]
```

## Workflow Shape

```mermaid
flowchart LR
    Request[User Request] --> Route[Route Decision]

    Route --> Contract[Task Contract]

    Contract -->|single| SingleAgent[Selected Agent]
    Contract -->|pipeline| RetrievalPlanner[Retrieval Planner]
    RetrievalPlanner --> ContextRetrieval[Context Retrieval]
    ContextRetrieval --> ContextSynth[Context Synthesizer]
    ContextSynth --> DraftChoice{Deliverable}
    DraftChoice -->|summary| Summary[Summary]
    DraftChoice -->|design / docs| Design[Design]
    Summary --> Review[Review when needed]
    Design --> Review
    Review --> Orchestrator[Orchestrator]

    Contract -->|peer| PeerRetrieval[Optional Retrieval]
    PeerRetrieval --> Author[Design Author]
    Author --> Challenger[Design Challenger]
    Challenger --> Refiner[Design Refiner]
    Refiner --> Judge[Judge]
    Judge -->|revise| Refiner
    Judge -->|accept| PeerFinal[Orchestrator + Verifier]

    SingleAgent --> Final[Final Output]
    Orchestrator --> Final
    PeerFinal --> Final
```

## Repository Map

```text
registry/     Agent, server, model, routing, policy, and retrieval dictionaries
prompts/      Agent prompt files and prompt-authoring guidance
src/crisai/   CLI, web app, orchestration, MCP servers, runtime, and validation code
tests/        Network-free unit, CLI, and orchestration regression tests
workspace/    Local inputs, approved context, staged drafts, outputs, sessions, and caches
runbooks/     Operational setup, security, registry, policy, and observability notes
```

## Requirements

- Python 3.10+
- Linux, macOS, or WSL on Windows
- `OPENAI_API_KEY` for OpenAI-backed agents
- Optional: Gemini or Anthropic keys when selected in `registry/models.yaml`
- Optional: Microsoft Entra app registration for SharePoint document retrieval and SharePoint-backed intranet retrieval

## Quick Install

```bash
git clone https://github.com/crissdiamond/crisAI
cd crisAI
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
cp .env.example .env
```

Set at least:

```dotenv
OPENAI_API_KEY=your_openai_api_key
CRISAI_DEFAULT_MODEL=gpt-5.4-mini
CRISAI_WORKSPACE_DIR=./workspace
CRISAI_LOG_DIR=./logs
CRISAI_REGISTRY_DIR=./registry
```

For local development, tests, linting, and type checks:

```bash
pip install -e ".[dev]"
```

For Gemini or Anthropic through LiteLLM-backed integration:

```bash
pip install -e ".[litellm]"
```

## Start

```bash
crisai doctor
./start cli
```

For the web app:

```bash
./start web
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## First Commands

Inside the CLI:

```text
/status
/list servers
/list agents
/help
```

Example one-off request:

```bash
python -m crisai.cli.main ask -m "Find the most relevant document for integration strategy and summarise it."
```

## Workflow Modes

| Mode | Purpose |
|---|---|
| `single` | Run one selected specialist agent for bounded work. |
| `pipeline` | Retrieve, synthesize, summarize or design, optionally review, then orchestrate. |
| `peer` | Run author, challenger, refiner, judge, bounded revise loops, and final verification. |

Use `/mode auto` to let the router decide, or pin a mode with `/mode single`, `/mode pipeline`, or `/mode peer`.

## Configuration

The registry is the main control plane:

- `registry/agents.yaml`: agent ids, prompts, allowed MCP servers, and model refs.
- `registry/models.yaml`: provider-specific model names and API key env vars.
- `registry/servers.yaml`: MCP server definitions and allowed tools.
- `registry/workflow_policy.yaml`: runtime hard gates.
- `registry/semantic_catalog.yaml`: legacy router, verifier, and peer-contract terms.
- `registry/semantic_graph.yaml`: task intent, deliverable, source-resolution, source-family, and retrieval topic expansion.

Run `crisai doctor` after registry edits.

## Retrieval Sources

crisAI can retrieve from:

- Approved local architecture context under `workspace/context/`.
- Local user files and generated outputs under `workspace/`.
- Supported local documents such as `.md`, `.txt`, `.csv`, `.docx`, `.pdf`, `.pptx`, and `.xlsx`; PowerPoint files expose slide-level text, tables, and extraction coverage.
- SharePoint / OneDrive documents through delegated Microsoft Graph, with opaque read handles, PowerPoint inspection tools, and validated evidence handoffs to prevent ID transcription errors.
- Published intranet pages through the scoped intranet MCP. The default provider is SharePoint Site Pages; custom providers can adapt wiki-style intranets.

SharePoint documents and SharePoint-backed intranet pages use separate MCP servers and separate token caches. Full Graph setup, auth behavior, and prompting guidance are in [DOCUMENTATION.md](DOCUMENTATION.md).

## Testing

Install dev dependencies first:

```bash
pip install -e ".[dev]"
pytest
```

Static checks:

```bash
ruff check .
mypy src
```

See [TESTING.md](TESTING.md) for the suite layout and manual Graph login smoke test.

## Logs

Logs default to `./logs`:

```text
agent_trace.jsonl
crisai.log
workspace_mcp.log
document_mcp.log
diagram_mcp.log
sharepoint_mcp.log
intranet_mcp.log
```

## More Documentation

- [DOCUMENTATION.md](DOCUMENTATION.md): full operator manual.
- [DOCUMENTATION_DETERMINISTIC_RETRIEVAL.md](DOCUMENTATION_DETERMINISTIC_RETRIEVAL.md): deterministic retrieval architecture.
- [TESTING.md](TESTING.md): test suite and development checks.
- [runbooks/](runbooks): setup, registry, policies, observability, and security.
- [prompts/README.md](prompts/README.md): prompt authoring guidance.

## Licence

crisAI is released under the MIT License. See [LICENSE](LICENSE).
