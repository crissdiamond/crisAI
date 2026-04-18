# crisAI

crisAI is a local AI tool platform for architecture, design, documentation, and research work.

This starter pack includes:
- a registry-driven catalogue of MCP servers
- a runtime manager for multiple local stdio MCP servers
- a workspace MCP server
- a diagram MCP server
- agent registry and prompt files
- a visible pipeline: discovery -> design -> review -> orchestrator
- CLI entry points
- trace logs and MCP logs

## Quick start

```bash
bash ./scripts/bootstrap.sh
vi .env
source .venv/bin/activate
export PYTHONPATH=./src
python -m crisai.cli.main list-servers
python -m crisai.cli.main list-agents
python -m crisai.cli.main ask --pipeline --verbose -m "List the files in the workspace and draft a short HLD skeleton for a federated data architecture operating model."
```

## Main logs

- `logs/agent_trace.log`
- `workspace/workspace_mcp.log`
- `workspace/diagram_mcp.log`
