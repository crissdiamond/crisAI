# Registry And Servers

- `registry/agents.yaml` defines agent ids, prompt files, model refs, and allowed MCP servers.
- `registry/models.yaml` maps logical model refs to provider/model/API-key settings.
- `registry/servers.yaml` defines MCP stdio servers and allowed tool names.
- `registry/semantic_catalog.yaml` owns legacy router, peer-contract, and peer-verifier terms.
- `registry/semantic_graph.yaml` owns task intent, deliverable, source-resolution, source-family, and deterministic retrieval topic expansion semantics.
- `registry/workflow_policy.yaml` maps inferred capabilities to hard runtime gates.

Run `uv run crisai doctor` after registry edits. It checks duplicate ids, missing prompt files, unknown model refs, unknown server refs, malformed semantic registries, unset provider key warnings, and tracked secret/cache files.

### Server transports

Three transport types are supported:

- **`stdio`** — local subprocess managed by crisAI. Requires `command:` and optional `args:`. Used by all built-in servers.
- **`sse`** — remote MCP server reachable over Server-Sent Events. Requires `url:`.
- **`streamable-http`** — remote MCP server using the Streamable HTTP transport. Requires `url:`.

Remote servers (`sse`, `streamable-http`) are not started by crisAI — they must already be running at the configured `url`. Authentication is handled via:

- `api_key_env:` — name of an environment variable whose value is injected as `Authorization: Bearer <value>`.
- `headers:` — optional map of additional static HTTP headers.

See the commented example at the bottom of `registry/servers.yaml` for the full remote-server schema.

Workspace write tools are intentionally bounded. `write_workspace_file` and `append_workspace_file` default to configured writable workspace roots, with text/markdown/data/diagram extensions only. Override cautiously with `CRISAI_WORKSPACE_WRITE_SUBDIRS`, `CRISAI_WORKSPACE_WRITE_EXTENSIONS`, and `CRISAI_WORKSPACE_MAX_WRITE_BYTES`.

Use `workspace_read` for retrieval, synthesis, review, challenge, and judge agents that only need to list, search, or read workspace files. Use write-capable `workspace` only for agents that are allowed to create or update artefacts, such as design, refiner, publisher, document formatter, or orchestrator roles. The workflow runtime filters active MCP servers per stage, so an agent only receives the server ids listed in its own `allowed_servers`.

The built-in `vision` server is a stdio MCP server for workspace-bounded image inspection. It exposes `describe_image` for standalone images and `describe_powerpoint_slide_images` for picture shapes embedded in local `.pptx` files. Add `vision` to an agent's `servers:` list before expecting that agent to inspect image content; live descriptions require `OPENAI_API_KEY` and can use `CRISAI_VISION_MODEL` to override the default vision model.
