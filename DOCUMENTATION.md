# crisAI Documentation

> **Operator manual for the local AI workstation.**
>
> Think of this as the nerdy field guide for using crisAI effectively: what it is, how it routes work, how to control it, and how to prompt it well.

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

It is designed to feel like a practical workstation rather than a black-box chatbot.

That means:
- you can inspect the available agents
- you can inspect the available servers
- you can control the mode
- you can pin the agent
- you can keep persistent session histories
- you can decide when review should run

---

## 2. Mental model

crisAI has four main moving parts:

### 2.1 CLI
The interactive shell where you type slash commands and prompts.

### 2.2 Agents
Specialist reasoning roles such as:
- `discovery`
- `design`
- `review`
- `operations`
- `orchestrator`

### 2.3 MCP servers
Tool adapters that let agents interact with the outside world.

Typical examples:
- local workspace server
- document reader server
- diagram server
- SharePoint / OneDrive server

### 2.4 Router
A lightweight heuristic layer that decides which agent or mode makes the most sense when you have not explicitly chosen one.

---

## 3. Starting crisAI

From the project root:

```bash
./start
```

Recommended startup behaviour:
- do **not** force `--pipeline` in the `start` script
- let the router decide unless you explicitly pin a mode later

When crisAI opens, you are inside the interactive CLI.

---

## 4. First things to try

Inside the CLI:

```text
/help
/list servers
/list agents
```

These are the best first commands because they show you:
- what tooling is available
- what specialist reasoning roles exist

---

## 5. Slash commands

### Core commands

```text
/help
/list servers
/list agents
/history
/clear
/session architecture
/exit
```

### Mode controls

```text
/mode single
/mode pipeline
/mode peer
```

### Review controls

```text
/review on
/review off
```

### Agent controls

```text
/agent discovery
/agent design
/agent review
/agent operations
/agent orchestrator
```

### Important behaviour

- `/mode ...` pins the mode
- `/agent ...` pins the agent
- once pinned, the router should stop auto-selecting for that dimension
- if you want the router to choose again, remove the pinned behaviour in your workflow or switch back to your preferred neutral/default setup

---

## 6. Modes

### 6.1 `single`
Use one agent directly.

Best for:
- pure discovery
- direct design drafting
- review only
- operations/debug

### 6.2 `pipeline`
Structured flow:

```text
discovery -> design -> optional review -> orchestrator
```

Best for:
- find source material
- turn source material into a draft
- optionally critique and polish the draft

### 6.3 `peer`
Collaborative critique flow:

```text
discovery -> design_author -> design_challenger -> design_refiner -> judge -> orchestrator
```

Best for:
- debated design work
- more rigorous challenge and refinement
- higher-effort architecture shaping

---

## 7. Agents

### `orchestrator`
General coordinator and safe fallback.

Use when:
- the task is broad
- the task is mixed
- you are not sure which specialist should go first

### `discovery`
The retrieval and source-finding specialist.

Use when:
- you want to find documents
- you want to inspect sources
- you want a list of relevant material
- you want evidence gathering without drafting

### `design`
The drafting and architecture specialist.

Use when:
- you want an HLD
- you want options
- you want a design note
- you want a recommendation

### `review`
The critique specialist.

Use when:
- you already have a draft
- you want challenge and gaps identified
- you want assumptions tested

### `operations`
The troubleshooting specialist.

Use when:
- something is failing
- auth keeps prompting
- a server is broken
- the CLI is behaving oddly

### Peer-specialist agents
- `design_author`
- `design_challenger`
- `design_refiner`
- `judge`

These are mainly for the `peer` workflow.

---

## 8. Heuristic router

crisAI includes a Phase 1 heuristic router.

Its purpose is simple:
- if you have not explicitly chosen a mode or agent, it picks a sensible route

### Typical routing examples

| Prompt type | Likely route |
|---|---|
| Find documents only | `single` + `discovery` |
| Find documents and draft a note | `pipeline` |
| Review this draft | `single` + `review` |
| Why is SharePoint login popping up? | `single` + `operations` |
| Broad mixed request | `single` + `orchestrator` |

### Good routing behaviour

For this prompt:

```text
Search my personal OneDrive, not SharePoint sites, and find all documents related to the integration strategy.
```

The router should normally pick:

```text
single • discovery
```

not pipeline.

### Important rule

A default startup state should **not** count as a user-explicit mode selection.

If the router says something like:

```text
pipeline • - • Mode or agent explicitly selected by user.
```

without you having actually pinned one, then something in startup or session state is still forcing a mode.

---

## 9. Retrieval discipline

This is one of the most important parts of crisAI.

### Core rules

- never guess file paths
- never guess site names
- never guess drive IDs
- never guess item IDs
- always list or search before read
- only inspect things returned by the current run
- when retrieval fails, report the actual tool failure

### Why this matters

This prevents false confidence and phantom sources.

For architecture and documentation work, trustworthy retrieval is more important than sounding clever.

---

## 10. Workspace usage

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

## 11. SharePoint / OneDrive usage

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

### Auth guidance

A good operational pattern is:
- auth status check first
- only use interactive login when actually needed
- avoid surprise browser prompts during normal discovery

---

## 12. Prompting patterns

Below are prompt patterns that work well in crisAI.

### 12.1 Discovery only

```text
Use discovery only.

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

### 12.2 Discovery + design

```text
Find the most relevant source material on federated data architecture operating models, then draft a one-page HLD skeleton based on the strongest sources.
```

### 12.3 Review only

```text
Use review only. Critique this architecture note, identify weak assumptions, and suggest specific improvements.
```

### 12.4 Operations / debugging

```text
Use operations only. Investigate why SharePoint discovery is triggering interactive web authentication even when a cached token should already exist.
```

### 12.5 Peer critique

```text
Use peer mode. Produce a debated and refined architecture recommendation for a registry-driven local AI workstation with controlled MCP access.
```

---

## 13. Prompting tips

### Be explicit about the target source
Good:

```text
Search my personal OneDrive, not SharePoint sites.
```

Less good:

```text
Find the document somewhere in Microsoft.
```

### Be explicit about the task shape
Good:

```text
Use discovery only.
Return only a markdown table.
Do not draft a design.
```

### Be explicit about guardrails
Good:

```text
Do not guess IDs or paths.
Search before read.
```

### Separate retrieval from drafting when useful
If you want better control, do this in two steps:
1. discovery task
2. design task based on identified sources

---

## 14. Example workflows

### Workflow A — find source material only

```text
Use discovery only.
Find all integration strategy documents on my personal OneDrive and return a markdown table of sources.
```

Expected route:
- `single`
- `discovery`

### Workflow B — find and draft

```text
Find the best documents related to integration strategy, inspect the strongest ones, and draft a short architecture note explaining the producer-consumer approach.
```

Expected route:
- `pipeline`

### Workflow C — critique an existing draft

```text
Use review only. Review this draft and identify gaps, risks, and ambiguities.
```

Expected route:
- `single`
- `review`

### Workflow D — debug the platform

```text
Use operations only. Investigate why the router is treating the startup mode as an explicit user selection.
```

Expected route:
- `single`
- `operations`

---

## 15. Reading router output

You may see messages such as:

```text
[router:auto] single • discovery • Prompt primarily asks for finding or inspecting sources.
```

Meaning:
- router chose automatically
- mode is `single`
- agent is `discovery`

Or:

```text
[router:pinned] pipeline • - • Mode or agent explicitly selected by user.
```

Meaning:
- a mode or agent was pinned by the user or startup path
- the router is intentionally not auto-selecting

---

## 16. Suggested operator habits

A good way to use crisAI in practice:

1. start with `/list servers`
2. check `/list agents`
3. begin in an unpinned state when possible
4. use `discovery` for source finding
5. use `design` only when you want drafting
6. keep review off unless you actually want it
7. use `peer` for more serious challenge and refinement
8. inspect logs when behaviour looks wrong

---

## 17. Logs and troubleshooting

Useful logs:

```text
logs/agent_trace.log
workspace/workspace_mcp.log
workspace/document_mcp.log
workspace/sharepoint_mcp.log
```

### If routing looks wrong
Check:
- whether startup is forcing `--pipeline`
- whether a session already pinned `/mode pipeline`
- whether `/agent ...` is still pinned

### If SharePoint behaves oddly
Check:
- auth status flow
- token cache presence
- whether the server is silently failing and escalating to interactive auth

---

## 18. Suggested prompts library

### Local architecture retrieval

```text
Use discovery only. Search the workspace inputs and reference folders for documents related to data architecture principles. Return a markdown table of relevant sources only.
```

### SharePoint / OneDrive discovery

```text
Use discovery only.
Search my personal OneDrive, not SharePoint sites, for all documents related to the integration strategy.
Check auth first, search before read, do not guess IDs or paths, and return only a markdown table with: File name, Path / Location, Last modified, Why relevant.
```

### HLD drafting

```text
Find the strongest source material related to federated data architecture operating models and draft a concise one-page HLD skeleton in British English.
```

### Diagram task

```text
Design a high-level architecture for a local AI workstation with registry-driven agents and MCP servers, then generate a Mermaid diagram for it.
```

### Review task

```text
Use review only. Challenge this design for hidden assumptions, weak boundaries, and operational risks.
```

---

## 19. Closing note

crisAI works best when it is:
- retrieval-disciplined
- explicit
- inspectable
- overrideable
- boringly reliable in how it chooses tools and agents

The goal is not mystery.
The goal is a sharp local workstation that helps you think, retrieve, draft, and challenge work with confidence.
