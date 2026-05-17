import assert from "node:assert/strict";
import test from "node:test";
import {
  buildEventLines,
  checkpointDecisionLines,
  clampScrollTop,
  fallbackGemHeight,
  fallbackGemWidth,
  gemTerminalThemeFromPalette,
  maximumStageSidebarWidth,
  minimumGemHeight,
  minimumGemWidth,
  minimumStageSidebarWidth,
  resolveInputActive,
  resolveOutputPanelWidth,
  resolvePanelContentHeight,
  resolveStageSidebarWidth,
  resolveTranscriptHeight,
  resolveViewportDimension,
  stageVisual,
  truncateStageLabel,
  wrapPlainText,
  type GemTerminalTheme
} from "../src/viewModel.js";
import type { UiEvent } from "@crisai/contracts";

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

test("checkpoint copy is phrased as a user decision with consequences", () => {
  const lines = checkpointDecisionLines();

  assert.equal(lines[0], "Review retrieved sources");
  assert(lines[1].includes("/continue use sources"));
  assert(lines[1].includes("/redirect <guidance> refine retrieval"));
  assert(lines[1].includes("/stop end run"));
  assert(!lines.join(" ").toLowerCase().includes("requested"));
});
