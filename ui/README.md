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
- `POST /api/v1/workspace/upload`
- `GET /api/v1/ui/theme`

Current status:

- `packages/contracts` defines shared TypeScript types and a small runtime API client.
  The client can attach `Authorization: Bearer <token>` to HTTP requests and
  uses a fetch-based SSE reader when a token is configured, because browser
  `EventSource` cannot send custom headers.
- `apps/web` is a React scaffold that can start runs, consume SSE events,
  apply registry-backed theme tokens, render expected stages, select/create
  sessions, show recent session history, browse/read/save editable workspace
  files, upload source documents to task inputs or knowledge intake, and submit
  retrieval checkpoint decisions.
- `apps/gem` is an Ink scaffold that uses the same contract, stage derivation,
  session APIs, and checkpoint commands (`/continue`, `/redirect <guidance>`,
  `/stop`).

The existing static web app and Textual Gem remain active until these clients
reach parity.

Auth-aware local development:

- React web reads `VITE_CRISAI_API_KEY` and also provides an in-page API key
  control backed by browser local storage for local development.
- Ink Gem reads `CRISAI_API_KEY`.
- `./start web-react` maps `CRISAI_API_KEY` to `VITE_CRISAI_API_KEY` and
  `CRISAI_RUNTIME_URL` to `VITE_CRISAI_RUNTIME_URL` when the Vite-specific
  variables are not already set.
- `VITE_CRISAI_API_TOKEN` and `CRISAI_API_TOKEN` are accepted as temporary
  compatibility aliases.
- Both still work without a token when the local FastAPI runtime does not
  require one.
