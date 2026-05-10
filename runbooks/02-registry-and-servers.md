# Registry And Servers

- `registry/agents.yaml` defines agent ids, prompt files, model refs, and allowed MCP servers.
- `registry/models.yaml` maps logical model refs to provider/model/API-key settings.
- `registry/servers.yaml` defines MCP stdio servers and allowed tool names.
- `registry/semantic_catalog.yaml` owns router, peer-contract, and peer-verifier terms.
- `registry/retrieval_association_graph.yaml` owns deterministic retrieval topic expansion.
- `registry/workflow_policy.yaml` maps inferred capabilities to hard runtime gates.

Run `crisai doctor` after registry edits. It checks duplicate ids, missing prompt files, unknown model refs, unknown server refs, malformed semantic/retrieval registries, unset provider key warnings, and tracked secret/cache files.

Workspace write tools are intentionally bounded. `write_workspace_file` and `append_workspace_file` default to `outputs/`, `context_staging/`, and `scratch/`, with text/markdown/data/diagram extensions only. Override cautiously with `CRISAI_WORKSPACE_WRITE_SUBDIRS`, `CRISAI_WORKSPACE_WRITE_EXTENSIONS`, and `CRISAI_WORKSPACE_MAX_WRITE_BYTES`.
