import assert from "node:assert/strict";
import test from "node:test";
import {
  buildRunListLines,
  buildEventLines,
  checkpointDecisionLines,
  clampScrollTop,
  fallbackGemHeight,
  fallbackGemWidth,
  findStagePinTarget,
  gemTerminalThemeFromPalette,
  maximumStageSidebarWidth,
  minimumGemHeight,
  minimumGemWidth,
  minimumStageSidebarWidth,
  pinnedStageContent,
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
  resolveRunsListIndex,
  resolveStageSidebarWidth,
  resolveTranscriptHeight,
  resolveViewportDimension,
  runSummaryTitle,
  sidebarStages,
  stageVisual,
  truncateStageLabel,
  wrapPlainText,
  type GemTerminalTheme
} from "../src/viewModel.js";
import type { UiEvent, UiRunSummary, UiStageSummary } from "@crisai/contracts";

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
  assert.equal(resolveTranscriptHeight(24), 13);
  assert.equal(resolvePanelContentHeight(13), 12);
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
