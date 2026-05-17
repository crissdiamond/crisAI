# crisAI UI Workspace

This workspace contains the future React web app and Ink Gem terminal app.

The Python runtime remains authoritative for routing, agents, retrieval, sessions,
workspace access, and MCP tools. UI clients consume the local FastAPI v1 contract:

- `POST /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/events`
- `POST /api/v1/runs/{run_id}/checkpoint`
- `GET /api/v1/sessions`
- `POST /api/v1/sessions`
- `GET /api/v1/sessions/{session_name}`
- `GET /api/v1/workspace/roots`
- `GET /api/v1/workspace/tree/{root_name}`
- `GET /api/v1/workspace/file`
- `POST /api/v1/workspace/file`
- `GET /api/v1/ui/theme`

Current status:

- `packages/contracts` defines shared TypeScript types and a small runtime API client.
- `apps/web` is a React scaffold that can start runs, consume SSE events,
  apply registry-backed theme tokens, render expected stages, select/create
  sessions, show recent session history, browse/read/save editable workspace
  files, and submit retrieval checkpoint decisions.
- `apps/gem` is an Ink scaffold that uses the same contract, stage derivation,
  session APIs, and checkpoint commands (`/continue`, `/redirect <guidance>`,
  `/stop`).

The existing static web app and Textual Gem remain active until these clients
reach parity.
