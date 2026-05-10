# Observability

All paths default to `CRISAI_LOG_DIR` (`./logs`).

- `agent_trace.jsonl`: structured workflow events, stage outputs, deterministic retrieval metadata, policy signals, and peer decisions.
- `crisai.log`: application JSON logs.
- `workspace_mcp.log`, `document_mcp.log`, `diagram_mcp.log`, `sharepoint_mcp.log`, `intranet_mcp.log`: MCP server audit and warning logs.

Use `tail -f logs/agent_trace.jsonl logs/crisai.log` during debugging. For routing issues, compare `/status`, the web routing decision, and `DETERMINISTIC_RETRIEVAL_CONTEXT` trace entries. For SharePoint/intranet issues, check the relevant auth status tool before triggering login.

CI runs the network-free pytest suite with a per-test timeout so async or web regressions fail deterministically instead of hanging the job.
