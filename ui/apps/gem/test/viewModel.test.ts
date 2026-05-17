import assert from "node:assert/strict";
import test from "node:test";
import {
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
  resolveInputActive,
  resolveOutputPanelWidth,
  resolvePanelLines,
  resolvePanelContentHeight,
  resolveStageSidebarWidth,
  resolveTranscriptHeight,
  resolveViewportDimension,
  sidebarStages,
  stageVisual,
  truncateStageLabel,
  wrapPlainText,
  type GemTerminalTheme
} from "../src/viewModel.js";
import type { UiEvent, UiStageSummary } from "@crisai/contracts";

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
  const event: UiEvent = {
    schema_version: "ui_event_v1",
    event_type: "stage_output",
    run_id: "run-1",
    timestamp: "2026-05-17T12:00:00Z",
    session: "default",
    status: "running",
    title: "Stage output",
    summary: "event summary",
    content: "event content",
    verbose_content: "",
    mode: "auto",
    agent_id: "summary",
    stage: "summary",
    metadata: {}
  };
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

test("checkpoint copy is phrased as a user decision with consequences", () => {
  const lines = checkpointDecisionLines();

  assert.equal(lines[0], "Review retrieved sources");
  assert(lines[1].includes("/continue use sources"));
  assert(lines[1].includes("/redirect <guidance> refine retrieval"));
  assert(lines[1].includes("/stop end run"));
  assert(!lines.join(" ").toLowerCase().includes("requested"));
});
