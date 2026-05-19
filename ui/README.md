# crisAI UI Workspace

This workspace contains the React web app and Ink Gem terminal app.

The Python runtime remains authoritative for routing, agents, retrieval, sessions,
workspace access, and MCP tools. UI clients consume the local FastAPI v1 contract:

- `POST /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/events`
- `POST /api/v1/runs/{run_id}/checkpoint`
- `GET /api/v1/sessions`
- `POST /api/v1/sessions`
- `GET /api/v1/sessions/{session_name}`
- `GET /api/v1/sessions/{session_name}/runs`
- `GET /api/v1/sessions/{session_name}/runs/{run_id}`
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
  `EventSource` cannot send custom headers. Run events include routing decisions
  and a human-readable task contract before agent execution starts. Stage text
  deltas are delivered as `stage_delta` events while supported agent runs are in
  progress.
- `apps/web` is a React scaffold that can start runs, consume SSE events,
  apply registry-backed theme tokens, render expected stages, select/create
  sessions, show recent session history, browse/read/save editable workspace
  files, upload source documents to task inputs or knowledge intake, and submit
  retrieval checkpoint decisions. Normal run transcripts hide routing,
  task-contract, and other transport events while verbose mode keeps them
  available for debugging. Final answers render common Markdown structures, and
  checkpoint cards put the decision controls before collapsible evidence detail
  so long retrieval plans stay bounded inside the transcript panel.
- `apps/gem` is an Ink scaffold that uses the same contract, stage derivation,
  session APIs, run-history APIs, and checkpoint commands (`/continue`,
  `/redirect <guidance>`, `/stop`). It renders streamed `stage_delta` output in
  the main pane while a run is active and keeps an in-session command history
  available with `Ctrl+P` and `Ctrl+N`. Slash-command history can show a dim
  ghost suffix in the prompt; Right arrow accepts the suggestion. The prompt
  panel is a fixed-height multiline editor: long prompts wrap inside the panel,
  pasted multiline text is normalized for terminal display, Left/Right moves the
  cursor, and Up/Down moves through wrapped prompt lines when the prompt spans
  multiple visible lines.
  The stage sidebar uses a terminal-relative width with minimum and maximum
  bounds, and renders compact status items from the shared theme palette so
  running, completed, skipped, failed, and pending stages are easy to scan. The
  main pane uses the same fixed scroll boundary for event summaries, streamed
  stage output, errors, and final answers. When the runtime requests a
  checkpoint, the prompt panel becomes a decision state that explains
  `/continue`, `/redirect <guidance>`, and `/stop` in user-facing terms.
  Gem can pin the output pane to a previous stage with `/stage <key>` or
  `/stage N`, where `N` is the visible sidebar position 1-9. `/stage`,
  `/stage live`, and `/stage release` release the pin and return to live/final
  output. `/nav` opens stage navigation mode for keyboard browsing: up/down or
  `j`/`k` moves the stage cursor, Enter pins the focused stage, Tab or Esc exits
  navigation mode, and `l` releases the pin. Tab also releases a pinned stage
  before resuming its normal output/events toggle.
  `/runs` opens a bounded list of completed or failed runs for the current
  session. Up/down or `j`/`k` selects a run, Enter opens read-only review, and
  Tab or Esc returns to live mode. `/prev` opens the most recent completed or
  failed run, and `/prev N` opens the Nth previous run. In review mode, `/stage`
  and `/nav` operate on the historical snapshot, while checkpoint commands show
  informational text and do not call the runtime.
  Mouse selection is deferred because Ink core does not provide reliable click
  handling across the terminal configurations crisAI supports.
  The bottom status bar shows the selected model when the runtime exposes it,
  elapsed execution time, and token/cost placeholders until provider usage
  telemetry is available. `/sessions` output is rendered as informational
  notice text rather than as an error. By default, Gem uses the current terminal
  columns and rows. `CRISAI_GEM_WIDTH` and `CRISAI_GEM_HEIGHT` can still pin the
  terminal layout size for local testing; invalid or nonpositive values fall
  back to the detected terminal size.

Auth-aware local development:

- React web reads `VITE_CRISAI_API_KEY` and also provides an in-page API key
  control backed by browser local storage for local development.
- Ink Gem reads `CRISAI_API_KEY`.
- `./start web` maps `CRISAI_API_KEY` to `VITE_CRISAI_API_KEY` and
  `CRISAI_RUNTIME_URL` to `VITE_CRISAI_RUNTIME_URL` when the Vite-specific
  variables are not already set.
- `VITE_CRISAI_API_TOKEN` and `CRISAI_API_TOKEN` are accepted as temporary
  compatibility aliases.
- Both still work without a token when the local FastAPI runtime does not
  require one.
