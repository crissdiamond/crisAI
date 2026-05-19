import assert from "node:assert/strict";
import test from "node:test";
import {
  buildRunListLines,
  buildEventLines,
  buildSessionContextPreviewLines,
  checkpointDecisionLines,
  clampScrollTop,
  buildPromptView,
  bufferStartupPaste,
  consumeStartupPasteReplay,
  contextReviewUnavailableNotice,
  deletePromptBackward,
  deletePromptForward,
  fallbackGemHeight,
  fallbackGemWidth,
  findStagePinTarget,
  gemTerminalThemeFromPalette,
  insertPromptText,
  isContextCommand,
  maximumStageSidebarWidth,
  markStartupPasteHandled,
  minimumGemHeight,
  minimumGemWidth,
  minimumStageSidebarWidth,
  movePromptCursorHorizontal,
  movePromptCursorVertical,
  normalizePromptInput,
  parseContextCommand,
  pinnedStageContent,
  promptVisibleLineCount,
  promptVisualLines,
  resolveCommandHistoryMove,
  resolveCheckpointWaiting,
  formatRunSummaryTimestamp,
  resolveGhostSuffix,
  resolveInputActive,
  resolveNavCursorAfterPrune,
  resolveNavCursorMove,
  resolveOutputPanelWidth,
  resolvePanelLines,
  resolvePanelContentHeight,
  resolvePromptDeleteDirection,
  resolvePromptPasteInput,
  resolveRunsListIndex,
  resolveStageSidebarWidth,
  resolveTranscriptHeight,
  resolveViewportDimension,
  runSummaryTitle,
  shouldBufferStartupPaste,
  sidebarStages,
  stageVisual,
  truncateStageLabel,
  wrapPlainText,
  type GemTerminalTheme
} from "../src/viewModel.js";
import { deriveStageSummaries } from "@crisai/contracts";
import type { UiEvent, UiRunSummary, UiSessionContext, UiStageSummary } from "@crisai/contracts";

function uiEvent(overrides: Partial<UiEvent>): UiEvent {
  return {
    schema_version: "ui_event_v1",
    event_type: "run_created",
    run_id: "run-1",
    timestamp: "2026-05-17T12:00:00Z",
    session: "default",
    status: "running",
    title: "Run created",
    summary: "",
    content: "",
    verbose_content: "",
    mode: "auto",
    agent_id: null,
    stage: null,
    metadata: {},
    ...overrides
  };
}

function runSummary(overrides: Partial<UiRunSummary> = {}): UiRunSummary {
  return {
    run_id: "run1",
    session: "default",
    status: "completed",
    created_at: "2026-05-17T12:00:00Z",
    updated_at: "2026-05-17T12:01:00Z",
    completed_at: "2026-05-17T12:01:00Z",
    message_summary: "Summarise platform standards",
    mode: "auto",
    agent: "auto",
    expected_stages: [],
    event_count: 4,
    stage_count: 2,
    final_answer_summary: "Final answer",
    final_answer_length: 42,
    error: "",
    display_order: 1,
    ...overrides
  };
}

function sessionContext(overrides: Partial<UiSessionContext> = {}): UiSessionContext {
  return {
    schema_version: "ui_session_context_v1",
    session: "default",
    baseline_brief: "The user is preparing a platform architecture note with several open integration decisions.",
    memory: {
      task_goal: "Draft the architecture note.",
      current_state: "Reviewing source material.",
      next_actions: ["Compare options", "Write decision summary"],
      open_questions: ["Which integration pattern is preferred?"],
      important_decisions: ["Use session-scoped memory only"],
      known_sources: ["standards.md"]
    },
    budget: {
      baseline_chars: 120,
      baseline_char_limit: 500,
      recall_limit: 5,
      recall_count: 1,
      truncated: false
    },
    recall_query: "integration",
    recall_results: [
      {
        field: "important_decisions",
        content: "Prefer event-driven integration for asynchronous updates.",
        score: 0.82,
        provenance: "session_memory",
        matched_terms: ["integration"]
      }
    ],
    ...overrides
  };
}

test("Gem viewport sizing prefers valid pins and otherwise uses terminal bounds", () => {
  assert.equal(resolveViewportDimension("100", 120, fallbackGemWidth, minimumGemWidth), 100);
  assert.equal(resolveViewportDimension("0", 120, fallbackGemWidth, minimumGemWidth), 120);
  assert.equal(resolveViewportDimension("bad", undefined, fallbackGemHeight, minimumGemHeight), fallbackGemHeight);
  assert.equal(resolveViewportDimension("20", 120, fallbackGemWidth, minimumGemWidth), minimumGemWidth);
});

test("Gem layout calculations keep sidebar and transcript dimensions bounded", () => {
  assert.equal(resolveStageSidebarWidth(80), minimumStageSidebarWidth);
  assert.equal(resolveStageSidebarWidth(132), 31);
  assert.equal(resolveStageSidebarWidth(200), maximumStageSidebarWidth);
  assert.equal(resolveTranscriptHeight(24), 11);
  assert.equal(resolvePanelContentHeight(11), 10);
  assert.equal(resolveOutputPanelWidth(80, 20), 52);
  assert.equal(clampScrollTop(99, 30, 10), 20);
});

test("Gem input activates only when Ink confirms raw mode support", () => {
  assert.equal(resolveInputActive(true), true);
  assert.equal(resolveInputActive(false), false);
  assert.equal(resolveInputActive(undefined), false);
});

test("stage visuals derive semantics from the terminal theme", () => {
  const theme: GemTerminalTheme = gemTerminalThemeFromPalette({
    accent_bright: "#993BFF",
    accent_blue: "#30D6FF",
    success: "#52C152",
    warning: "#FFCA36",
    error: "#D50032",
    transcript_background: "#FAFAFA"
  });

  assert.deepEqual(stageVisual("running", theme), {
    icon: ">",
    color: "cyan",
    bold: true,
    dimColor: false
  });
  assert.equal(stageVisual("failed", theme).color, "red");
  assert.equal(stageVisual("skipped", theme).icon, "-");
  assert.equal(stageVisual("pending", theme).dimColor, true);
});

test("stage labels and event content wrap before they can exceed panel bounds", () => {
  assert.equal(truncateStageLabel("Very long retrieval planner label", 20), "Very long …");
  assert.deepEqual(wrapPlainText("alpha beta gamma delta", 10), ["alpha beta", "gamma", "delta"]);

  const event: UiEvent = {
    schema_version: "ui_event_v1",
    event_type: "stage_output",
    run_id: "run-1",
    timestamp: "2026-05-17T12:00:00Z",
    session: "default",
    status: "running",
    title: "Long title for bounded rendering",
    summary: "Summary with enough words to wrap cleanly",
    content: "Content with enough words to wrap cleanly inside the terminal panel",
    verbose_content: "",
    mode: "auto",
    agent_id: "summary",
    stage: "summary",
    metadata: {}
  };

  const lines = buildEventLines([event], "Runtime event stream disconnected.", 18);
  assert(lines.length > 4);
  assert(lines.every((line) => line.length <= 18));
});

test("event lines keep informational notices separate from errors", () => {
  const lines = buildEventLines([], "", 24, "sessions: default, draft");

  assert.deepEqual(lines, ["Info: sessions: default,", "draft"]);
  assert(!lines.join(" ").includes("Error:"));
});

test("event lines suppress duplicate summary and content body text", () => {
  const event = uiEvent({
    event_type: "stage_output",
    title: "Retrieval Planner",
    summary: "**Summary:** Retrieve the specific OneDrive deck.",
    content: "  **Summary:** Retrieve the specific OneDrive deck.\n",
    agent_id: "retrieval_planner",
    stage: "RETRIEVAL_PLANNER OUTPUT"
  });

  const lines = buildEventLines([event], "", 80);

  assert.deepEqual(lines, [
    "Retrieval Planner",
    "**Summary:** Retrieve the specific OneDrive deck.",
    ""
  ]);
});

test("event lines keep distinct content after a compact summary", () => {
  const event = uiEvent({
    event_type: "stage_output",
    title: "Retrieval Planner",
    summary: "**Summary:** Retrieve the specific OneDrive deck.",
    content: "- Query OneDrive for the exact deck title.\n- Inspect matching PowerPoint content.",
    agent_id: "retrieval_planner",
    stage: "RETRIEVAL_PLANNER OUTPUT"
  });

  const lines = buildEventLines([event], "", 80);

  assert.deepEqual(lines, [
    "Retrieval Planner",
    "**Summary:** Retrieve the specific OneDrive deck.",
    "- Query OneDrive for the exact deck title.",
    "- Inspect matching PowerPoint content.",
    ""
  ]);
});

test("event lines keep content when summary is empty", () => {
  const event = uiEvent({
    event_type: "stage_output",
    title: "Retrieval Planner",
    summary: "",
    content: "Retrieve the specific OneDrive deck.",
    agent_id: "retrieval_planner",
    stage: "RETRIEVAL_PLANNER OUTPUT"
  });

  const lines = buildEventLines([event], "", 80);

  assert.deepEqual(lines, [
    "Retrieval Planner",
    "Retrieve the specific OneDrive deck.",
    ""
  ]);
});

test("event lines preserve content with meaningful internal whitespace", () => {
  const event = uiEvent({
    event_type: "stage_output",
    title: "Retrieval Planner",
    summary: "Retrieve the deck",
    content: "Retrieve\nthe\ndeck",
    agent_id: "retrieval_planner",
    stage: "RETRIEVAL_PLANNER OUTPUT"
  });

  const lines = buildEventLines([event], "", 80);

  assert.deepEqual(lines, [
    "Retrieval Planner",
    "Retrieve the deck",
    "Retrieve",
    "the",
    "deck",
    ""
  ]);
});

test("normal event lines hide internal transport events like the web transcript", () => {
  const lines = buildEventLines([
    uiEvent({
      event_type: "run_created",
      title: "Run created",
      summary: "Transport setup."
    }),
    uiEvent({
      event_type: "routing_decision",
      title: "Routing decision",
      summary: "Internal route selected."
    }),
    uiEvent({
      event_type: "task_contract",
      title: "Task contract",
      summary: "Internal contract."
    }),
    uiEvent({
      event_type: "stage_output",
      title: "Retrieval Planner",
      summary: "Plan retrieval.",
      content: "Use workspace sources.",
      agent_id: "retrieval_planner",
      stage: "retrieval_planner"
    }),
    uiEvent({
      event_type: "checkpoint_decision",
      title: "Checkpoint decision",
      summary: "Continue."
    }),
    uiEvent({
      event_type: "run_completed",
      title: "Run completed",
      summary: "Done."
    })
  ], "", 80);
  const rendered = lines.join("\n");

  assert(rendered.includes("Retrieval Planner"));
  assert(!rendered.includes("Run created"));
  assert(!rendered.includes("Routing decision"));
  assert(!rendered.includes("Task contract"));
  assert(!rendered.includes("Checkpoint decision"));
  assert(!rendered.includes("Run completed"));
});

test("checkpoint event lines summarize evidence rows without expanding metadata bundles", () => {
  const event = uiEvent({
    event_type: "checkpoint_requested",
    title: "Review retrieved sources",
    summary: "Confirm whether these sources are sufficient.",
    content: "Raw retrieval prose with a long https://tenant.sharepoint.com/sites/team/Shared%20Documents/VeryLongFolder/VeryLongSourceName.pptx URL should stay out of normal panels.",
    verbose_content: JSON.stringify({
      evidence_bundle_v1: {
        items: [
          {
            source: {
              title: "Very Long Integration Strategy Source Deck Name That Needs Bounding.pptx",
              source_type: "sharepoint_doc",
              open_url: "https://tenant.sharepoint.com/sites/team/Shared%20Documents/VeryLongFolder/VeryLongSourceName.pptx",
              read_handle: "sharepoint_doc:secret-handle"
            },
            content_excerpt: "Sensitive excerpt"
          }
        ]
      }
    }),
    metadata: {
      evidence_bundle_v1: {
        schema_version: "evidence_bundle_v1",
        items: [
          {
            source: {
              title: "Integration Strategy Update.pptx",
              source_type: "sharepoint_doc",
              open_url: "https://tenant.sharepoint.com/sites/team/Shared%20Documents/Strategy/Integration%20Strategy%20Update.pptx",
              read_handle: "sharepoint_doc:secret-handle"
            },
            evidence_level: "content_read",
            read_status: "read",
            content_excerpt: "Do not render checkpoint excerpts here."
          },
          {
            source: {
              title: "",
              source_type: "workspace_file",
              workspace_path: "workspace/tasks/NewTest-04/artefacts/architecture-recommendation.md"
            }
          }
        ]
      }
    }
  });

  const lines = buildEventLines([event], "", 58);
  const rendered = lines.join("\n");

  assert(rendered.includes("Review retrieved sources"));
  assert(rendered.includes("Confirm whether these sources are sufficient."));
  assert(rendered.includes("Sources"));
  assert(rendered.includes("Integration Strategy Update.pptx"));
  assert(rendered.includes("architecture-recommendation.md"));
  assert(lines.every((line) => line.length <= 58));
  assert(!rendered.includes("Raw retrieval prose"));
  assert(!rendered.includes("evidence_bundle_v1"));
  assert(!rendered.includes("read_handle"));
  assert(!rendered.includes("secret-handle"));
  assert(!rendered.includes("Sensitive excerpt"));
  assert(!rendered.includes("Do not render checkpoint excerpts"));
  assert(!rendered.includes("https://tenant.sharepoint.com"));
});

test("checkpoint source rows prefer concise URL labels when no title is available", () => {
  const event = uiEvent({
    event_type: "checkpoint_requested",
    title: "Review retrieved sources",
    summary: "Confirm source fit.",
    metadata: {
      artifacts: {
        evidence_bundle_v1: {
          items: [
            {
              source: {
                source_type: "sharepoint_doc",
                open_url: "https://tenant.sharepoint.com/sites/team/Shared%20Documents/Strategy/Integration%20Strategy%20Update.pptx"
              }
            }
          ]
        }
      }
    }
  });

  const rendered = buildEventLines([event], "", 72).join("\n");

  assert(rendered.includes("tenant.sharepoint.com/.../Integration Strategy Update.pptx"));
  assert(!rendered.includes("https://tenant.sharepoint.com/sites/team"));
});

test("checkpoint waiting clears on decision or terminal event", () => {
  const requested = uiEvent({
    event_type: "checkpoint_requested",
    title: "Checkpoint requested",
    stage: "retrieval_checkpoint"
  });
  const decision = uiEvent({
    event_type: "checkpoint_decision",
    title: "Checkpoint decision",
    stage: "retrieval_checkpoint"
  });
  const completed = uiEvent({
    event_type: "run_completed",
    status: "completed",
    title: "Run completed"
  });

  assert.equal(resolveCheckpointWaiting([]), false);
  assert.equal(resolveCheckpointWaiting([requested]), true);
  assert.equal(resolveCheckpointWaiting([requested, decision]), false);
  assert.equal(resolveCheckpointWaiting([requested, completed]), false);
});

test("stage pin targets resolve by sidebar position, exact key, and label substring", () => {
  const stages = Array.from({ length: 13 }, (_, index): UiStageSummary => ({
    key: `stage_${index + 1}`,
    label: `Stage ${index + 1}`,
    status: "pending",
    summary: `summary ${index + 1}`
  }));

  assert.equal(sidebarStages(stages)[0]?.key, "stage_2");
  assert.deepEqual(findStagePinTarget(stages, "1"), {
    ok: true,
    stage: stages[1]
  });
  assert.deepEqual(findStagePinTarget(stages, "stage_1"), {
    ok: true,
    stage: stages[0]
  });
  assert.deepEqual(findStagePinTarget(stages, "Stage 13"), {
    ok: true,
    stage: stages[12]
  });
  assert.deepEqual(findStagePinTarget(stages, "9"), {
    ok: true,
    stage: stages[9]
  });
  assert.deepEqual(findStagePinTarget(stages, "missing"), {
    ok: false,
    message: "No stage: missing."
  });
  assert.deepEqual(findStagePinTarget(stages, "0"), {
    ok: false,
    message: "No stage at position 0."
  });
});

test("sidebar stages hide stale expected-only pending stages after final answer", () => {
  const expectedStages = [
    { key: "retrieval_planner", label: "retrieval_planner" },
    { key: "context_retrieval", label: "context_retrieval" },
    { key: "context_synthesizer", label: "context_synthesizer" },
    { key: "design", label: "design" },
    { key: "orchestrator", label: "orchestrator" },
    { key: "final_output", label: "final_output" }
  ];
  const events = [
    uiEvent({
      event_type: "stage_skipped",
      title: "Context Synthesizer",
      summary: "Context synthesizer skipped for summary fast path.",
      agent_id: "context_synthesizer",
      stage: "CONTEXT OUTPUT"
    }),
    uiEvent({
      event_type: "stage_output",
      title: "Summary",
      summary: "Summary answer.",
      content: "Summary answer.",
      agent_id: "summary",
      stage: "SUMMARY OUTPUT"
    }),
    uiEvent({
      event_type: "stage_skipped",
      title: "Orchestrator",
      summary: "Final orchestration skipped for summary fast path.",
      agent_id: "orchestrator",
      stage: "FINAL OUTPUT"
    }),
    uiEvent({
      event_type: "final_answer",
      title: "Final answer",
      summary: "Run completed with a final answer.",
      content: "Final summary.",
      status: "completed",
      agent_id: "final_output",
      stage: "final_output"
    })
  ];

  const keys = sidebarStages(deriveStageSummaries(events, expectedStages)).map((stage) => stage.key);

  assert(!keys.includes("design"));
  assert(keys.includes("summary"));
  assert(keys.includes("final_output"));
});

test("sidebar stages keep expected pending stages for active runs", () => {
  const stages: UiStageSummary[] = [
    { key: "retrieval_planner", label: "retrieval planner", status: "complete", summary: "done" },
    { key: "design", label: "design", status: "pending", summary: "" },
    { key: "final_output", label: "final output", status: "pending", summary: "" }
  ];

  const keys = sidebarStages(stages).map((stage) => stage.key);

  assert(keys.includes("design"));
  assert(keys.includes("final_output"));
});

test("sidebar stages hide checkpoint decision rows from the progress rail", () => {
  const expectedStages = [
    { key: "retrieval_planner", label: "retrieval_planner" },
    { key: "context_retrieval", label: "context_retrieval" },
    { key: "design", label: "design" }
  ];
  const events = [
    uiEvent({
      event_type: "stage_output",
      title: "Retrieval Planner",
      summary: "Plan retrieval.",
      agent_id: "retrieval_planner",
      stage: "RETRIEVAL_PLANNER OUTPUT"
    }),
    uiEvent({
      event_type: "checkpoint_requested",
      title: "Retrieval checkpoint",
      summary: "Retrieval evidence is ready for confirmation.",
      agent_id: "retrieval_checkpoint",
      stage: "retrieval_checkpoint"
    }),
    uiEvent({
      event_type: "checkpoint_decision",
      title: "Checkpoint decision",
      summary: "Checkpoint decision: continue.",
      agent_id: "retrieval_checkpoint",
      stage: "retrieval_checkpoint"
    })
  ];

  const keys = sidebarStages(deriveStageSummaries(events, expectedStages)).map((stage) => stage.key);

  assert(!keys.includes("retrieval_checkpoint"));
  assert(keys.includes("design"));
});

test("pinned stage content prefers event content and falls back to summary", () => {
  const event = uiEvent({
    event_type: "stage_output",
    title: "Stage output",
    summary: "event summary",
    content: "event content",
    agent_id: "summary",
    stage: "summary"
  });
  const stages: UiStageSummary[] = [
    { key: "retrieval", label: "Retrieval", status: "complete", summary: "retrieval summary" },
    { key: "summary", label: "Summary", status: "complete", summary: "summary fallback", event }
  ];

  assert.equal(pinnedStageContent(stages, "summary"), "event content");
  assert.equal(pinnedStageContent(stages, "retrieval"), "retrieval summary");
  assert.equal(pinnedStageContent(stages, "missing"), "");
  assert.equal(pinnedStageContent(stages, null), "");
});

test("panel lines keep selected stage pinned while live output changes", () => {
  const selected = resolvePanelLines({
    showEvents: false,
    selectedStage: "retrieval",
    pinnedStageLines: ["retrieval output"],
    outputLines: ["new live delta"],
    eventLines: ["event output"]
  });
  const released = resolvePanelLines({
    showEvents: false,
    selectedStage: null,
    pinnedStageLines: ["retrieval output"],
    outputLines: ["new live delta"],
    eventLines: ["event output"]
  });
  const events = resolvePanelLines({
    showEvents: true,
    selectedStage: "retrieval",
    pinnedStageLines: ["retrieval output"],
    outputLines: ["new live delta"],
    eventLines: ["event output"]
  });

  assert.deepEqual(selected, ["retrieval output"]);
  assert.deepEqual(released, ["new live delta"]);
  assert.deepEqual(events, ["event output"]);
});

test("nav cursor movement clamps and recovers when current key is missing", () => {
  const stages: UiStageSummary[] = [
    { key: "one", label: "One", status: "complete", summary: "" },
    { key: "two", label: "Two", status: "running", summary: "" },
    { key: "three", label: "Three", status: "pending", summary: "" }
  ];

  assert.equal(resolveNavCursorMove(stages, "one", "previous"), "one");
  assert.equal(resolveNavCursorMove(stages, "three", "next"), "three");
  assert.equal(resolveNavCursorMove(stages, "two", "previous"), "one");
  assert.equal(resolveNavCursorMove(stages, "two", "next"), "three");
  assert.equal(resolveNavCursorMove(stages, "missing", "next"), "one");
  assert.equal(resolveNavCursorMove(stages, "missing", "previous"), "three");
  assert.equal(resolveNavCursorMove([], "missing", "next"), null);
});

test("nav cursor prune recovery keeps prior index proximity", () => {
  const stages: UiStageSummary[] = [
    { key: "one", label: "One", status: "complete", summary: "" },
    { key: "three", label: "Three", status: "pending", summary: "" }
  ];

  assert.equal(resolveNavCursorAfterPrune(stages, 1), "three");
  assert.equal(resolveNavCursorAfterPrune(stages, 99), "three");
  assert.equal(resolveNavCursorAfterPrune(stages, -1), "one");
  assert.equal(resolveNavCursorAfterPrune(stages, null), "three");
  assert.equal(resolveNavCursorAfterPrune([], 1), null);
});

test("checkpoint copy is phrased as a user decision with consequences", () => {
  const lines = checkpointDecisionLines();

  assert.equal(lines[0], "Review retrieved sources");
  assert(lines[1].includes("/continue use sources"));
  assert(lines[1].includes("/redirect <guidance> refine retrieval"));
  assert(lines[1].includes("/stop end run"));
  assert(!lines.join(" ").toLowerCase().includes("requested"));
});

test("run list lines are bounded and expose loading, failure, and empty states", () => {
  const long = runSummary({
    message_summary: "A very long previous run title that must be truncated inside a narrow terminal",
    display_order: 1
  });
  const lines = buildRunListLines([long], 0, 42);

  assert.equal(buildRunListLines([], 0, 42, true)[0], "Loading runs...");
  assert.equal(buildRunListLines([], 0, 42, false, "failed")[0], "Could not load runs.");
  assert.equal(buildRunListLines([], 0, 42)[0], "No previous completed or failed runs.");
  assert(lines.some((line) => line.startsWith("> 1.")));
  assert(lines.some((line) => line.includes("May 17 12:01")));
  assert(lines.every((line) => line.length <= 42));
});

test("run summary timestamps use compact UTC labels and preserve unknown values", () => {
  assert.equal(formatRunSummaryTimestamp("2026-05-17T12:01:00Z"), "May 17 12:01");
  assert.equal(formatRunSummaryTimestamp("not-a-date"), "not-a-date");
  assert.equal(formatRunSummaryTimestamp(""), "");
});

test("run list navigation clamps within available history rows", () => {
  assert.equal(resolveRunsListIndex(0, 0, "next"), 0);
  assert.equal(resolveRunsListIndex(0, 3, "previous"), 0);
  assert.equal(resolveRunsListIndex(1, 3, "next"), 2);
  assert.equal(resolveRunsListIndex(2, 3, "next"), 2);
});

test("context command parser accepts show with optional query and rejects raw context access", () => {
  assert.deepEqual(parseContextCommand("/context show"), { ok: true, query: "" });
  assert.deepEqual(parseContextCommand("/context show integration risk"), {
    ok: true,
    query: "integration risk"
  });
  assert.deepEqual(parseContextCommand("/context"), {
    ok: false,
    message: "Usage: /context show [query]."
  });
  assert.deepEqual(parseContextCommand("/context raw"), {
    ok: false,
    message: "Usage: /context show [query]."
  });
});

test("context command routing supports review-mode guard notices", () => {
  assert.equal(isContextCommand("/context"), true);
  assert.equal(isContextCommand("/context show integration"), true);
  assert.equal(isContextCommand("/contextual"), false);
  assert.equal(contextReviewUnavailableNotice, "/context show is unavailable while reviewing history.");
});

test("session context preview renders bounded human-readable context without raw JSON", () => {
  const lines = buildSessionContextPreviewLines(sessionContext({
    recall_query: "integration risk review with a long phrase"
  }), { width: 36, maxRecallResults: 1 });
  const normalLines = buildSessionContextPreviewLines(sessionContext(), { width: 72, maxRecallResults: 1 });
  const rendered = lines.join("\n");

  assert(lines.some((line) => line.includes("Context preview: default")));
  assert(lines.includes("Baseline brief"));
  assert(lines.includes("Memory fields"));
  assert(lines.some((line) => line.includes("Recall: integration risk review")));
  assert(lines.some((line) => line.includes("score 0.82")));
  assert(lines.every((line) => line.length <= 36));
  assert(normalLines.every((line) => line.length <= 72));
  assert(!rendered.includes("{"));
  assert(!rendered.includes("schema_version"));
  assert(!rendered.includes("recall_results"));
});

test("session context preview exposes empty context as a quiet notice", () => {
  const lines = buildSessionContextPreviewLines(sessionContext({
    session: "",
    baseline_brief: "",
    memory: {},
    budget: {
      baseline_chars: 0,
      baseline_char_limit: 500,
      recall_limit: 5,
      recall_count: 0,
      truncated: false
    },
    recall_query: "",
    recall_results: []
  }), { width: 36 });

  assert.deepEqual(lines, ["No session context yet."]);
});

test("run summary title falls back from message summary to final answer then run id", () => {
  assert.equal(runSummaryTitle(runSummary({ message_summary: "Main ask" })), "Main ask");
  assert.equal(runSummaryTitle(runSummary({ message_summary: "", final_answer_summary: "Final" })), "Final");
  assert.equal(runSummaryTitle(runSummary({ message_summary: "", final_answer_summary: "", run_id: "abc" })), "abc");
});

test("command history recall uses Ctrl-style cycling and restores the live draft", () => {
  const history = ["/runs", "/prev 2", "draft architecture"];
  const first = resolveCommandHistoryMove(history, null, "", "/st", "previous");
  const second = resolveCommandHistoryMove(history, first.cursor, first.draft, first.prompt, "previous");
  const forward = resolveCommandHistoryMove(history, second.cursor, second.draft, second.prompt, "next");
  const live = resolveCommandHistoryMove(history, 2, "/st", "draft architecture", "next");

  assert.deepEqual(first, { prompt: "draft architecture", cursor: 2, draft: "/st" });
  assert.deepEqual(second, { prompt: "/prev 2", cursor: 1, draft: "/st" });
  assert.deepEqual(forward, { prompt: "draft architecture", cursor: 2, draft: "/st" });
  assert.deepEqual(live, { prompt: "/st", cursor: null, draft: "/st" });
});

test("ghost suffix only uses slash-command prefix matches and truncates without mutating prompt", () => {
  const history = ["normal prompt", "/session design", "/stage retrieval"];

  assert.equal(resolveGhostSuffix("", history, 20), "");
  assert.equal(resolveGhostSuffix("normal", history, 20), "");
  assert.equal(resolveGhostSuffix("/s", history, 20), "tage retrieval");
  assert.equal(resolveGhostSuffix("/stage", history, 8), " r");
  assert.equal(resolveGhostSuffix("/stage retrieval", history, 30), "");
});

test("prompt input normalizes pasted text and edits at the cursor", () => {
  const inserted = insertPromptText({ text: "hello world", cursor: 5 }, "\r\n\tthere\u001b[31m");
  assert.deepEqual(inserted, { text: "hello\n  there world", cursor: 13 });
  assert.deepEqual(deletePromptBackward(inserted), { text: "hello\n  ther world", cursor: 12 });
  assert.deepEqual(deletePromptForward({ text: "abc", cursor: 1 }), { text: "ac", cursor: 1 });
  assert.deepEqual(movePromptCursorHorizontal({ text: "abc", cursor: 0 }, "previous"), { text: "abc", cursor: 0 });
  assert.equal(normalizePromptInput("a\r\nb\rc\td"), "a\nb\nc  d");
});

test("prompt paste preserves first line and bracketed-paste initial characters", () => {
  const pasted = "\u001b[200~First line\r\nSecond line\r\nThird line\u001b[201~";
  const inserted = insertPromptText({ text: "prefix ", cursor: 7 }, pasted);

  assert.equal(inserted.text, "prefix First line\nSecond line\nThird line");
  assert.equal(inserted.cursor, inserted.text.length);
});

test("startup paste preserves first line when Ink strips the leading escape", () => {
  const raw = "\u001b[200~First line\r\nSecond line\u001b[201~";
  const inkInput = "[200~First line\r\nSecond line\u001b[201~";

  const fromRaw = insertPromptText({ text: "", cursor: 0 }, resolvePromptPasteInput(inkInput, raw));
  const fromFallback = insertPromptText({ text: "", cursor: 0 }, resolvePromptPasteInput(inkInput, ""));

  assert.equal(fromRaw.text, "First line\nSecond line");
  assert.equal(fromFallback.text, "First line\nSecond line");
  assert.equal(fromRaw.cursor, "First line\nSecond line".length);
});

test("startup paste replay buffers only raw bracketed paste and cancels on normal handling", () => {
  const raw = "\u001b[200~First line\r\nSecond line\u001b[201~";
  const empty = { pendingSequence: null };
  const buffered = bufferStartupPaste(empty, raw);
  const normal = bufferStartupPaste(empty, "First line\r\nSecond line");
  const handled = markStartupPasteHandled(buffered, raw);
  const replay = consumeStartupPasteReplay(buffered);

  assert.equal(shouldBufferStartupPaste(raw), true);
  assert.equal(shouldBufferStartupPaste("First line\r\nSecond line"), false);
  assert.deepEqual(normal, empty);
  assert.deepEqual(handled, empty);
  assert.equal(replay.sequence, raw);
  assert.deepEqual(replay.state, empty);
});

test("startup paste replay preserves prepared prompt when useInput missed first event", () => {
  const raw = "\u001b[200~First line\r\nSecond line\u001b[201~";
  const replay = consumeStartupPasteReplay(bufferStartupPaste({ pendingSequence: null }, raw));
  assert(replay.sequence !== null);

  const inserted = insertPromptText({ text: "", cursor: 0 }, replay.sequence);

  assert.equal(inserted.text, "First line\nSecond line");
  assert.equal(inserted.cursor, "First line\nSecond line".length);
});

test("prompt deletion treats terminal DEL backspace as left delete and Delete key as right delete", () => {
  assert.equal(resolvePromptDeleteDirection({ backspace: true }, ""), "backward");
  assert.equal(resolvePromptDeleteDirection({ delete: true }, "\x7f"), "backward");
  assert.equal(resolvePromptDeleteDirection({ delete: true }, "\x1b[3~"), "forward");
  assert.deepEqual(deletePromptBackward({ text: "abcd", cursor: 2 }), { text: "acd", cursor: 1 });
  assert.deepEqual(deletePromptForward({ text: "abcd", cursor: 2 }), { text: "abd", cursor: 2 });
});

test("prompt visual lines wrap logical lines and keep cursor visible in a bounded viewport", () => {
  const text = "alpha beta\ngamma";
  const lines = promptVisualLines(text, 5);

  assert.deepEqual(lines.map((line) => line.text), ["alpha", " beta", "gamma"]);
  const down = movePromptCursorVertical({ text, cursor: 2 }, 5, "next");
  const up = movePromptCursorVertical(down, 5, "previous");

  assert.equal(down.cursor, 7);
  assert.equal(up.cursor, 2);

  const view = buildPromptView("one two three four five", 18, 4, promptVisibleLineCount, "");
  assert.equal(view.lines.length, promptVisibleLineCount);
  assert.equal(view.hiddenBefore > 0, true);
  assert.equal(view.hiddenAfter, 1);
  assert.equal(view.totalLines, 6);
});

test("prompt view renders ghost suffix only on the cursor line", () => {
  const view = buildPromptView("/st", 3, 10, 4, "age retrieval");

  assert.equal(view.lines[0]?.beforeCursor, "/st");
  assert.equal(view.lines[0]?.cursorText, " ");
  assert.equal(view.lines[0]?.ghostSuffix, "age retrieval");
});

test("prompt cursor remains visible at exact visual wrap boundaries", () => {
  const view = buildPromptView("abcdEF", 4, 4, 4, "");

  assert.equal(view.cursorLine, 0);
  assert.equal(view.lines[0]?.beforeCursor, "abcd");
  assert.equal(view.lines[0]?.cursorText, " ");
  assert.equal(view.lines[1]?.beforeCursor, "EF");
  assert.equal(view.lines[1]?.cursorText, "");
});
