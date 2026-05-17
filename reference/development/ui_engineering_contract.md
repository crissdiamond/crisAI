# UI Engineering Contract

This contract applies to Gem, web, and shared UI contract work. Agents must read
it before changing user-facing interfaces.

## Principles

- crisAI is a support tool for enterprise, solution, and data architects. UI
  changes should make expert work clearer, calmer, and faster.
- Gem and web should present the same workflow semantics whenever practical:
  routing, stages, checkpoints, final answers, sessions, model information, and
  cost/token indicators should use consistent names and states.
- Do not expose implementation mechanics as user experience. Translate runtime
  state into plain, useful user actions.

## Shared Styling

- Use shared style/theme contracts before adding local style values.
- Do not hardcode colours, status labels, spacing systems, or visual state
  semantics in app code unless the value is truly local and documented in the
  change summary.
- If a required style or semantic state is missing from the shared contract,
  propose or add it there first when assigned by the orchestrator.
- Keep Gem and web visually aligned within the constraints of each surface.

## Layout Invariants

- Header, navigation/stage areas, output panels, prompts, and status bars must
  keep stable dimensions during runs.
- Variable-length content must scroll, clip, paginate, or truncate
  intentionally. It must never grow past its allocated panel or cover input,
  status, or adjacent panels.
- Dynamic labels, stage names, event content, errors, and final answers must be
  bounded for narrow, normal, and large viewports.
- Do not solve overflow by hiding important meaning. Preserve the full meaning
  through scrolling, progressive disclosure, or an alternate detail view.
- For terminal UIs, test at least a narrow viewport and a normal viewport. For
  web UIs, test at least mobile-width and desktop-width layouts when practical.

## Output And Events

- The main output area is for user-meaningful progress and final answers, not
  raw transport payloads.
- Verbose mode may reveal detailed events, but raw JSON, schemas, and internal
  evidence transport should stay separated from normal prose.
- All variable output streams need the same boundary treatment. Do not make only
  final answers scroll while stage or event output can overflow.
- Stage views should help the user understand progress at a glance, not become
  a second transcript.

## Checkpoints

- Checkpoints are user decisions, not errors or implementation gates.
- The UI must explain:
  - what decision is needed;
  - the available actions;
  - the consequence of each action when space allows.
- Avoid alarming labels unless the workflow is genuinely failed or blocked by an
  error.
- Do not require the user to know internal command syntax when a surface can
  offer clear actions. If commands are the only input mechanism, present them as
  concise choices with human-readable meaning.

## Testing And Review

- UI tests should validate behaviour or contracts, not only the presence of
  implementation strings.
- Review must include layout stability, overflow handling, shared styling, and
  consistency with the other UI surface.
- The implementation handoff should state:
  - viewport sizes or scenarios tested;
  - how overflow is handled;
  - whether shared style contracts were used or extended;
  - any residual UX risk.
