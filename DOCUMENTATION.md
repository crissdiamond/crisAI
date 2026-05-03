# crisAI Documentation

> **Operator manual for the local AI workstation.**
>
> This guide explains what crisAI is, how it is structured, how the CLI behaves, how routing works, how models are assigned, and how to use it effectively.

---

## 1. What crisAI is

crisAI is a local AI workstation for:

- architecture work
- technical design
- documentation drafting
- research and retrieval
- source inspection
- diagram generation
- SharePoint / OneDrive discovery
- controlled multi-agent critique

It is designed to behave like a practical workstation rather than a black-box chatbot.

That means:
- you can inspect the available agents
- you can inspect the available MCP servers
- you can control the execution mode
- you can pin or unpin the target agent
- you can keep persistent session histories
- you can choose your review preference
- you can see when routing is automatic versus pinned
- you can assign different providers and models to different agents through configuration

---

## 2. Mental model

crisAI has five main moving parts:

### 2.1 App surfaces
- **CLI**: interactive shell where you type slash commands and prompts.
- **Web**: browser interface with session history and progressive workflow tabs.

### 2.2 Agents
Specialist reasoning roles such as:
- `retrieval_planner`
- `context_retrieval`
- `context_synthesizer`
- `design`
- `review`
- `operations`
- `orchestrator`
- peer-only roles such as `design_author`, `design_challenger`, `design_refiner`, and `judge`

### 2.3 MCP servers
Tool adapters that let agents interact with the outside world.

Typical examples:
- local workspace server
- document reader server
- diagram server
- SharePoint / OneDrive server

### 2.4 Router
A lightweight heuristic layer that decides which agent or mode is most suitable when you have not explicitly chosen one.

The router distinguishes between:
- **auto routing**
- **pinned mode**
- **pinned agent**

### 2.5 Model registry
Agents do not need to hard-code provider model names anymore.

Instead:
- agents reference a logical `model_ref`
- `registry/models.yaml` defines the real provider and model mapping
- the runtime resolves the correct provider-specific model for each agent

This allows examples such as:
- `retrieval_planner` → OpenAI
- `judge` → Gemini
- `design_challenger` → Anthropic

### 2.6 Installation and virtual environment

crisAI is meant to run from a **local Python virtual environment** named **`.venv`** at the project root. The **`./start`** script activates `.venv` for both CLI and web; if `.venv` is missing, it prints short setup commands and exits.

First-time setup (full step-by-step, including `.env`, is in the repository **README**):

1. Create and activate the venv, for example:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies, for example:
   ```bash
   pip install --upgrade pip
   pip install -e .
   ```
   or `pip install -r requirements.txt` (same default install). Optional LiteLLM: `pip install -r requirements-litellm.txt`.

On **Debian / Ubuntu**, if `python3 -m venv` fails with a message about **`ensurepip`** or **`python3.x-venv` missing**, install the OS **`venv`** package for your Python version (e.g. `sudo apt install python3-venv` or `python3.12-venv`).

You can also use **`scripts/bootstrap.sh`**, which creates `.venv` if needed and runs `pip install -r requirements.txt`.

---

## 3. Starting crisAI

From the project root (after `.venv` exists and dependencies are installed):

```bash
./start cli
```

Recommended startup behaviour:
- do **not** force `--pipeline` in the launcher
- let the router decide unless you explicitly pin a mode or agent later

When crisAI opens, you are inside the interactive CLI.

To run the web interface:

```bash
./start web
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## 4. First things to try

Inside the CLI:

```text
/help
/status
/list servers
/list agents
```

These are the best first commands because they show you:
- what tooling is available
- what specialist reasoning roles exist
- whether routing is currently auto or pinned
- which models are assigned to agents by configuration

---

## 5. Slash commands

### Core commands

```text
/help
/status
/list servers
/list agents
/history
/clear
/session architecture
/exit
```

### Mode controls

```text
/mode auto
/mode single
/mode pipeline
/mode peer
```

### Review controls

```text
/review on
/review off
```

### Verbose controls

```text
/verbose on
/verbose off
```

### Agent controls

```text
/agent auto
/agent retrieval_planner
/agent design
/agent review
/agent operations
/agent orchestrator
```

### Important behaviour

- `/mode ...` pins the mode when you choose `single`, `pipeline`, or `peer`
- `/mode auto` clears the mode pin and returns control to the router
- `/agent ...` pins the agent
- `/agent auto` clears the agent pin and returns agent choice to the router
- `/status` prints the current chat state, including:
  - session
  - routing mode state
  - agent state
  - review preference
  - verbose setting
  - history count

---

## 6. Reading chat state

Typical examples:

```text
Routing: auto | Agent: auto
```

Meaning:
- the router is free to decide the most suitable mode and agent

```text
Routing: pinned:peer | Agent: auto
```

Meaning:
- mode is explicitly pinned to `peer`
- the router is still free to infer details such as retrieval need

```text
Routing: auto | Agent: pinned:design
```

Meaning:
- agent is explicitly pinned to `design`
- the router should not auto-select a different agent

---

## 7. Modes

### 7.1 `single`
Use one agent directly.

Best for:
- pure source lookup (finding documents only)
- direct design drafting
- review only
- operations/debug

### 7.2 `pipeline`
Structured flow:

```text
retrieval_planner -> context_retrieval -> context_synthesizer -> design -> optional review -> orchestrator
```

Best for:
- find source material
- turn source material into a draft
- critique and polish the draft when the routing decision says review is needed

### 7.3 `peer`
Collaborative critique flow:

```text
optional retrieval_planner -> optional context_retrieval -> design_author -> design_challenger -> design_refiner -> judge -> orchestrator
```

Notes:
- `retrieval_planner` and `context_retrieval` can be skipped when retrieval is not needed for the peer task.
- when retrieval is needed, `context_retrieval` runs after the retrieval planner to provide a stronger evidence basis for peer stages.

Best for:
- debated design work
- more rigorous challenge and refinement
- higher-effort architecture shaping

---

## 8. Agents

### `orchestrator`
General coordinator and safe fallback.

### `retrieval_planner`
Plans a compact retrieval handoff (search angles, paths, constraints) before **Context Retrieval** fetches sources. Does not retrieve documents itself.

### `context_retrieval`
The evidence retrieval specialist for local context chunks and source-grounded extracts.

### `context_synthesizer`
The context structuring specialist that turns retrieved evidence into a grounded brief for downstream design.

### `design`
The drafting and architecture specialist.

### `review`
The critique specialist.

### `operations`
The troubleshooting specialist.

### Peer-specialist agents
- `design_author`
- `design_challenger`
- `design_refiner`
- `judge`

### `publisher`
The packaging specialist for turning approved outputs or user requests into more formal artefacts when supported by the available tools.

---

## 9. Heuristic router

crisAI includes a Phase 1 heuristic router.

Its purpose is simple:
- if you have not explicitly chosen a mode or agent, it picks a sensible route

### Typical routing examples

| Prompt type | Likely route |
|---|---|
| Find documents only | `single` + `retrieval_planner` |
| Find documents and draft a note | `pipeline` |
| Propose and critique a design | `pipeline` with review |
| Review this draft | `single` + `review` |
| Why is SharePoint login popping up? | `single` + `operations` |
| Broad mixed request | `single` + `orchestrator` |
| Ask for author/challenger/refiner/judge debate | `peer` |

### Important rule

A default startup state should **not** count as a user-explicit mode selection.

---

## 10. Reading router output

You may see messages such as:

```text
[router:auto] single • retrieval_planner • review:off • retrieval:on • Prompt primarily asks for finding or inspecting sources.
```

Or:

```text
[router:pinned] peer • design_author • review:on • retrieval:off • Prompt requests peer-style proposal, challenge, refinement, and judgement.
```

This makes the router behaviour inspectable rather than hidden.

---

## 11. Retrieval discipline

This is one of the most important parts of crisAI.

### Core rules

- never guess file paths
- never guess site names
- never guess drive IDs
- never guess item IDs
- always list or search before read
- only inspect things returned by the current run
- when retrieval fails, report the actual tool failure

For architecture and documentation work, trustworthy retrieval matters more than sounding clever.

---

## 12. Workspace usage

Recommended folders:

```text
workspace/inputs/
workspace/reference/
workspace/outputs/
workspace/scratch/
workspace/chat_sessions/
```

### Good path style

```text
inputs/strategy.md
reference/integration-guidelines.pdf
```

### Bad path style

```text
workspace/inputs/strategy.md
```

Agents should work with paths relative to the workspace root.

---

## 13. SharePoint / OneDrive usage

crisAI supports delegated Microsoft Graph access for:
- SharePoint sites
- personal OneDrive
- drives, items, and documents

### Best practice

- check auth status first
- prefer personal OneDrive when you explicitly say so
- do not let the system guess identifiers
- search before read
- only inspect matching results from the current run

### Authentication behaviour

- if the cached Graph token is missing or expired, crisAI forces interactive Microsoft Entra authentication
- this applies to both CLI and web runtime paths
- on WSL, interactive Microsoft Entra login opens the browser using WSL-aware fallbacks (`wslview` or `explorer.exe`)

### Manual Graph auth smoke test

The Graph login script under `tests/orchestration/test_graph_login.py` is manual by design and skipped in automated pytest runs.

Run it directly when validating local auth/browser flow:

```bash
python tests/orchestration/test_graph_login.py
```

---

## 14. Model assignment and providers

crisAI now supports provider-aware model assignment.

### How it works

- `registry/agents.yaml` assigns a `model_ref` to each agent
- `registry/models.yaml` defines the actual provider and model name
- the runtime resolves the provider-specific model when building the agent

### Example

```yaml
agents:
  - id: retrieval_planner
    model_ref: openai_fast

  - id: judge
    model_ref: gemini_strong
```

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

### Supported provider direction

The current design is built to support:
- OpenAI
- Gemini
- Anthropic

OpenAI uses the native SDK path. Gemini and Anthropic are resolved through LiteLLM-backed integration when selected.

### Environment variables

Put provider keys in `.env`:

```dotenv
OPENAI_API_KEY=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
```

Use `.env.example` as the template for repo-safe configuration.

---

## 15. Prompting patterns

### 15.1 Source finding only

```text
Use retrieval_planner only.

Search my personal OneDrive, not SharePoint sites, and find all documents related to the integration strategy.

Rules:
- do not guess any path, drive id, or item id
- check auth status first
- search before read
- only inspect documents returned by the search
- do not draft a design or summary

Return the final result as a markdown table with these columns:
| File name | Path / Location | Last modified | Why relevant |
```

### 15.2 Source material + design

```text
Find the most relevant source material on federated data architecture operating models, then draft a one-page HLD skeleton based on the strongest sources.
```

### 15.3 Review only

```text
Use review only. Critique this architecture note, identify weak assumptions, and suggest specific improvements.
```

### 15.4 Operations / debugging

```text
Use operations only. Investigate why SharePoint discovery is triggering interactive Microsoft Entra login even when a cached token should already exist.
```

### 15.5 Peer critique

```text
Use peer mode. Produce a debated and refined architecture recommendation for a registry-driven local AI workstation with controlled MCP access.
```

---

## 16. Suggested operator habits

A good way to use crisAI in practice:

1. start with `/status`
2. check `/list servers`
3. check `/list agents`
4. begin in an unpinned state when possible
5. use `retrieval_planner` for source finding
6. use `design` when you want drafting
7. let review follow the routing decision unless you have a reason to pin behaviour
8. use `peer` for more serious challenge and refinement
9. inspect logs when behaviour looks wrong

---

## 17. Logs and troubleshooting

Useful logs (default directory **`./logs`**, override with **`CRISAI_LOG_DIR`**):

```text
logs/agent_trace.jsonl
logs/crisai.log
logs/workspace_mcp.log
logs/document_mcp.log
logs/diagram_mcp.log
logs/sharepoint_mcp.log
```

The **workspace** directory is for your documents and generated files; MCP server logs are written under the log directory with the main trace and `crisai.log`.

### If routing looks wrong
Check:
- whether startup is forcing `--pipeline`
- whether a session already pinned `/mode pipeline`
- whether `/agent ...` is still pinned
- what `/status` shows for current pin state

### If model resolution fails
Check:
- `registry/models.yaml` exists
- the referenced `model_ref` exists
- the provider key is present in `.env`
- the runtime path is loading models and passing them into the factory

### If SharePoint behaves oddly
Check:
- auth status flow
- token cache presence
- whether the server is silently failing and escalating to interactive auth

---

## 18. Closing note

crisAI works best when it is:
- retrieval-disciplined
- explicit
- inspectable
- overrideable
- boringly reliable in how it chooses tools and agents

The goal is not mystery.
The goal is a sharp local workstation that helps you think, retrieve, draft, and challenge work with confidence.
