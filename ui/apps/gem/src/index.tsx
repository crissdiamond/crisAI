#!/usr/bin/env node
import chalk from "chalk";
import React, { useMemo, useRef, useState } from "react";
import { EventSource } from "eventsource";
import { Box, render, Text, useInput, useStdin, useStdout } from "ink";
import {
  CrisaiRuntimeClient,
  deriveStageSummaries,
  isTerminalEvent,
  latestFinalContent,
  resolveThemePalette,
  type UiEvent,
  type UiRunDetail,
  type UiRunState,
  type UiRunSummary,
  type UiSessionContext,
  type UiSessionState,
  type UiStageSummary
} from "@crisai/contracts";
import {
  buildRunListLines,
  buildEventLines,
  buildSessionContextPreviewLines,
  checkpointDecisionLines,
  clampScrollTop,
  bufferStartupPaste,
  defaultGemTerminalTheme,
  deletePromptBackward,
  deletePromptForward,
  fallbackGemHeight,
  fallbackGemWidth,
  findStagePinTarget,
  buildPromptView,
  gemTerminalThemeFromPalette,
  insertPromptText,
  parseContextCommand,
  minimumGemHeight,
  minimumGemWidth,
  movePromptCursorHorizontal,
  movePromptCursorVertical,
  markStartupPasteHandled,
  normalizePromptInput,
  pinnedStageContent,
  resolveCommandHistoryMove,
  promptPanelHeight,
  promptVisibleLineCount,
  resolveGhostSuffix,
  resolveRunsListIndex,
  resolveNavCursorAfterPrune,
  resolveCheckpointWaiting,
  resolveInputActive,
  resolveNavCursorMove,
  resolveOutputPanelWidth,
  resolvePanelLines,
  resolvePanelContentHeight,
  resolvePromptDeleteDirection,
  resolvePromptPasteInput,
  resolveStageSidebarWidth,
  resolveTranscriptHeight,
  resolveViewportDimension,
  runSummaryTitle,
  sidebarStages,
  stageVisual,
  shouldBufferStartupPaste,
  truncateStageLabel,
  wrapPlainText,
  type DisplayMode,
  type GemTerminalTheme,
  type PromptBufferState,
  type StartupPasteReplayState
} from "./viewModel.js";

const runtimeBaseUrl = process.env.CRISAI_RUNTIME_URL ?? "http://127.0.0.1:8000";

const runtime = new CrisaiRuntimeClient({
  baseUrl: runtimeBaseUrl,
  apiToken: process.env.CRISAI_API_KEY ?? process.env.CRISAI_API_TOKEN,
  eventSourceFactory: (url) => new EventSource(url) as unknown as globalThis.EventSource
});

// --- Markdown rendering ---

function renderMarkdownLines(text: string, width = 100): string[] {
  if (!text) return [];
  const lines = text.split("\n");
  const result: string[] = [];
  let inCodeBlock = false;
  let codeLang = "";

  for (const raw of lines) {
    const fence = raw.match(/^```(\w*)$/);
    if (fence !== null) {
      if (!inCodeBlock) {
        inCodeBlock = true;
        codeLang = fence[1] || "code";
        result.push(chalk.dim(`┌─ ${codeLang} ` + "─".repeat(Math.max(2, 36 - codeLang.length))));
      } else {
        inCodeBlock = false;
        codeLang = "";
        result.push(chalk.dim("└" + "─".repeat(39)));
      }
      continue;
    }

    if (inCodeBlock) {
      for (const line of wrapPlainText(raw, Math.max(8, width - 2))) {
        result.push("  " + chalk.cyan(line));
      }
      continue;
    }

    if (raw.startsWith("### ")) {
      result.push(...wrapPlainText(raw.slice(4), width).map((line) => chalk.bold(line)));
      continue;
    }
    if (raw.startsWith("## "))  {
      result.push(...wrapPlainText(raw.slice(3), width).map((line) => chalk.bold.underline(line)));
      continue;
    }
    if (raw.startsWith("# "))   {
      result.push(...wrapPlainText(raw.slice(2), width).map((line) => chalk.bold.underline(line)));
      continue;
    }

    if (/^[-*_]{3,}$/.test(raw.trim())) {
      result.push(chalk.dim("─".repeat(40)));
      continue;
    }

    if (raw.startsWith("> ")) {
      for (const line of wrapPlainText(raw.slice(2), Math.max(8, width - 2))) {
        result.push(chalk.dim("│ ") + chalk.italic(renderInline(line)));
      }
      continue;
    }

    const ulMatch = raw.match(/^(  )?[-*+] (.*)/);
    if (ulMatch) {
      const indent = ulMatch[1] ? "    " : "  ";
      const wrapped = wrapPlainText(ulMatch[2], Math.max(8, width - indent.length - 2));
      wrapped.forEach((line, index) => {
        result.push(index === 0
          ? indent + chalk.yellow("•") + " " + renderInline(line)
          : `${indent}  ${renderInline(line)}`);
      });
      continue;
    }

    const olMatch = raw.match(/^(\d+)\. (.*)/);
    if (olMatch) {
      const prefix = `  ${olMatch[1]}. `;
      const wrapped = wrapPlainText(olMatch[2], Math.max(8, width - prefix.length));
      wrapped.forEach((line, index) => {
        result.push(index === 0
          ? "  " + chalk.yellow(olMatch[1] + ".") + " " + renderInline(line)
          : " ".repeat(prefix.length) + renderInline(line));
      });
      continue;
    }

    if (raw.startsWith("    ")) {
      for (const line of wrapPlainText(raw.trimStart(), Math.max(8, width - 2))) {
        result.push("  " + chalk.cyan(line));
      }
      continue;
    }

    result.push(...wrapPlainText(raw, width).map(renderInline));
  }

  return result;
}

function renderInline(text: string): string {
  text = text.replace(/\*\*\*(.*?)\*\*\*/gs, (_: string, g: string) => chalk.bold.italic(g));
  text = text.replace(/\*\*(.*?)\*\*/gs, (_: string, g: string) => chalk.bold(g));
  text = text.replace(/\*(.*?)\*/gs, (_: string, g: string) => chalk.italic(g));
  text = text.replace(/`([^`]+)`/g, (_: string, g: string) => chalk.cyan(g));
  text = text.replace(/~~(.*?)~~/gs, (_: string, g: string) => chalk.strikethrough(g));
  return text;
}

// --- Components ---

function ScrollPane({
  lines,
  height,
  scrollTop,
}: {
  lines: string[];
  height: number;
  scrollTop: number;
}) {
  const contentH = Math.max(1, height - 1);
  const visible = lines.slice(scrollTop, scrollTop + contentH);
  const padCount = Math.max(0, contentH - visible.length);
  const lineEnd = Math.min(scrollTop + contentH, lines.length);
  const pct = lines.length > 0 ? Math.round((lineEnd / lines.length) * 100) : 100;

  return (
    <Box flexDirection="column" height={height}>
      {visible.map((line, i) => (
        <Text key={`line-${scrollTop + i}`}>{line || " "}</Text>
      ))}
      {Array.from({ length: padCount }, (_, i) => (
        <Text key={`pad-${i}`}> </Text>
      ))}
      <Text dimColor>
        {scrollTop > 0 ? "↑ " : "  "}
        {`line ${lineEnd}/${lines.length} (${pct}%)`}
        {lineEnd < lines.length ? " ↓" : "  "}
        {"  · ↑↓ / PgUp PgDn"}
      </Text>
    </Box>
  );
}

function StageItem({
  stage,
  sidebarWidth,
  theme,
  selected
}: {
  stage: UiStageSummary;
  sidebarWidth: number;
  theme: GemTerminalTheme;
  selected: boolean;
}) {
  const visual = stageVisual(stage.status, theme);
  const shortLabel = truncateStageLabel(stage.label, sidebarWidth);

  return (
    <Text
      bold={visual.bold}
      color={visual.color}
      dimColor={visual.dimColor}
      inverse={selected}
      wrap="truncate-end"
    >
      [{visual.icon} {shortLabel}]
    </Text>
  );
}

// --- Main app ---

function GemApp() {
  const { stdout } = useStdout();
  const { internal_eventEmitter: inputEvents, isRawModeSupported } = useStdin();
  const inputActive = resolveInputActive(isRawModeSupported);
  const viewportWidth = resolveViewportDimension(
    process.env.CRISAI_GEM_WIDTH,
    stdout?.columns,
    fallbackGemWidth,
    minimumGemWidth
  );
  const viewportHeight = resolveViewportDimension(
    process.env.CRISAI_GEM_HEIGHT,
    stdout?.rows,
    fallbackGemHeight,
    minimumGemHeight
  );
  const stageSidebarWidth = resolveStageSidebarWidth(viewportWidth);
  const transcriptHeight = resolveTranscriptHeight(viewportHeight);
  const outputPanelWidth = resolveOutputPanelWidth(viewportWidth, stageSidebarWidth);
  const promptEditorWidth = Math.max(8, viewportWidth - 6);

  const [prompt, setPrompt] = useState("");
  const [promptCursor, setPromptCursor] = useState(0);
  const [run, setRun] = useState<UiRunState | null>(null);
  const [events, setEvents] = useState<UiEvent[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [terminalTheme, setTerminalTheme] = useState(defaultGemTerminalTheme);
  const [session, setSession] = useState("default");
  const [sessions, setSessions] = useState<string[]>(["default"]);
  const [scrollTop, setScrollTop] = useState(0);
  const [showEvents, setShowEvents] = useState(false);
  const [selectedStage, setSelectedStage] = useState<string | null>(null);
  const [navMode, setNavMode] = useState(false);
  const [navFocusKey, setNavFocusKey] = useState<string | null>(null);
  const [commandHistory, setCommandHistory] = useState<string[]>([]);
  const [historyCursor, setHistoryCursor] = useState<number | null>(null);
  const [displayMode, setDisplayMode] = useState<DisplayMode>("live");
  const [runHistory, setRunHistory] = useState<UiRunSummary[]>([]);
  const [runHistoryLoading, setRunHistoryLoading] = useState(false);
  const [runHistoryFailure, setRunHistoryFailure] = useState("");
  const [selectedRunIndex, setSelectedRunIndex] = useState(0);
  const [reviewRun, setReviewRun] = useState<UiRunDetail | null>(null);
  const [sessionContext, setSessionContext] = useState<UiSessionContext | null>(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [contextFailure, setContextFailure] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const navFocusIndexRef = useRef<number | null>(null);
  const historyDraftRef = useRef("");
  const lastInputSequenceRef = useRef("");
  const promptTextRef = useRef("");
  const promptCursorRef = useRef(0);
  const startupPasteReplayRef = useRef<StartupPasteReplayState>({ pendingSequence: null });
  const startupPasteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const activeRun = displayMode === "review" ? reviewRun : run;
  const activeEvents = displayMode === "review" ? reviewRun?.events ?? [] : events;
  const status = useMemo(
    () => activeEvents.at(-1)?.status ?? activeRun?.status ?? (displayMode === "runs-list" ? "history" : "idle"),
    [activeEvents, activeRun, displayMode]
  );
  const statusMetrics = useMemo(() => buildStatusMetrics(activeEvents, now), [activeEvents, now]);
  const stages = useMemo(() => deriveStageSummaries(activeEvents, activeRun?.expected_stages ?? []), [activeEvents, activeRun]);
  const visibleStages = useMemo(() => sidebarStages(stages), [stages]);
  const effectiveSelectedKey = navMode ? navFocusKey : selectedStage;
  const pinnedStage = useMemo(
    () => stages.find((stage) => stage.key === effectiveSelectedKey) ?? null,
    [effectiveSelectedKey, stages]
  );
  const liveCheckpointWaiting = useMemo(() => resolveCheckpointWaiting(events), [events]);
  const checkpointWaiting = displayMode === "live" ? liveCheckpointWaiting : false;
  const finalContent = useMemo(() => latestFinalContent(activeRun, activeEvents), [activeRun, activeEvents]);
  const finalLines = useMemo(() => renderMarkdownLines(finalContent, outputPanelWidth), [finalContent, outputPanelWidth]);
  const pinnedStageLines = useMemo(
    () => renderMarkdownLines(pinnedStageContent(stages, effectiveSelectedKey), outputPanelWidth),
    [effectiveSelectedKey, outputPanelWidth, stages]
  );
  const liveStageEvent = useMemo(() => latestLiveStageEvent(activeEvents), [activeEvents]);
  const liveLines = useMemo(
    () => renderMarkdownLines(liveStageEvent?.content ?? "", outputPanelWidth),
    [liveStageEvent, outputPanelWidth]
  );
  const eventLines = useMemo(
    () => buildEventLines(activeEvents, error, outputPanelWidth, notice),
    [activeEvents, error, notice, outputPanelWidth]
  );
  const outputLines = finalLines.length > 0 ? finalLines : liveLines;
  const livePanelLines = resolvePanelLines({
    showEvents,
    selectedStage: effectiveSelectedKey,
    pinnedStageLines,
    outputLines,
    eventLines
  });
  const runListLines = useMemo(
    () => buildRunListLines(runHistory, selectedRunIndex, outputPanelWidth, runHistoryLoading, runHistoryFailure),
    [outputPanelWidth, runHistory, runHistoryFailure, runHistoryLoading, selectedRunIndex]
  );
  const contextLines = useMemo(
    () => contextLoading
      ? ["Loading session context..."]
      : contextFailure
      ? wrapPlainText(`Could not load session context: ${contextFailure}`, outputPanelWidth)
      : sessionContext
      ? buildSessionContextPreviewLines(sessionContext, { width: outputPanelWidth, maxRecallResults: 3 })
      : livePanelLines,
    [contextFailure, contextLoading, livePanelLines, outputPanelWidth, sessionContext]
  );
  const contextPanelActive = sessionContext !== null || contextLoading || Boolean(contextFailure);
  const panelLines = displayMode === "runs-list" ? runListLines : contextPanelActive ? contextLines : livePanelLines;
  const contentH = resolvePanelContentHeight(transcriptHeight);
  const maxScroll = Math.max(0, panelLines.length - contentH);
  const canScrollPanel = panelLines.length > contentH;
  const isLiveOutput = displayMode === "live" && !navMode && selectedStage === null && finalLines.length === 0 && liveLines.length > 0;
  const ghostSuffix = useMemo(
    () => promptCursor === prompt.length ? resolveGhostSuffix(prompt, commandHistory, promptEditorWidth) : "",
    [commandHistory, prompt, promptCursor, promptEditorWidth]
  );
  const visiblePromptLines = checkpointWaiting ? 2 : promptVisibleLineCount;
  const promptView = useMemo(
    () => buildPromptView(prompt, promptCursor, promptEditorWidth, visiblePromptLines, ghostSuffix),
    [ghostSuffix, prompt, promptCursor, promptEditorWidth, visiblePromptLines]
  );
  const isLiveRunInFlight = useMemo(() => {
    if (!run) return false;
    if (events.some(isTerminalEvent)) return false;
    return run.status !== "completed" && run.status !== "failed";
  }, [events, run]);

  React.useEffect(() => {
    runtime
      .getTheme()
      .then((theme) => {
        const palette = resolveThemePalette(theme);
        setTerminalTheme(gemTerminalThemeFromPalette(palette));
      })
      .catch(() => undefined);
  }, []);

  React.useEffect(() => {
    runtime
      .listSessions()
      .then(applySessionState)
      .catch((reason: unknown) => setError(formatRuntimeError(reason)));
  }, []);

  React.useEffect(() => {
    const latest = events.at(-1);
    if (!run || (latest && isTerminalEvent(latest))) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [run, events]);

  React.useEffect(() => {
    const rememberInputSequence = (data: Buffer | string) => {
      const sequence = Buffer.isBuffer(data) ? data.toString("utf8") : String(data);
      lastInputSequenceRef.current = sequence;
      if (!shouldBufferStartupPaste(sequence)) return;
      startupPasteReplayRef.current = bufferStartupPaste(startupPasteReplayRef.current, sequence);
      if (startupPasteTimerRef.current) {
        clearTimeout(startupPasteTimerRef.current);
      }
      startupPasteTimerRef.current = setTimeout(() => {
        startupPasteTimerRef.current = null;
        const pending = startupPasteReplayRef.current.pendingSequence;
        if (!pending) return;
        startupPasteReplayRef.current = { pendingSequence: null };
        setPromptBuffer(insertPromptText(
          { text: promptTextRef.current, cursor: promptCursorRef.current },
          pending
        ));
      }, 0);
    };
    inputEvents.on("input", rememberInputSequence);
    return () => {
      inputEvents.off("input", rememberInputSequence);
      if (startupPasteTimerRef.current) {
        clearTimeout(startupPasteTimerRef.current);
        startupPasteTimerRef.current = null;
      }
    };
  }, [inputEvents]);

  React.useEffect(() => {
    setScrollTop((current) => clampScrollTop(current, panelLines.length, contentH));
  }, [panelLines.length, contentH]);

  React.useEffect(() => {
    if (selectedStage !== null && !stages.some((stage) => stage.key === selectedStage)) {
      setSelectedStage(null);
    }
  }, [selectedStage, stages]);

  React.useEffect(() => {
    setScrollTop(0);
  }, [selectedStage]);

  React.useEffect(() => {
    if (!navMode) return;
    const currentIndex = visibleStages.findIndex((stage) => stage.key === navFocusKey);
    if (currentIndex >= 0) {
      navFocusIndexRef.current = currentIndex;
      return;
    }
    if (visibleStages.length === 0) {
      setNavMode(false);
      setNavFocusKey(null);
      navFocusIndexRef.current = null;
      return;
    }
    setNavFocusKey(resolveNavCursorAfterPrune(visibleStages, navFocusIndexRef.current));
  }, [navFocusKey, navMode, visibleStages]);

  React.useEffect(() => {
    setScrollTop(0);
  }, [navMode, navFocusKey]);

  useInput((input, key) => {
    startupPasteReplayRef.current = markStartupPasteHandled(
      startupPasteReplayRef.current,
      lastInputSequenceRef.current
    );

    if (navMode) {
      if (key.upArrow || input === "k") {
        setNavFocusKey((current) => resolveNavCursorMove(visibleStages, current, "previous"));
        setScrollTop(0);
        return;
      }
      if (key.downArrow || input === "j") {
        setNavFocusKey((current) => resolveNavCursorMove(visibleStages, current, "next"));
        setScrollTop(0);
        return;
      }
      if (key.pageUp && canScrollPanel) {
        setScrollTop((prev) => Math.max(0, prev - Math.max(1, contentH - 1)));
        return;
      }
      if (key.pageDown && canScrollPanel) {
        setScrollTop((prev) => Math.min(maxScroll, prev + Math.max(1, contentH - 1)));
        return;
      }
      if (key.tab || key.escape) {
        exitNavMode();
        return;
      }
      if (input === "l" && !prompt.trim()) {
        releaseStagePin();
        exitNavMode();
        return;
      }
      if (key.return && !prompt.trim()) {
        pinNavFocus();
        return;
      }
    }

    if (displayMode === "runs-list") {
      if (key.upArrow || input === "k") {
        setSelectedRunIndex((current) => resolveRunsListIndex(current, runHistory.length, "previous"));
        return;
      }
      if (key.downArrow || input === "j") {
        setSelectedRunIndex((current) => resolveRunsListIndex(current, runHistory.length, "next"));
        return;
      }
      if (key.return) {
        void openSelectedRunReview();
        return;
      }
      if (key.tab || key.escape) {
        enterLiveMode("history closed");
        return;
      }
      if (key.pageUp && canScrollPanel) {
        setScrollTop((prev) => Math.max(0, prev - Math.max(1, contentH - 1)));
        return;
      }
      if (key.pageDown && canScrollPanel) {
        setScrollTop((prev) => Math.min(maxScroll, prev + Math.max(1, contentH - 1)));
        return;
      }
      return;
    }

    if (displayMode === "review") {
      if (key.tab || key.escape) {
        enterLiveMode("returned to live run");
        return;
      }
      if (canScrollPanel) {
        if (key.upArrow) { setScrollTop((prev) => Math.max(0, prev - 1)); return; }
        if (key.downArrow) { setScrollTop((prev) => Math.min(maxScroll, prev + 1)); return; }
        if (key.pageUp) { setScrollTop((prev) => Math.max(0, prev - Math.max(1, contentH - 1))); return; }
        if (key.pageDown) { setScrollTop((prev) => Math.min(maxScroll, prev + Math.max(1, contentH - 1))); return; }
      }
    }

    if (displayMode === "live" && contextPanelActive && (key.tab || key.escape)) {
      enterLiveMode("context closed");
      return;
    }

    if (promptView.totalLines > 1 && (key.upArrow || key.downArrow)) {
      setPromptBuffer(movePromptCursorVertical(
        { text: prompt, cursor: promptCursor },
        promptEditorWidth,
        key.upArrow ? "previous" : "next"
      ));
      return;
    }

    // Scroll the bounded transcript pane whenever visible content exceeds it.
    if (displayMode === "live" && canScrollPanel) {
      if (key.upArrow) { setScrollTop((prev) => Math.max(0, prev - 1)); return; }
      if (key.downArrow) { setScrollTop((prev) => Math.min(maxScroll, prev + 1)); return; }
      if (key.pageUp) { setScrollTop((prev) => Math.max(0, prev - Math.max(1, contentH - 1))); return; }
      if (key.pageDown) { setScrollTop((prev) => Math.min(maxScroll, prev + Math.max(1, contentH - 1))); return; }
    }

    if (key.ctrl && input === "p") {
      const next = resolveCommandHistoryMove(commandHistory, historyCursor, historyDraftRef.current, prompt, "previous");
      historyDraftRef.current = next.draft;
      setHistoryCursor(next.cursor);
      setPromptBuffer({ text: next.prompt, cursor: next.prompt.length });
      return;
    }

    if (key.ctrl && input === "n") {
      const next = resolveCommandHistoryMove(commandHistory, historyCursor, historyDraftRef.current, prompt, "next");
      historyDraftRef.current = next.draft;
      setHistoryCursor(next.cursor);
      setPromptBuffer({ text: next.prompt, cursor: next.prompt.length });
      return;
    }

    if (key.rightArrow && ghostSuffix) {
      setPromptBuffer(insertPromptText({ text: prompt, cursor: promptCursor }, ghostSuffix));
      setHistoryCursor(null);
      historyDraftRef.current = "";
      return;
    }

    if (key.leftArrow) {
      setPromptBuffer(movePromptCursorHorizontal({ text: prompt, cursor: promptCursor }, "previous"));
      return;
    }

    if (key.rightArrow) {
      setPromptBuffer(movePromptCursorHorizontal({ text: prompt, cursor: promptCursor }, "next"));
      return;
    }

    if (displayMode === "live" && key.tab && selectedStage !== null) {
      setSelectedStage(null);
      setShowEvents(false);
      setNotice("stage view released");
      setScrollTop(0);
      return;
    }

    if (displayMode === "live" && key.tab && (outputLines.length > 0 || eventLines.length > 0)) {
      setShowEvents((prev) => !prev);
      setScrollTop(0);
      return;
    }

    if (!key.ctrl && input.length > 1 && /[\r\n]/.test(input)) {
      setHistoryCursor(null);
      historyDraftRef.current = "";
      setPromptBuffer(insertPromptText(
        { text: prompt, cursor: promptCursor },
        resolvePromptPasteInput(input, lastInputSequenceRef.current)
      ));
      return;
    }

    if (key.return && prompt.trim()) {
      const command = prompt.trim();
      setCommandHistory((current) => current.at(-1) === command ? current : [...current, command].slice(-100));
      setHistoryCursor(null);
      historyDraftRef.current = "";
      if (checkpointWaiting && command.startsWith("/")) {
        void handleCheckpointCommand(command);
      } else if (displayMode === "review" && isCheckpointCommand(command)) {
        setNotice("Checkpoint commands are unavailable while reviewing history.");
      } else if (command === "/runs") {
        void handleRunsCommand();
      } else if (command === "/context" || command.startsWith("/context ")) {
        void handleContextCommand(command);
      } else if (command === "/prev" || command.startsWith("/prev ")) {
        void handlePrevCommand(command);
      } else if (command === "/nav" || command.startsWith("/nav ")) {
        handleNavCommand(command);
      } else if (command === "/stage" || command.startsWith("/stage ")) {
        handleStageCommand(command);
      } else if (command === "/sessions" || command.startsWith("/session ")) {
        void handleSessionCommand(command);
      } else {
        void startRun(command);
      }
      setPromptBuffer({ text: "", cursor: 0 });
      return;
    }
    if (key.return) {
      return;
    }
    const deleteDirection = resolvePromptDeleteDirection(key, lastInputSequenceRef.current);
    if (deleteDirection !== null) {
      setHistoryCursor(null);
      historyDraftRef.current = "";
      setPromptBuffer(
        deleteDirection === "backward"
          ? deletePromptBackward({ text: prompt, cursor: promptCursor })
          : deletePromptForward({ text: prompt, cursor: promptCursor })
      );
      return;
    }
    if (!key.ctrl && input) {
      const normalized = normalizePromptInput(input);
      if (!normalized) return;
      setHistoryCursor(null);
      historyDraftRef.current = "";
      setPromptBuffer(insertPromptText({ text: prompt, cursor: promptCursor }, normalized));
    }
  }, { isActive: inputActive });

  function setPromptBuffer(next: PromptBufferState) {
    promptTextRef.current = next.text;
    promptCursorRef.current = next.cursor;
    setPrompt(next.text);
    setPromptCursor(next.cursor);
  }

  function applySessionState(state: UiSessionState) {
    setSession(state.current_session);
    setSessions(state.sessions.length > 0 ? state.sessions : [state.current_session]);
  }

  async function startRun(message: string) {
    try {
      setError("");
      setNotice("");
      setSessionContext(null);
      setContextFailure("");
      setContextLoading(false);
      setDisplayMode("live");
      setReviewRun(null);
      setRunHistoryFailure("");
      setEvents([]);
      setScrollTop(0);
      setShowEvents(false);
      setSelectedStage(null);
      setNavMode(false);
      setNavFocusKey(null);
      navFocusIndexRef.current = null;
      const started = await runtime.startRun({ message, mode: "auto", session });
      setRun(started);
      setEvents(started.events);
      const source = runtime.subscribe(
        started.run_id,
        (event) => {
          setEvents((current) => dedupeEvents([...current, event]));
          if (isTerminalEvent(event)) {
            source.close();
            runtime
              .getRun(started.run_id)
              .then((state) => {
                setRun(state);
                return runtime.getSession(state.session).then(applySessionState);
              })
              .catch((reason: unknown) => setError(String(reason)));
          }
        },
        () => setError("Runtime event stream disconnected.")
      );
    } catch (reason) {
      setError(formatRuntimeError(reason));
    }
  }

  async function handleRunsCommand() {
    setError("");
    setNotice("");
    setSessionContext(null);
    setContextFailure("");
    setContextLoading(false);
    setDisplayMode("runs-list");
    setReviewRun(null);
    setRunHistoryLoading(true);
    setRunHistoryFailure("");
    setSelectedRunIndex(0);
    resetStageNavigation();
    setSelectedStage(null);
    setShowEvents(false);
    setScrollTop(0);
    try {
      const history = await runtime.listSessionRuns(session, 12);
      const terminalRuns = history.runs.filter((item) => item.status === "completed" || item.status === "failed");
      setRunHistory(terminalRuns.slice(0, 12));
      setSelectedRunIndex(0);
      setNotice(terminalRuns.length > 0 ? `history: ${terminalRuns.length} runs` : "No previous completed or failed runs.");
    } catch {
      setRunHistory([]);
      setRunHistoryFailure("Could not load runs.");
      setNotice("Could not load runs.");
    } finally {
      setRunHistoryLoading(false);
    }
  }

  async function handlePrevCommand(command: string) {
    setError("");
    setNotice("");
    if (isLiveRunInFlight) {
      setNotice("Previous-run review is available after the active run finishes.");
      return;
    }
    const rawOffset = command.replace(/^\/prev\s*/, "").trim();
    const offset = rawOffset ? Number(rawOffset) : 1;
    if (!Number.isInteger(offset) || offset < 1) {
      setNotice("Usage: /prev or /prev <number>.");
      return;
    }
    try {
      const history = await runtime.listSessionRuns(session, Math.max(12, offset));
      const target = history.runs.filter((item) => item.status === "completed" || item.status === "failed")[offset - 1];
      if (!target) {
        setNotice(`No previous run at ${offset}.`);
        return;
      }
      await openRunReview(target);
    } catch {
      setNotice("Could not load runs.");
    }
  }

  async function handleContextCommand(command: string) {
    setError("");
    setNotice("");
    const parsed = parseContextCommand(command);
    if (!parsed.ok) {
      setNotice(parsed.message);
      return;
    }
    const query = parsed.query;
    setContextLoading(true);
    setContextFailure("");
    setSessionContext(null);
    setShowEvents(false);
    setSelectedStage(null);
    resetStageNavigation();
    setScrollTop(0);
    try {
      const context = await runtime.getSessionContext(session, query || undefined, 5);
      setSessionContext(context);
      setNotice(query ? `context: ${query}` : "context shown");
    } catch (reason) {
      setContextFailure(formatRuntimeError(reason));
    } finally {
      setContextLoading(false);
    }
  }

  async function openSelectedRunReview() {
    const selected = runHistory[selectedRunIndex];
    if (!selected || runHistoryLoading || runHistoryFailure) return;
    await openRunReview(selected);
  }

  async function openRunReview(summary: UiRunSummary) {
    try {
      setError("");
      setNotice("Loading run...");
      const detail = await runtime.getSessionRun(summary.session, summary.run_id);
      clearContextPreview();
      setReviewRun(detail);
      setDisplayMode("review");
      setRunHistoryFailure("");
      resetStageNavigation();
      setSelectedStage(null);
      setShowEvents(false);
      setScrollTop(0);
      setNotice(`reviewing: ${runSummaryTitle(summary)}`);
    } catch {
      setNotice("Could not load run.");
    }
  }

  async function handleSessionCommand(command: string) {
    try {
      setError("");
      setNotice("");
      clearContextPreview();
      if (command === "/sessions") {
        const state = await runtime.listSessions();
        applySessionState(state);
        setNotice(`sessions: ${state.sessions.join(", ")}`);
        return;
      }
      const requested = command.replace(/^\/session\s+/, "").trim();
      if (!requested) { setError("Usage: /session <name>."); return; }
      const state = await runtime.createSession(requested);
      applySessionState(state);
    } catch (reason) {
      setError(formatRuntimeError(reason));
    }
  }

  function handleStageCommand(command: string) {
    setError("");
    setNotice("");
    clearContextPreview();
    const requested = command.replace(/^\/stage\s*/, "").trim();
    if (!requested || requested === "live" || requested === "release") {
      releaseStagePin();
      return;
    }

    const result = findStagePinTarget(stages, requested);
    if (!result.ok) {
      setError(result.message);
      return;
    }

    setSelectedStage(result.stage.key);
    setNavMode(false);
    setNavFocusKey(null);
    setShowEvents(false);
    setScrollTop(0);
    setNotice(`pinned: ${result.stage.label}`);
  }

  function handleNavCommand(command: string) {
    setError("");
    setNotice("");
    clearContextPreview();
    const requested = command.replace(/^\/nav\s*/, "").trim();
    if (requested) {
      setError("Usage: /nav.");
      return;
    }
    if (navMode) {
      exitNavMode();
      return;
    }
    if (visibleStages.length === 0) {
      setError("No stages to navigate.");
      return;
    }
    const currentVisiblePin = selectedStage !== null && visibleStages.some((stage) => stage.key === selectedStage)
      ? selectedStage
      : null;
    const nextFocus = currentVisiblePin ?? visibleStages.at(-1)?.key ?? null;
    setNavFocusKey(nextFocus);
    navFocusIndexRef.current = visibleStages.findIndex((stage) => stage.key === nextFocus);
    setNavMode(true);
    setShowEvents(false);
    setScrollTop(0);
  }

  function releaseStagePin() {
    setSelectedStage(null);
    resetStageNavigation();
    setShowEvents(false);
    setScrollTop(0);
    setNotice("stage view released");
  }

  function exitNavMode() {
    resetStageNavigation();
    setShowEvents(false);
    setScrollTop(0);
  }

  function pinNavFocus() {
    if (navFocusKey === null) return;
    const stage = stages.find((item) => item.key === navFocusKey);
    if (!stage) return;
    setSelectedStage(stage.key);
    setNavMode(false);
    setNavFocusKey(null);
    navFocusIndexRef.current = null;
    setShowEvents(false);
    setScrollTop(0);
    setNotice(`pinned: ${stage.label}`);
  }

  function enterLiveMode(message = "") {
    setDisplayMode("live");
    setReviewRun(null);
    clearContextPreview();
    setRunHistoryFailure("");
    resetStageNavigation();
    setSelectedStage(null);
    setShowEvents(false);
    setScrollTop(0);
    setNotice(message);
  }

  function resetStageNavigation() {
    setNavMode(false);
    setNavFocusKey(null);
    navFocusIndexRef.current = null;
  }

  function clearContextPreview() {
    setSessionContext(null);
    setContextFailure("");
    setContextLoading(false);
  }

  async function handleCheckpointCommand(command: string) {
    try {
      setError("");
      setNotice("");
      if (!run) return;
      if (command === "/continue") {
        await runtime.submitCheckpoint(run.run_id, { action: "continue" });
        injectCheckpointDecision("continue");
      } else if (command === "/stop") {
        await runtime.submitCheckpoint(run.run_id, { action: "stop" });
        injectCheckpointDecision("stop");
      } else if (command.startsWith("/redirect ")) {
        const redirectInstruction = command.replace(/^\/redirect\s+/, "");
        await runtime.submitCheckpoint(run.run_id, {
          action: "redirect",
          redirect_instruction: redirectInstruction
        });
        injectCheckpointDecision("redirect", redirectInstruction);
      } else {
        setError("Checkpoint commands: /continue, /stop, or /redirect <guidance>.");
        return;
      }
    } catch (reason) {
      setError(formatRuntimeError(reason));
    }
  }

  function injectCheckpointDecision(action: "continue" | "stop" | "redirect", redirectInstruction = "") {
    if (!run) return;
    setEvents((current) => dedupeEvents([
      ...current,
      {
        schema_version: "ui_event_v1",
        event_type: "checkpoint_decision",
        run_id: run.run_id,
        timestamp: new Date().toISOString(),
        session: run.session,
        status: current.at(-1)?.status ?? "running",
        title: "Decision submitted",
        summary: `Checkpoint decision: ${action}.`,
        content: redirectInstruction,
        verbose_content: "",
        mode: null,
        agent_id: "retrieval_checkpoint",
        stage: "retrieval_checkpoint",
        metadata: { action, redirect_instruction: redirectInstruction }
      }
    ]));
  }

  return (
    <Box flexDirection="column" width={viewportWidth} height={viewportHeight}>
      <Box height={3} borderStyle="single" borderColor={terminalTheme.accent} paddingX={1}>
        <Text bold>crisAI Gem</Text>
        <Text> | {status}</Text>
        <Text> | {session}</Text>
        {displayMode === "runs-list" ? <Text color={terminalTheme.border}> | history</Text> : null}
        {displayMode === "review" && reviewRun ? (
          <Text color={terminalTheme.border} wrap="truncate-end">
            {` | reviewing: ${truncateStageLabel(reviewTitle(reviewRun), 24)}`}
          </Text>
        ) : null}
        {displayMode === "live" && contextPanelActive ? <Text color={terminalTheme.border}> | context</Text> : null}
        {checkpointWaiting ? <Text color={terminalTheme.checkpoint.label}> | decision needed</Text> : null}
        {navMode && pinnedStage ? (
          <Text color={terminalTheme.border} wrap="truncate-end">
            {` | nav: ${truncateStageLabel(pinnedStage.label, 16)}`}
          </Text>
        ) : pinnedStage ? (
          <Text color={terminalTheme.border} wrap="truncate-end">
            {` | pinned: ${truncateStageLabel(pinnedStage.label, 16)}`}
          </Text>
        ) : isLiveOutput ? <Text color={terminalTheme.stage.running}> | streaming</Text> : null}
        <Text dimColor wrap="truncate-end">
          {displayMode === "runs-list" || displayMode === "review"
            ? " | Tab/Esc: live"
            : showEvents ? " | tab: output" : " | tab: events"}
        </Text>
      </Box>

      <Box height={transcriptHeight + 2} flexDirection="row">
        <Box width={stageSidebarWidth} borderStyle="single" borderColor={terminalTheme.border} paddingX={1} flexDirection="column">
          <Text bold>{displayMode === "review" ? "Review stages" : "Stages"}</Text>
          {stages.length === 0 ? <Text dimColor>No stages yet.</Text> : null}
          {visibleStages.map((stage, index) => (
            <StageItem
              key={`${stage.key}-${index}`}
              stage={stage}
              sidebarWidth={stageSidebarWidth}
              theme={terminalTheme}
              selected={stage.key === effectiveSelectedKey}
            />
          ))}
        </Box>

        <Box flexGrow={1} borderStyle="single" borderColor={terminalTheme.outputBorder} paddingX={1} flexDirection="column">
          <ScrollPane lines={panelLines} height={transcriptHeight} scrollTop={scrollTop} />
        </Box>
      </Box>

      <Box
        height={promptPanelHeight}
        borderStyle="single"
        borderColor={checkpointWaiting ? terminalTheme.checkpoint.border : terminalTheme.accent}
        paddingX={1}
        flexDirection="column"
      >
        {checkpointWaiting ? (
          <>
            {checkpointDecisionLines().map((line, index) => (
              <Text
                key={`checkpoint-decision-${index}`}
                bold={index === 0}
                color={terminalTheme.checkpoint.label}
                wrap="truncate-end"
              >
                {line}
              </Text>
            ))}
          </>
        ) : (
          <Text dimColor>
            {displayMode === "runs-list" ? "History" : displayMode === "review" ? "Review" : "Prompt"}
            {promptView.totalLines > visiblePromptLines
              ? ` · lines ${promptView.cursorLine + 1}/${promptView.totalLines}`
              : ""}
          </Text>
        )}
        {promptView.lines.map((line, index) => (
          <Text key={`prompt-line-${index}`} wrap="truncate-end">
            {index === 0 ? "> " : "  "}
            {index === 0 && promptView.hiddenBefore > 0 ? <Text dimColor>↑ </Text> : null}
            {line.beforeCursor}
            {line.cursorText ? <Text inverse>{line.cursorText}</Text> : null}
            {line.afterCursor}
            {line.ghostSuffix ? <Text dimColor>{line.ghostSuffix}</Text> : null}
            {index === promptView.lines.length - 1 && promptView.hiddenAfter > 0 ? <Text dimColor> ↓</Text> : null}
          </Text>
        ))}
      </Box>

      <Box paddingX={1} backgroundColor="white">
        <Text color="black" wrap="truncate-end">
          {`${statusMetrics.model} | ${statusMetrics.elapsed} | tokens:${statusMetrics.tokens} | cost:${statusMetrics.cost} | `}
          {displayMode === "runs-list"
            ? "↑↓/j/k select · Enter review · Tab/Esc live"
            : displayMode === "review" && reviewRun
            ? `${canScrollPanel ? "↑↓/PgUp/PgDn scroll · " : ""}reviewing: ${reviewTitle(reviewRun)} · /stage and /nav use historical stages · Tab/Esc live`
            : checkpointWaiting
            ? "decision: /continue use sources | /stop end run | /redirect refine"
            : contextPanelActive
            ? `${canScrollPanel ? "↑↓/PgUp/PgDn scroll · " : ""}/context show <query> refresh · Enter prompt returns to live output`
            : navMode
              ? "↑↓ stages · Enter pin · l release · Tab/Esc exit · PgUp/PgDn scroll content"
            : pinnedStage
              ? canScrollPanel
                ? `↑↓/PgUp/PgDn scroll · /stage release · Tab unpin · pinned: ${pinnedStage.label}`
                : `/stage release · Tab unpin · pinned: ${pinnedStage.label}`
              : prompt
                ? `prompt: ←→ cursor · ↑↓ lines · Ctrl+P/Ctrl+N history · Enter submit`
              : canScrollPanel
                ? `↑↓/PgUp/PgDn scroll · tab: ${showEvents ? "output" : "events"} · /session <name>`
                : `mode:auto | session:${session} | sessions:${sessions.length} | Ctrl+P/Ctrl+N history | /context show | /session <name>${!run ? " · [/runs for history]" : ""}${stages.length > 0 ? " · /stage <key>" : ""}${stages.length > 1 ? " · /nav browse" : ""}`}
        </Text>
      </Box>
    </Box>
  );
}

function latestLiveStageEvent(events: UiEvent[]): UiEvent | null {
  const terminal = [...events].reverse().find((event) => isTerminalEvent(event));
  if (terminal) return null;
  return [...events].reverse().find((event) => event.event_type === "stage_delta") ?? null;
}

function isCheckpointCommand(command: string): boolean {
  return command === "/continue" || command === "/stop" || command === "/redirect" || command.startsWith("/redirect ");
}

function reviewTitle(run: UiRunDetail): string {
  const messageSummary = typeof run.metadata.message_summary === "string" ? run.metadata.message_summary.trim() : "";
  if (messageSummary) return messageSummary;
  const finalSummary = run.final_output.trim().split("\n")[0] ?? "";
  return finalSummary || run.run_id;
}

function formatRuntimeError(reason: unknown): string {
  const message = reason instanceof Error ? reason.message : String(reason);
  if (message.toLowerCase().includes("fetch failed")) {
    return `Cannot reach crisAI API at ${runtimeBaseUrl}. Start it in another terminal with './start api' or set CRISAI_RUNTIME_URL.`;
  }
  return message;
}

type StatusMetrics = {
  model: string;
  elapsed: string;
  tokens: string;
  cost: string;
};

function buildStatusMetrics(events: UiEvent[], nowMs: number): StatusMetrics {
  const startedAt = parseTimestamp(events.find((event) => event.event_type === "run_created")?.timestamp);
  const terminal = [...events].reverse().find((event) => isTerminalEvent(event));
  const endedAt = parseTimestamp(terminal?.timestamp);
  const elapsedMs = startedAt === null ? 0 : Math.max(0, (endedAt ?? nowMs) - startedAt);
  const metadataItems = events.map((event) => event.metadata);
  const model = firstString(metadataItems, ["model_name", "model_ref", "provider"]) ?? "model:n/a";
  const tokens = firstNumber(metadataItems, ["total_tokens", "tokens", "token_count"]);
  const cost = firstNumber(metadataItems, ["cost_usd", "total_cost_usd", "cost"]);
  return {
    model,
    elapsed: formatElapsed(elapsedMs),
    tokens: tokens === null ? "n/a" : String(Math.round(tokens)),
    cost: cost === null ? "n/a" : `$${cost.toFixed(4)}`,
  };
}

function parseTimestamp(value: string | undefined): number | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatElapsed(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}:${remaining.toString().padStart(2, "0")}`;
}

function firstString(items: Record<string, unknown>[], keys: string[]): string | null {
  for (const item of items) {
    for (const key of keys) {
      const value = item[key];
      if (typeof value === "string" && value.trim()) return value;
    }
  }
  return null;
}

function firstNumber(items: Record<string, unknown>[], keys: string[]): number | null {
  for (const item of items) {
    for (const key of keys) {
      const value = item[key];
      if (typeof value === "number" && Number.isFinite(value)) return value;
      if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
    }
  }
  return null;
}

function dedupeEvents(items: UiEvent[]): UiEvent[] {
  const seen = new Set<string>();
  return items.filter((event) => {
    const key = `${event.event_type}-${event.timestamp}-${event.agent_id ?? ""}-${event.stage ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

render(<GemApp />);
