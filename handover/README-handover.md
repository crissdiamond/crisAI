I’m continuing work on a local AI tool platform called crisAI.

Current purpose:
- local AI platform for architecture, design, documentation, and research work
- registry-driven MCP server catalogue
- multiple agents with controlled server access
- local workspace + SharePoint retrieval
- interactive CLI

Current stack:
- Python
- OpenAI Agents SDK
- MCP servers over stdio
- registry files:
  - registry/servers.yaml
  - registry/agents.yaml
- prompts in prompts/
- CLI entry point in src/crisai/cli/main.py

Current MCP servers:
- workspace_server.py
- document_server.py
- diagram_server.py
- sharepoint_server.py

Current agent set:
- orchestrator
- discovery
- design
- review
- operations
- design_author
- design_challenger
- design_refiner
- judge

Current CLI capabilities:
- list-servers
- list-agents
- ask
- chat
- modes: single / pipeline / peer
- review off by default
- /review on and /review off supported in chat
- persistent session history
- prompt_toolkit history in CLI

Please continue from this state.
Before suggesting changes, ask me what exact next task I want to work on.
