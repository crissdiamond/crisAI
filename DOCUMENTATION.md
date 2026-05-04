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
- intranet **site page** retrieval on configured SharePoint sites
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
- SharePoint / OneDrive documents server
- intranet **site pages** server (scoped to `registry/intranet.yaml`; **independent** Graph auth token cache from the SharePoint docs server)

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
/clear-session
/clear-session architecture
/session architecture
/exit
```

Outside interactive chat, you can reset a persisted session directly:

```bash
crisai clear-session --session architecture
```

Structural checks on staged or promoted corpus Markdown (`workspace/context/` and `workspace/context_staging/`) are driven by **`registry/workspace_artifact_profiles.yaml`**. The first matching profile (by declare order) supplies rules on top of `defaults`; front-matter **`type`** can be spelled with synonyms listed under `type_aliases` (for example **`HLD`** maps to **`high_level_design`**). Run validation manually:

```bash
crisai validate-artefacts
crisai validate-artefacts -p workspace/context_staging/patterns/example.md
```

The same validator runs automatically as part of the **peer post-run verifier** for Markdown files touched in that workflow (`src/crisai/orchestration/peer_verifier.py` calling `validate_workspace_artefact_paths`).

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

With **`/verbose off`** (the usual default for readable transcripts), pipeline and peer **stage output** is shown as **compact Markdown**: short headings, bullets, and recaps rather than dumping full raw model text. Turn **`/verbose on`** when you need the full verbatim stage bodies for debugging.

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
- bounded/simple tasks where one specialist is enough

### 7.2 `pipeline`
Structured flow:

```text
retrieval_planner -> context_retrieval -> context_synthesizer -> design -> review -> orchestrator
```

Best for:
- find source material
- turn source material into a draft
- critique and polish complex retrieval+drafting outputs with a mandatory review gate on that route

### 7.3 `peer`
Collaborative critique flow:

```text
optional retrieval_planner -> optional context_retrieval -> optional context_synthesizer -> design_author -> design_challenger -> design_refiner -> judge -> [refiner <-> judge iterative loop when decision=revise] -> orchestrator -> peer_verifier
```

Notes:
- `retrieval_planner` and `context_retrieval` can be skipped when retrieval is not needed for the peer task.
- when retrieval is needed and the agent is configured, `context_synthesizer` runs after context retrieval to provide a stronger evidence basis for peer stages.
- peer mode now compiles a run contract from the user request (expected output type, required side effects, grounding needs, acceptance dimensions) and injects it into peer role prompts.
- contract inference prefers `artifact_package` for file-backed staging requests (for example `context_staging` deliverables) unless the request includes clear code targets (`src/`, `tests/`, language file extensions, or explicit code symbols).
- judge output is now actionable: `Decision: revise` triggers bounded extra refiner/judge rounds (`CRISAI_PEER_MAX_REFINEMENT_ROUNDS`, default `2`) before orchestration.
- when revise loops remain unresolved, peer mode runs a bounded structural escalation (`design_author` + `design_challenger` + `design_refiner` + `judge`) driven by judge feedback (`CRISAI_PEER_MAX_ESCALATIONS`, default `1`).
- accepted peer output still passes through a post-run verifier that checks file-backed claims against on-disk artefacts (for example referenced files exist, markdown shape is present, front-matter ids are unique, and claimed mismatch notes are actually written).
- peer finalization is hard-gated: if judge does not return `accept` after the allowed loop, the run fails before orchestrator final recommendation.
- peer final prompts include a runtime changed-file manifest and require verbatim path reuse in close-out sections.
- verifier also checks close-out fidelity against changed files and flags gap/leaf contradictions in staged markdown packages.
- retrieval-gaps markdown files are exempt from mandatory `## Source` sections; semantic leaf/index artefacts still require source sections.
- if verifier failure is limited to final-text reference/close-out drift, peer mode runs one bounded final-output repair pass and re-verifies before hard failing.
- loop safeguards: max rounds bound, and a convergence guard that stops early when refiner output stops changing materially.
- workflow policy gates still apply in peer mode (see section 9.1): requests that require intranet-grounded evidence or filesystem side effects can fail fast when those outcomes are missing.

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

### `design_author`
The peer-mode authoring specialist. Produces the initial design proposal that the challenger and refiner then work from.

### `design_challenger`
The peer-mode adversarial specialist. Stress-tests assumptions and identifies weaknesses in the author's proposal.

### `design_refiner`
The peer-mode synthesis specialist. Reconciles the author's proposal with the challenger's critique into an improved position.

### `judge`
The peer-mode arbitration specialist. Evaluates the full author → challenger → refiner exchange, rules on the strongest position, and produces the final peer verdict.

### `publisher`
The packaging specialist for turning approved outputs or user requests into more formal artefacts when supported by the available tools.

---

## 9. Heuristic router

crisAI includes a Phase 1 heuristic router.

Its purpose is simple:
- if you have not explicitly chosen a mode or agent, it picks a sensible route

### 9.1 Runtime workflow policy gates

After routing selects a mode/agent path, crisAI applies a generic runtime policy layer from `registry/workflow_policy.yaml`:

- infer capabilities from request text (for example `intranet_grounded`, `produce_artifacts`)
- map capabilities to hard requirements (for example intranet fetch evidence, workspace file writes)
- fail the run with a clear error when required outcomes are missing

This keeps behaviour generic and guardrail-driven, instead of relying only on prompt compliance.

For peer mode specifically, there are two additional runtime guardrails:
- `peer_contract`: inferred from the user request and used to focus author/challenger/refiner/judge on deliverable-level outcomes.
- `peer_verifier`: validates final peer claims against filesystem state before the run is considered successful.

### 9.2 External semantic catalogue

Router and verifier semantics are configurable from `registry/semantic_catalog.yaml`:

- router term families (discovery/design/review/operations/peer/publication)
- router criticality terms for high-accuracy/high-risk prompts that can promote complex design/review asks to peer mode
- explicit routing phrase patterns
- source and architecture-location marker lists
- peer-verifier regex patterns (for example gap-line and leaf-file matching)
- peer-verifier semantic leaf-file terminology (`leaf_file_terms`) to classify architecture-oriented deliverables by filename terms (for example `patterns`, `template`, `hld`, `guides`, `standards`, `principles`, `toolkit`)
- **peer_contract** marker phrase lists (`file_write_markers`, `code_change_markers`, `code_target_markers`, `grounding_markers`, `assessment_markers`) used by `infer_peer_run_contract` (substring match on lowercased user text; inference logic stays in code)

The loader reads **only** this file (no in-code term defaults). A missing file raises `FileNotFoundError`; invalid YAML or a shape that fails validation raises `SemanticCatalogError` with a field-level message. Restart processes after edits so `load_semantic_catalog` picks up changes.

This keeps semantic/heuristic tuning maintainable outside code, similar to `registry/search_synonyms.yaml`.

### Typical routing examples

| Prompt type | Likely route |
|---|---|
| Find documents only | `single` + `retrieval_planner` |
| Find documents and draft a note | `pipeline` + review |
| Propose and critique a design | `pipeline` with review |
| Review this draft | `single` + `review` |
| Why is SharePoint login popping up? | `single` + `operations` |
| High-criticality/high-accuracy design request | `peer` |
| Broad mixed request | `pipeline` + `design` + review |
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
workspace/context_staging/
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

### Intranet site pages (scoped MCP server)

For **published SharePoint site pages** (modern intranet content), use the separate **`intranet`** MCP server — not a generic web browser.

**Available tools:**

| Tool | Purpose |
|---|---|
| `intranet_list_all_pages` | Full page catalogue across all configured sites (deterministic; uses local cache) |
| `intranet_search` | Keyword search against page titles, names, and descriptions |
| `intranet_fetch` | Retrieve full page text by `graph_site_id` + `graph_page_id` |
| `intranet_list_page_links` | Enumerate child Site Page links from a hub or catalogue page |
| `intranet_login` | Trigger interactive Microsoft Entra authentication for the intranet token cache |
| `intranet_auth_status` | Check authentication status without prompting |

**Two-stage search strategy:**

`intranet_search` runs a two-stage strategy to ensure leaf pages (e.g. `Consumer-Pattern-1`, `Producer-Pattern-2`) are never silently dropped:

1. **OData / scored pass** — Graph OData filter returns the most relevant pages first (fast, capped per site).
2. **Cache expansion** — any pages in the local catalogue that match at least one expanded query token are merged in, deduplicated, up to `max_hits`. This stage only runs when the cache is warm and adds no Graph API calls.

Both stages use **synonym-expanded tokens** (see below), so a search for "integration patterns" automatically includes "integration", "integrate", "integrations", "pattern", and "patterns" as match tokens.

Operational logs for hit counts and fetch sizes are written to **`logs/intranet_mcp.log`** (alongside other MCP logs under `CRISAI_LOG_DIR`).

**Search synonym dictionary (`registry/search_synonyms.yaml`):**

A YAML file of equivalent-term groups loaded once at provider start-up. When any token from a user query appears in a group, all other members of that group are added as additional match tokens. This allows:

- plural/singular pairs: `patterns` → also matches `pattern`
- abbreviations: `hld` → also matches `high-level-design`, `high level design`
- domain synonyms: `integration` → also matches `integrate`, `integrations`

The file is maintained independently of code — add a group when a query consistently misses relevant pages. Restart the CLI to pick up changes. The default path is `registry/search_synonyms.yaml`; override with `search_synonyms_file:` in `intranet.yaml`.

**Retrieval association graph (`registry/retrieval_association_graph.yaml`):**

A **declarative graph** (vertices with hint terms, undirected edges, `settings.max_hops`) used for **deterministic pre-expansion** before retrieval agents run. When the user message matches a vertex term (substring match for terms of five or more characters, word-boundary match for shorter terms), associated neighbour terms within `max_hops` are merged and injected into the runtime prompts for **`retrieval_planner`** and **`context_retrieval`** as a **Deterministic retrieval expansion** block (see `src/crisai/orchestration/retrieval_association_graph.py` and `src/crisai/cli/prompt_builders.py`). This keeps `prompts/retrieval_planner_agent.md` generic while you evolve topic associations in YAML. **Restart the CLI** after editing the graph.

The default graph ships with clusters aligned to common **enterprise architecture (EA)**, **data architecture (DA)**, and **solution architecture (SA)** language, for example:

- **EA:** `enterprise_architecture_core` (capabilities, value streams, target operating model, governance), `application_portfolio_architecture`, `technology_infrastructure_architecture`.
- **DA:** `data_architecture_core` (conceptual/logical/physical models, canonical and enterprise data models), `data_governance_and_management` (lineage, catalogue, MDM, data mesh/product).
- **SA / delivery:** `solution_architecture_delivery` (HLD/LLD, as-is/to-be), `architecture_views_and_notations` (viewpoints, C4/UML-style views), `quality_and_security_architecture` (NFRs, resilience, security), `integration_and_api_architecture` (APIs, EDA, SOA/microservices).
- **Integration principles (wording corpus):** `integration_principles_corpus` expands phrases such as **integration principles**, **integration strategy**, **producer/consumer flows**, and related tokens into intranet search/list hints (see `workspace/context_staging/_prompt_integration_principles.md`).

Operational vertices (`intranet_site_pages`, `document_library_boundary`, `integration_patterns_area`, `catalogue_and_leaf_drilldown`) remain linked so EA/DA/SA-style queries can still surface **intranet list/link/fetch** and **catalogue vs leaf** hints where relevant.

**Extending the graph:** add a new `vertices` entry with a stable `id` and lowercase `terms`, then add `edges` between related ids. Prefer **new vertices** over very large term lists on one node. Keep **edges sparse** so `max_hops: 2` does not over-expand unrelated hints.

**Configuration in `registry/intranet.yaml`:**

- **`provider`**: `sharepoint_pages` (default) or `wiki` (placeholder for future adapters).
- **`allow_hosts`**: optional lowercase hostnames; page `webUrl` hosts must match exactly. If omitted, hosts are **derived only** from the configured sites' `webUrl` values (still not open internet).
- **`sharepoint_pages.sites`**: list entries with either `site_path` (for example `contoso.sharepoint.com:/sites/Intranet`) or `graph_site_id`.
- **`search_synonyms_file`**: path to a synonym YAML file relative to `registry/` (default `search_synonyms.yaml`).
- **`limits`**:
  - `max_fetch_chars` — maximum characters returned by `intranet_fetch`.
  - `graph_timeout_seconds` — Graph API call timeout.
  - `page_cache_ttl_hours` — how long the `intranet_list_all_pages` catalogue is kept on disk before re-fetching (default `4`). Override at runtime with **`INTRANET_PAGE_CACHE_TTL_HOURS`** in `.env`.

**Page catalogue cache:**

`intranet_list_all_pages` stores results at `workspace/.cache/intranet_pages_cache.json`. The cache is reused until it is older than `INTRANET_PAGE_CACHE_TTL_HOURS` (env var) or `limits.page_cache_ttl_hours` (YAML). A cache miss triggers a full paginated Graph scan and updates the file. Each entry contains `title`, `web_url`, `graph_site_id`, `graph_page_id`, and `site_label`.

`intranet_list_all_pages(query="<keywords>")` accepts an optional query parameter that filters the full catalogue using the same synonym-expanded any-token matching, with no scoring cap — useful when an agent needs a comprehensive list without fetching every page.

`intranet_fetch` only accepts `graph_site_id` values that came from that configuration, so agents cannot pivot to arbitrary Graph sites.

### Best practice

- for broad or open-ended intranet requests, `intranet_search` now returns comprehensive results via cache expansion — no extra steps required for most queries
- for explicit exhaustive listing, use `intranet_list_all_pages(query="<keywords>")` — returns all catalogue matches with no cap
- after fetching any hub or catalogue page, call `intranet_list_page_links` to enumerate child pages — search may still miss pages reachable only via navigation links
- add synonym groups to `registry/search_synonyms.yaml` when a user query misses obviously relevant pages — no code change needed
- check auth status first when uncertain whether the token is still valid
- do not let the system guess identifiers; only inspect results returned in the current run
- prefer personal OneDrive when you explicitly say so

### Authentication behaviour

- SharePoint (documents) and Intranet (site pages) have **independent Microsoft Graph token caches** — resetting or re-authenticating one does not affect the other
- if a cached token is missing or expired, crisAI triggers interactive Microsoft Entra authentication automatically (CLI and web)
- on **WSL2**, crisAI uses the OAuth 2.0 **device code flow**: a URL (`https://microsoft.com/devicelogin`) and a short user code are printed to the terminal — open the URL in any browser and enter the code; no localhost redirect is required
- your Azure AD app registration must have **"Allow public client flows"** enabled (App registrations → Authentication → Advanced settings) for the device code flow to work
- site resolution (Graph `/sites/...` lookup) is **lazy**: the MCP server starts immediately and the first real tool call triggers authentication, so the CLI is never blocked during server startup

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

### 15.1 Intranet Site Pages (SharePoint publishing)

For **published site pages** (intranet articles, integration pattern pages, hub catalogues):

1. Use **`intranet_search`** for targeted or broad lookup — it now runs a two-stage strategy (OData scored pass + cache expansion with synonym-expanded tokens) so leaf pages like `Consumer-Pattern-1` are included even when they score below the OData cap.
2. For **exhaustive listing** without a scoring cap, call **`intranet_list_all_pages(query="<keywords>")`** — it filters the full catalogue with synonym expansion and no result limit.
3. Call **`intranet_fetch`** to retrieve the full body of each candidate page.
4. After fetching any hub or catalogue page, call **`intranet_list_page_links`** to enumerate child pages reachable only via navigation links.

Do **not** use generic SharePoint **document** search for `.aspx` Site Pages unless you intend library files. The Intranet MCP has its own independent Microsoft Graph token cache; check **`intranet_auth_status`** first when unsure.

### 15.2 Source finding only

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

### 15.3 Source material + design

```text
Find the most relevant source material on federated data architecture operating models, then draft a one-page HLD skeleton based on the strongest sources.
```

### 15.4 Review only

```text
Use review only. Critique this architecture note, identify weak assumptions, and suggest specific improvements.
```

### 15.5 Operations / debugging

```text
Use operations only. Investigate why SharePoint discovery is triggering interactive Microsoft Entra login even when a cached token should already exist.
```

### 15.6 Peer critique

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
logs/intranet_mcp.log
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
