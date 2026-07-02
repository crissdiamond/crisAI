---
name: crisai-ui-surfaces
description: Load before touching any crisAI user interface work — the React web client (ui/apps/web), the Ink terminal client "Gem" (ui/apps/gem), the shared TypeScript contracts package (ui/packages/contracts), UI theme tokens, or any src/crisai/schemas/ui_*.json schema. Also load when CLAUDE.md's "Web and mobile UI" section sends you to src/crisai/apps/ui/ (that directory does not exist), when a UI change needs the UCL Design System rules, when you need UI build/test commands, or when you are about to change ui_event_v1 or another Python↔TypeScript contract.
---

# crisAI UI surfaces

## The trap: CLAUDE.md's UI section points at a directory that does not exist

CLAUDE.md's "Web and mobile UI" section says the web front end lives in
`src/crisai/apps/ui/` (index.html / styles.css / app.js, "static files are served
directly by FastAPI", "do not introduce a build step"). **That directory does not
exist** and FastAPI serves no static files (no `StaticFiles`/`FileResponse` anywhere in
`src/`). The section is owner-confirmed stale as of 2026-07-02. Verify yourself:

```bash
ls src/crisai/apps/          # __init__.py  run_history.py  ui_config.py  web.py  .style.md — no ui/
grep -rn "StaticFiles" src/  # no hits
```

The real UI surfaces are:

| Surface | Location | Stack | Started by |
|---|---|---|---|
| Web client | `ui/apps/web/` (`@crisai/web`) | React 19 + Vite 7, TypeScript | `./start web` (Vite dev server, 127.0.0.1:5173) |
| "Gem" terminal client | `ui/apps/gem/` (`@crisai/gem`) | Ink 6 + React 19, TypeScript | `./start gem` |
| Shared contracts | `ui/packages/contracts/` (`@crisai/contracts`) | Plain TypeScript, one file `src/index.ts` | built by `npm --prefix ui run build:contracts` |

Both clients talk only to the FastAPI `/api/v1/*` contract served by
`src/crisai/apps/web.py` (127.0.0.1:8000). The Vite build step is legitimate — the
"no build step" and separate-vanilla-files rules in CLAUDE.md describe a legacy UI
that no longer exists.

Two more directory traps:

- Top-level `web/` and `gem/` at the repo root are **hcom dev-team context folders**
  (a README and logs), NOT source roots. Gem source is `ui/apps/gem/`; web source is
  `ui/apps/web/` (see crisai-devteam-operations for hcom).
- `src/crisai/apps/.style.md` is a **dot-prefixed file that plain `ls` hides**. It
  exists and is the authoritative design spec — do not trust any claim that it is
  absent without `ls -la src/crisai/apps/`.

## What from CLAUDE.md's UI section STILL applies

The design obligations survive the directory move and bind the React client today:

- **UCL Design System per `src/crisai/apps/.style.md`** — read that file fully before
  any visual change. It is the authoritative token spec: colour tokens
  (`--color-primary-dark #361a54`, `--color-accent-blue #30d6ff` for focus/CTAs, full
  table inside), DM Sans typography scale (12–36px tokens), **8px spacing grid**
  (`--space-1..8` = 8/12/16/24/32/40/48/64), radius capped at `--radius-md: 6px`,
  1120px container, **760px mobile breakpoint**, 360px-first responsive, 44×44px touch
  targets. `.style.md:221` itself confirms the active front end is `ui/apps/web/`.
  Do not use hex/px values that are not mapped to a token; all tokens live in
  `ui/apps/web/src/styles.css` `:root` (verified 1:1 with `.style.md` as of 2026-07-02).
- **Semantic HTML + ARIA**: native elements first; `role="alert"` for the single error
  region, `role="dialog" aria-modal` for modals, `aria-live` where needed, every
  interactive element keyboard-reachable. Follow the component class-name contract in
  `.style.md` (`.alert`, `.btn-secondary`, `.section-card`, `.toggle-switch` pattern…).
- **WCAG 2.1 AA**: ≥ 4.5:1 body-text contrast, ≥ 3:1 large text, visible focus rings
  using `--color-focus` with `outline-offset: 2px`.
- **`prefers-reduced-motion`** support — `styles.css` gates motion at three
  `@media (prefers-reduced-motion: reduce)` blocks (lines ~228, 339, 608 as of
  2026-07-02); keep any new animation behind the same guard.
- **Separation of concerns, reinterpreted for React**: `.style.md`'s
  index.html/styles.css/app.js table is legacy wording, but its intent stands — no
  inline `style="..."`, presentation via CSS classes and custom properties in
  `styles.css`, behaviour in components.

The "mobile app is a planned future surface" statement still holds: design 360px-up,
test the 760px breakpoint (`styles.css:1390` as of 2026-07-02).

## Theme tokens flow: registry → API → both clients

Colour palettes are registry-owned, not hardcoded in the clients:

```
registry/ui.yaml (schema_version: ui_theme_v1, default_theme: ucl_dark)
   └─ GET /api/v1/ui/theme          (src/crisai/apps/web.py:1495; loader :835)
        ├─ web:  cssVariablesForSurface(theme, "web")  → sets --color-* CSS custom
        │        properties from surfaces.web.css_variables (main.tsx:115-117)
        └─ gem:  resolveThemePalette(theme) → gemTerminalThemeFromPalette(palette)
                 (ui/apps/gem/src/index.tsx:410-412; viewModel.ts)
```

- `registry/ui.yaml` also owns `stage_labels` (stage key → human label), consumed by
  the Python side (`_load_stage_labels`, `src/crisai/apps/web.py:467`) when emitting
  events. Add new stage labels there, not in TS.
- Only **colour** tokens travel through the theme endpoint; typography/spacing/radius
  tokens are static in `ui/apps/web/src/styles.css`.
- `surfaces.gem.css_template` in `ui.yaml` is Textual-style CSS with **no consumer**
  in `src/` or `ui/` (verified by grep, 2026-07-02) — apparent leftover from an
  earlier Textual-based Gem; do not build on it without checking again.

## Workspace layout and build/test commands

npm workspaces rooted at `ui/package.json` (`packages/*`, `apps/*`). Node 24 in CI.
All commands verified against the package.json files, 2026-07-02:

| Task | Command (from repo root) |
|---|---|
| Install | `npm --prefix ui install` (CI uses `npm --prefix ui ci`) |
| Build contracts | `npm --prefix ui run build:contracts` (tsc → `packages/contracts/dist/`) |
| Web dev server | `npm --prefix ui run dev:web` (rebuilds contracts first, then Vite on 127.0.0.1:5173 — port hardcoded in the script) |
| Web production build | `npm --prefix ui run build:web` |
| Gem dev | `npm --prefix ui run dev:gem` (rebuilds contracts, then `tsx src/index.tsx`) |
| Gem build | `npm --prefix ui run build:gem` |
| Typecheck everything | `npm --prefix ui run typecheck` (`tsc -b`) |
| Web unit tests | `npm --prefix ui --workspace @crisai/web run test` (`tsx --test test/*.test.ts`) |
| Gem unit tests | `npm --prefix ui --workspace @crisai/gem run test` (`tsx --test test/*.test.ts`) |

**Trap:** `dev:*`/`build:*` rebuild contracts automatically; the **test scripts do
not**. Gem's `viewModel.test.ts` imports `@crisai/contracts`, which resolves to
`packages/contracts/dist/` — after editing `contracts/src/index.ts`, run
`build:contracts` before the tests or they exercise stale contract code.

Client environment (dev): web reads `VITE_CRISAI_RUNTIME_URL` (default
`http://127.0.0.1:8000`), `VITE_CRISAI_API_KEY` (alias `VITE_CRISAI_API_TOKEN`), plus
an in-page API-key control persisted in localStorage key `crisai_api_key`
(`ui/apps/web/src/lib/runtime.ts`). Gem reads `CRISAI_RUNTIME_URL`,
`CRISAI_API_KEY`/`CRISAI_API_TOKEN`, and `CRISAI_GEM_WIDTH`/`CRISAI_GEM_HEIGHT` to pin
terminal size for testing (`ui/apps/gem/src/index.tsx:81-86,260-266`). `./start web`
maps `CRISAI_API_KEY`→`VITE_CRISAI_API_KEY` and `CRISAI_RUNTIME_URL`→VITE equivalent
(`src/crisai/cli/main.py:901-908`). Full service start/stop sequence belongs to
crisai-build-run-operate; env-var catalogue to crisai-config-and-flags.

### Component map (as of 2026-07-02)

`ui/apps/web/src/`:

- `main.tsx` (~563 lines) — the App: composer-first primary flow; secondary surfaces
  (`workspace` | `history` | `memory`) mount on demand (post-redesign IA, see below).
- `components/StageRail.tsx` — workflow steps sidebar; fixed-size label+status buttons
  (`aria-pressed` select, `aria-current="step"` active); never renders streaming text.
- `components/Transcript.tsx` — focused single-stage output view; auto-follows the
  running agent unless the user pins a stage; "Follow live" release button.
- `components/CheckpointModal.tsx` — retrieval checkpoint as `role="dialog"
  aria-modal` overlay: Continue / Redirect (needs guidance text) / Stop, evidence in a
  collapsible `<details>`.
- `components/WorkspacePanel.tsx` — `WorkspaceBrowser`: roots/tree/file read-save,
  inline rename (basename only), upload to `task_inputs` | `knowledge_intake`.
- `components/SessionPanel.tsx` (`HistoryPanel`, `SessionContextBody`),
  `SharePointAuthDialog.tsx`, `StatusBadge.tsx`, `markdown.tsx`.
- `components/editors/` — content-type editor registry (`registry.ts`,
  `getEditorForPath`): `.json`/`.yaml`/`.yml`/`.py` → lazy CodeMirror 6,
  `.md` → lazy Toast UI Markdown WYSIWYG, `.txt`/`.log`/`.csv` → plain CodeMirror,
  unknown → eager `RawTextarea`. Heavy editors are code-split (~1.2MB combined);
  keep the fallback eager. Helpers: `frontMatter.ts`, `yamlLint.ts`.
- `runDisplay.ts`, `lib/runtime.ts` (shared `CrisaiRuntimeClient` instance),
  `lib/format.ts` (`humanizeError`, `isAuthError`).

`ui/apps/gem/src/`: `index.tsx` (~1272 lines, Ink rendering + input handling) and
`viewModel.ts` (~1172 lines of **pure, unit-tested** functions: layout maths, prompt
buffer, stage pinning `/stage`, navigation `/nav`, run review `/runs` `/prev`,
checkpoint slash-commands `/continue` `/redirect` `/stop`, startup-paste replay).
Keep logic in `viewModel.ts` — that is the only Gem code with tests.

`ui/packages/contracts/src/index.ts` (~814 lines, hand-written): every `Ui*` type,
stage-summary derivation, observability aggregation, theme helpers, and
`CrisaiRuntimeClient` — which uses a **fetch-based SSE reader when an API token is
configured** because browser `EventSource` cannot send `Authorization` headers
(plain `EventSource` path otherwise; Gem injects the `eventsource` npm polyfill via
`eventSourceFactory`).

## The shared `ui_event_v1` contract and the MANUAL Python↔TS sync

The run-event contract exists in **three hand-maintained places**:

1. `src/crisai/schemas/ui_event_v1.schema.json` — JSON Schema, 14 event types,
   `additionalProperties: false`.
2. `src/crisai/ui_events.py` — the frozen `UiEvent` dataclass + `make_ui_event()`
   that actually emits events.
3. `ui/packages/contracts/src/index.ts` — the TS `UiEvent` type + the 14-entry
   `UiEventType` union (duplicated a second time in the `subscribe()` listener list).

**There is no codegen and no CI drift check.** `packages/contracts/package.json` has
no schema reference; nothing validates that the three copies agree. The UI unit tests
that could catch drift are not run in CI (below). The same manual-sync risk applies to
the other UI schemas: `ui_run_request_v1`, `ui_run_state_v1`, `ui_run_history_v1`,
`ui_session_context_v1`, `ui_theme_v1` (all in `src/crisai/schemas/`), mirrored by
`UiRunRequest`, `UiRunState`, `UiRunHistory`, `UiSessionContext`, `UiTheme` in
`index.ts`. Python-side coverage is shallow: `tests/unit/test_schema_resources.py`
only checks the JSON parses; `tests/unit/test_ui_events.py` checks the dataclass
payload shape.

For a repo whose core rule is "machine-critical exchange must be schema-backed", this
TS twin is the one unguarded edge. Until a generator or drift check exists, follow
this checklist **every time you touch a `src/crisai/schemas/ui_*.json`** (or change
what `ui_events.py` / `apps/web.py` emit):

- [ ] Update `src/crisai/ui_events.py` if the event shape changed (both the
      `UiEventType` literal and the dataclass fields).
- [ ] Update `ui/packages/contracts/src/index.ts` — the type, AND the `UiEventType`
      union, AND the `eventTypes` array inside `subscribe()` if an event type was
      added/removed/renamed.
- [ ] `npm --prefix ui run build:contracts`
- [ ] `npm --prefix ui run typecheck` — surfaces most field-level drift in consumers.
- [ ] Run BOTH UI test suites locally (commands above) — **CI will not run them**.
- [ ] Grep both clients for the changed field/event name; the web transcript and Gem
      view-model switch on `event_type` strings.
- [ ] Python side: `tests/unit/test_ui_events.py`, `test_schema_resources.py`,
      `test_run_history.py`, `tests/integration/test_web_integration.py` cover the
      emitting half, and `tests/unit/test_ui_workspace.py` is a structural guard
      that string-asserts against the UI sources themselves (see below) — expect
      to update it when renaming components or scripts (test mechanics →
      crisai-validation-and-qa).

## UI test status (as of 2026-07-02)

Five test files, Node's built-in test runner via `tsx --test`:

| File | Cases (grep `test(`) | Covers |
|---|---|---|
| `ui/apps/web/test/runDisplay.test.ts` | 8 | live-stage selection, markdown parsing, display names |
| `ui/apps/web/test/editorRegistry.test.ts` | 2 | suffix→editor routing, lazy/eager structure |
| `ui/apps/web/test/frontMatter.test.ts` | 4 | front-matter split/join |
| `ui/apps/web/test/yamlLint.test.ts` | 4 | YAML diagnostics |
| `ui/apps/gem/test/viewModel.test.ts` | 72 | the entire Gem view-model |

**CI does NOT run them.** The `ui` job in `.github/workflows/ci.yml` runs only
`npm ci` → `typecheck` → `build:web` → `build:gem` — no test step. Getting them into
CI (plus browser E2E and automated WCAG checks) is tracked as **TODO-027** (P1).
Consequence: any UI logic regression that typechecks will merge green. Run the two
test commands yourself before declaring UI work done; a typecheck-only green is not
evidence (what counts as evidence → crisai-validation-and-qa).

React components themselves (main.tsx, panels, modals) have **no behavioural
tests** — only the extracted pure modules (`runDisplay`, editors helpers,
`viewModel`) do. They are, however, covered by a Python **structural guard**:
`tests/unit/test_ui_workspace.py` concatenates every `.ts`/`.tsx` file under
`ui/apps/web/src` (`_read_tree`) and asserts string presence (e.g.
`deriveStageSummaries(events`, `cssVariablesForSurface(theme, "web")`), and
also pins `ui/package.json` scripts and `ui/packages/contracts/src/index.ts`
contents — so renaming components, changing workspace scripts, or removing
helper calls fails the Python suite (commit `f57ce9b` had to update this
guard alongside its component changes). Prefer pushing new logic into the
testable pure modules.

## Regression-sensitive area: Gem prompt/paste handling

Terminal paste in Ink arrives as fragmented input sequences and has broken repeatedly.
Four dedicated fix commits, each touching `index.tsx` + `viewModel.ts` +
`viewModel.test.ts`:

| Commit | Date | Fix |
|---|---|---|
| `b80c33c` | 2026-05-17 | preserve pasted prompt text and backspace semantics |
| `b1cf3c8` | 2026-05-17 | replay startup pasted prompt |
| `ba931f4` | 2026-05-23 | preserve pasted prompt prefix |
| `9e47b80` | 2026-05-23 | append paste fragments to live prompt |

The machinery lives in `viewModel.ts` (`bufferStartupPaste`,
`shouldBufferStartupPaste`, `markStartupPasteHandled`, `insertPromptPasteText`,
`resolvePromptPasteInput`, `StartupPasteReplayState`) with timer-based replay wiring
in `index.tsx:~307-457`. If you touch the Gem prompt buffer, input handling, or
startup sequence: run the 72 view-model tests (not in CI), and manually paste
multi-line text into a live Gem session — including pasting *before* the app finishes
mounting (the startup-replay case). A second historically fragile Gem area is stage
streaming/focus (`bd195a3` cumulative deltas, `504d9f0`/`b87cd49` follow-active-agent,
`01cb87d` checkpoint-focus release) — same rule: view-model tests + live run.

## Open UX work (reference/TODO.md, as of 2026-07-02)

| Item | Priority / status | Scope |
|---|---|---|
| TODO-040 | P1, in-progress | Product-quality depth on the shared contract clients. Named follow-ups: align toggle markup with the UCL switch pattern, add alert live-region semantics, decide whether Gem gets the per-run retrieval-checkpoint toggle React web has, document upload limits in the UI. |
| TODO-040A | P2, todo | Web stage rail auto-scrolls the active stage into view — without disrupting keyboard nav or a user-pinned selection; verify mobile + reduced-motion. |
| TODO-045 | P2, todo | Editor enhancements on top of the existing registry: artefact-profile-aware fields, long-document section navigation, Mermaid preview/editing, profile-driven validation feedback. |

Done context you may see referenced: TODO-025 shipped the editor core (`1108d47`,
`671fb13`, `cf4d830`); TODO-040B shipped the checkpoint modal (`f57ce9b`), which
intentionally overlays run output while a decision is pending; TODO-019 (legacy web UI
rebuild) was superseded by the shared-contract work.

## The 2026-06-12 design audit → redesign (why the UI looks the way it does)

A Rams-principles design audit on 2026-06-12 scored the then-current web client
**16/30 → verdict REDESIGN**: eight regions rendered at once (53 interactive elements),
only colour tokens wired, internal jargon and a raw session-memory dump exposed,
contrast failures. A phased redesign was executed the same day (branch `web-redesign`,
cut over in place, **no API or `ui_event_v1` contract change**) and re-scored ~26/30.
The audit artefacts live in `DESIGN-IS-2026-06-12/` at the repo root — **gitignored,
local to this machine only** (`.gitignore:110`); a fresh clone will not have them.

Redesign decisions you must not casually undo:

- **Focused primary flow**: compose → run → answer; workspace/history/memory are
  on-demand secondary views (13 interactive elements on the default screen).
- **Plain-language labels**: "How to run" (mode), "Show detailed steps" (verbose),
  "Pause to review sources" (retrieval checkpoint); `event_type`/`agent_id` strings
  are humanised before display.
- **Single error region** (`role="alert"`), humanised 401/unreachable/run-failed copy.
- Full token system + 1120px container; stage-status colours fixed for contrast.
- Known residual polish (recorded in the audit's closing notes, still visible today):
  secondary toolbar buttons read as cards rather than tabs; the "+" new-session
  affordance; the UI still fixes `agent: "auto"` though the API accepts an agent.

## When NOT to use this skill

- **API backend behaviour** — endpoint semantics, run lifecycle, checkpoint handling,
  auth middleware, path safety in `src/crisai/apps/web.py` → crisai-architecture-contract.
- **Starting/stopping services, ports, env setup, `./start`/`./stop` anatomy** →
  crisai-build-run-operate.
- **Env var catalogue** (`CRISAI_API_KEY`, `VITE_*`, defaults and guards) →
  crisai-config-and-flags.
- **Python test mechanics, coverage gate, what counts as evidence** →
  crisai-validation-and-qa.
- **Branch/PR/commit discipline for landing a UI change** → crisai-change-control.
- **Fixing CLAUDE.md itself** (the stale UI section; CLAUDE/AGENTS/GEMINI three-way
  sync obligation) → crisai-docs-and-writing.
- **The hcom `web/`/`gem/` context folders and dev-team workflow** →
  crisai-devteam-operations.

## Provenance and maintenance

All facts verified directly against the working tree on 2026-07-02. Re-verify before
relying on anything volatile:

```bash
ls src/crisai/apps/                                        # apps/ui/ still absent; .style.md still present
grep -rn "StaticFiles" src/                                # still no static serving
grep -n '"dev"\|"test"\|"build"' ui/apps/web/package.json ui/apps/gem/package.json  # commands/ports
grep -n 'test' .github/workflows/ci.yml | grep -i ui       # UI tests still absent from CI?
ls ui/apps/web/test ui/apps/gem/test                       # test-file inventory
grep -c 'test(' ui/apps/gem/test/viewModel.test.ts         # gem case count (72 as of 2026-07-02)
grep -n 'event_type' src/crisai/schemas/ui_event_v1.schema.json  # event-type list (14)
grep -n 'UiEventType' ui/packages/contracts/src/index.ts   # TS twin still hand-written?
ls ui/packages/contracts/src/                              # still a single index.ts, no codegen
grep -n 'ui/theme' src/crisai/apps/web.py                  # theme endpoint location
grep -rn 'css_template' src/ ui/apps ui/packages --include='*.py' --include='*.ts*'  # still unconsumed?
grep -n 'TODO-040\|TODO-040A\|TODO-045\|TODO-027' reference/TODO.md  # open UX work status
git log --oneline -5 -- ui/apps/gem                        # recent Gem churn
sed -n '219,224p' src/crisai/apps/.style.md                # .style.md still names ui/apps/web/
```

Unverified/open items, labelled as such above: `surfaces.gem.css_template` consumer
(none found — treated as leftover, not fact); whether CLAUDE.md's UI section will be
rewritten (owner says stale, text unchanged as of 2026-07-02); TODO-027 CI adoption
timing.
