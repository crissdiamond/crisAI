import {
  isCheckpointWaiting,
  isTerminalEvent,
  type UiEvent,
  type UiRunSummary,
  type UiSessionContext,
  type UiStageStatus,
  type UiStageSummary
} from "@crisai/contracts";

export const fallbackGemWidth = 132;
export const fallbackGemHeight = 40;
export const minimumGemWidth = 80;
export const minimumGemHeight = 24;
export const minimumStageSidebarWidth = 20;
export const maximumStageSidebarWidth = 34;
export const promptPanelHeight = 7;
export const promptVisibleLineCount = 4;

export type InkColorName =
  | "black"
  | "blue"
  | "cyan"
  | "green"
  | "magenta"
  | "red"
  | "white"
  | "yellow";

export type GemTerminalTheme = {
  accent: InkColorName;
  border: InkColorName;
  outputBorder: InkColorName;
  stage: Record<UiStageStatus, InkColorName | undefined>;
  checkpoint: {
    border: InkColorName;
    label: InkColorName;
  };
  error: InkColorName;
};

export type StagePinResult =
  | {
      ok: true;
      stage: UiStageSummary;
    }
  | {
      ok: false;
      message: string;
    };

export type PanelLinesInput = {
  showEvents: boolean;
  selectedStage: string | null;
  pinnedStageLines: string[];
  outputLines: string[];
  eventLines: string[];
};

export type NavDirection = "previous" | "next";
export type DisplayMode = "live" | "runs-list" | "review";
export type CommandHistoryDirection = "previous" | "next";

export type CommandHistoryResult = {
  prompt: string;
  cursor: number | null;
  draft: string;
};

export type PromptBufferState = {
  text: string;
  cursor: number;
};

export type PromptVisualLine = {
  text: string;
  start: number;
  end: number;
};

export type PromptRenderLine = {
  beforeCursor: string;
  cursorText: string;
  afterCursor: string;
  ghostSuffix: string;
};

export type PromptView = {
  lines: PromptRenderLine[];
  cursorLine: number;
  totalLines: number;
  hiddenBefore: number;
  hiddenAfter: number;
};

export type PromptDeleteDirection = "backward" | "forward";

export type StartupPasteReplayState = {
  pendingSequence: string | null;
};

export type SessionContextPreviewOptions = {
  width: number;
  maxRecallResults?: number;
};

export type ContextCommandParseResult =
  | {
      ok: true;
      query: string;
    }
  | {
      ok: false;
      message: string;
    };

export const contextReviewUnavailableNotice = "/context show is unavailable while reviewing history.";

export const defaultGemTerminalTheme: GemTerminalTheme = {
  accent: "magenta",
  border: "blue",
  outputBorder: "white",
  stage: {
    pending: undefined,
    running: "cyan",
    complete: "green",
    skipped: "yellow",
    failed: "red"
  },
  checkpoint: {
    border: "yellow",
    label: "yellow"
  },
  error: "red"
};

export function gemTerminalThemeFromPalette(palette: Record<string, string>): GemTerminalTheme {
  return {
    accent: colorNameForToken(palette.accent_bright, defaultGemTerminalTheme.accent),
    border: colorNameForToken(palette.accent_blue, defaultGemTerminalTheme.border),
    outputBorder: colorNameForToken(palette.transcript_background, defaultGemTerminalTheme.outputBorder),
    stage: {
      pending: undefined,
      running: colorNameForToken(palette.accent_blue, defaultGemTerminalTheme.stage.running),
      complete: colorNameForToken(palette.success, defaultGemTerminalTheme.stage.complete),
      skipped: colorNameForToken(palette.warning, defaultGemTerminalTheme.stage.skipped),
      failed: colorNameForToken(palette.error, defaultGemTerminalTheme.stage.failed)
    },
    checkpoint: {
      border: colorNameForToken(palette.warning, defaultGemTerminalTheme.checkpoint.border),
      label: colorNameForToken(palette.warning, defaultGemTerminalTheme.checkpoint.label)
    },
    error: colorNameForToken(palette.error, defaultGemTerminalTheme.error)
  };
}

export function resolveViewportDimension(
  pinnedValue: string | undefined,
  terminalValue: number | undefined,
  fallbackValue: number,
  minimumValue: number
): number {
  const pinned = Number(pinnedValue);
  const preferred = Number.isFinite(pinned) && pinned > 0 ? pinned : terminalValue ?? fallbackValue;
  return Math.max(minimumValue, Math.floor(preferred));
}

export function resolveStageSidebarWidth(viewportWidth: number): number {
  const proportionalWidth = Math.floor(viewportWidth * 0.24);
  return Math.min(maximumStageSidebarWidth, Math.max(minimumStageSidebarWidth, proportionalWidth));
}

export function resolveTranscriptHeight(viewportHeight: number): number {
  return Math.max(8, viewportHeight - 6 - promptPanelHeight);
}

export function resolvePanelContentHeight(transcriptHeight: number): number {
  return Math.max(1, transcriptHeight - 1);
}

export function resolveInputActive(isRawModeSupported: boolean | undefined): boolean {
  return isRawModeSupported === true;
}

export function resolveCheckpointWaiting(events: UiEvent[]): boolean {
  return isCheckpointWaiting(events) && !events.some(isTerminalEvent);
}

export function resolveOutputPanelWidth(viewportWidth: number, stageSidebarWidth: number): number {
  return Math.max(24, viewportWidth - stageSidebarWidth - 8);
}

export function clampScrollTop(scrollTop: number, lineCount: number, contentHeight: number): number {
  return Math.max(0, Math.min(scrollTop, Math.max(0, lineCount - contentHeight)));
}

export function truncateStageLabel(label: string, sidebarWidth: number): string {
  const maxLabelLength = Math.max(6, sidebarWidth - 9);
  if (label.length <= maxLabelLength) return label;
  return `${label.slice(0, Math.max(1, maxLabelLength - 1))}…`;
}

export function sidebarStages(stages: UiStageSummary[]): UiStageSummary[] {
  const terminalComplete = stages.some((stage) =>
    stage.status === "complete" && (stage.key === "final_output" || stage.event?.event_type === "final_answer")
  );
  return stages
    .filter((stage) => !isCheckpointStage(stage))
    .filter((stage) => !(terminalComplete && stage.status === "pending" && stage.event === undefined))
    .slice(-12);
}

export function resolveRunsListIndex(currentIndex: number, runCount: number, direction: NavDirection): number {
  if (runCount <= 0) return 0;
  if (direction === "previous") return Math.max(0, currentIndex - 1);
  return Math.min(runCount - 1, currentIndex + 1);
}

export function runSummaryTitle(summary: UiRunSummary): string {
  const label = summary.message_summary || summary.final_answer_summary || summary.run_id;
  return label.trim() || summary.run_id;
}

export function buildRunListLines(
  runs: UiRunSummary[],
  selectedIndex: number,
  width: number,
  loading = false,
  failure = ""
): string[] {
  if (loading) return ["Loading runs..."];
  if (failure) return ["Could not load runs."];
  if (runs.length === 0) return ["No previous completed or failed runs."];

  const lines = ["Previous runs"];
  runs.forEach((run, index) => {
    const marker = index === selectedIndex ? ">" : " ";
    const title = runSummaryTitle(run);
    const suffix = [run.status, formatRunSummaryTimestamp(run.completed_at || run.updated_at || run.created_at)]
      .filter(Boolean)
      .join(" · ");
    const prefix = `${marker} ${run.display_order}. `;
    const maxTitle = Math.max(8, width - prefix.length - suffix.length - 3);
    const boundedTitle = title.length > maxTitle ? `${title.slice(0, Math.max(1, maxTitle - 1))}…` : title;
    const line = `${prefix}${boundedTitle}${suffix ? ` (${suffix})` : ""}`;
    lines.push(line.length > width ? `${line.slice(0, Math.max(1, width - 1))}…` : line);
  });
  lines.push("");
  const help = "Enter review · ↑↓/j/k select · Tab/Esc live";
  lines.push(help.length > width ? `${help.slice(0, Math.max(1, width - 1))}…` : help);
  return lines;
}

export function parseContextCommand(command: string): ContextCommandParseResult {
  const requested = command.replace(/^\/context\b\s*/, "").trim();
  if (!requested) {
    return { ok: false, message: "Usage: /context show [query]." };
  }
  if (requested === "show") {
    return { ok: true, query: "" };
  }
  if (requested.startsWith("show ")) {
    return { ok: true, query: requested.slice(5).trim() };
  }
  return { ok: false, message: "Usage: /context show [query]." };
}

export function isContextCommand(command: string): boolean {
  return command === "/context" || command.startsWith("/context ");
}

export function buildSessionContextPreviewLines(
  context: UiSessionContext,
  options: SessionContextPreviewOptions
): string[] {
  const width = Math.max(8, Math.floor(options.width));
  const maxRecallResults = Math.max(0, Math.floor(options.maxRecallResults ?? 3));
  let hasPreviewContent = context.session.trim().length > 0;
  const lines: string[] = [
    ...wrapPlainText(`Context preview: ${context.session}`, width),
    ...wrapPlainText(
      `Budget: ${context.budget.baseline_chars}/${context.budget.baseline_char_limit} chars · recall ${context.budget.recall_count}/${context.budget.recall_limit}${context.budget.truncated ? " · truncated" : ""}`,
      width
    )
  ];

  if (context.baseline_brief.trim()) {
    hasPreviewContent = true;
    lines.push("");
    lines.push("Baseline brief");
    lines.push(...wrapPlainText(context.baseline_brief.trim(), width));
  }

  const memoryLines = sessionMemoryPreviewLines(context.memory);
  if (memoryLines.length > 0) {
    hasPreviewContent = true;
    lines.push("");
    lines.push("Memory fields");
    lines.push(...memoryLines.flatMap((line) => wrapPlainText(line, width)));
  }

  const recallResults = context.recall_results.slice(0, maxRecallResults);
  if (recallResults.length > 0) {
    hasPreviewContent = true;
    lines.push("");
    lines.push(...wrapPlainText(context.recall_query ? `Recall: ${context.recall_query}` : "Recall", width));
    recallResults.forEach((result, index) => {
      const provenance = result.provenance ? ` · ${result.provenance}` : "";
      const score = Number.isFinite(result.score) ? ` · score ${formatRecallScore(result.score)}` : "";
      lines.push(...wrapPlainText(`${index + 1}. ${result.field}${provenance}${score}`, width));
      lines.push(...wrapPlainText(result.content, Math.max(8, width - 3)).map((line) => `   ${line}`));
    });
  }

  return hasPreviewContent ? lines : ["No session context yet."];
}

export function resolveCommandHistoryMove(
  history: string[],
  cursor: number | null,
  draft: string,
  prompt: string,
  direction: CommandHistoryDirection
): CommandHistoryResult {
  if (history.length === 0) {
    return { prompt, cursor, draft };
  }

  const liveDraft = cursor === null ? prompt : draft;
  if (direction === "previous") {
    const nextCursor = cursor === null ? history.length - 1 : Math.max(0, cursor - 1);
    return {
      prompt: history[nextCursor] ?? prompt,
      cursor: nextCursor,
      draft: liveDraft
    };
  }

  if (cursor === null) {
    return { prompt, cursor, draft };
  }

  const nextCursor = cursor + 1;
  if (nextCursor >= history.length) {
    return {
      prompt: liveDraft,
      cursor: null,
      draft: liveDraft
    };
  }

  return {
    prompt: history[nextCursor] ?? prompt,
    cursor: nextCursor,
    draft: liveDraft
  };
}

export function resolveGhostSuffix(prompt: string, history: string[], usableWidth: number): string {
  if (!prompt || !prompt.startsWith("/")) return "";
  const match = [...history]
    .reverse()
    .find((entry) => entry.startsWith("/") && entry.startsWith(prompt) && entry.length > prompt.length);
  if (!match) return "";
  const maxSuffixLength = Math.max(0, Math.floor(usableWidth) - prompt.length);
  return match.slice(prompt.length, prompt.length + maxSuffixLength);
}

export function normalizePromptInput(input: string): string {
  return input
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/\t/g, "  ")
    .replace(/(?:\x1b)?\[(?:200|201)~/g, "")
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, "");
}

export function resolvePromptPasteInput(input: string, rawSequence = ""): string {
  if (rawSequence.includes("\x1b[200~") || input.startsWith("[200~")) {
    return rawSequence || `\x1b${input}`;
  }
  return input;
}

export function shouldBufferStartupPaste(rawSequence: string): boolean {
  return rawSequence.includes("\x1b[200~");
}

export function bufferStartupPaste(
  state: StartupPasteReplayState,
  rawSequence: string
): StartupPasteReplayState {
  return shouldBufferStartupPaste(rawSequence) ? { pendingSequence: rawSequence } : state;
}

export function markStartupPasteHandled(
  state: StartupPasteReplayState,
  rawSequence: string
): StartupPasteReplayState {
  return state.pendingSequence === rawSequence ? { pendingSequence: null } : state;
}

export function consumeStartupPasteReplay(state: StartupPasteReplayState): {
  state: StartupPasteReplayState;
  sequence: string | null;
} {
  return {
    state: { pendingSequence: null },
    sequence: state.pendingSequence
  };
}

export function insertPromptText(state: PromptBufferState, input: string): PromptBufferState {
  const text = normalizePromptInput(input);
  const cursor = clampPromptCursor(state.cursor, state.text);
  const nextText = `${state.text.slice(0, cursor)}${text}${state.text.slice(cursor)}`;
  return {
    text: nextText,
    cursor: cursor + text.length
  };
}

export function deletePromptBackward(state: PromptBufferState): PromptBufferState {
  const cursor = clampPromptCursor(state.cursor, state.text);
  if (cursor <= 0) return { text: state.text, cursor };
  return {
    text: `${state.text.slice(0, cursor - 1)}${state.text.slice(cursor)}`,
    cursor: cursor - 1
  };
}

export function deletePromptForward(state: PromptBufferState): PromptBufferState {
  const cursor = clampPromptCursor(state.cursor, state.text);
  if (cursor >= state.text.length) return { text: state.text, cursor };
  return {
    text: `${state.text.slice(0, cursor)}${state.text.slice(cursor + 1)}`,
    cursor
  };
}

export function resolvePromptDeleteDirection(
  key: { backspace?: boolean; delete?: boolean },
  rawSequence = ""
): PromptDeleteDirection | null {
  if (key.backspace) return "backward";
  if (key.delete && rawSequence === "\x7f") return "backward";
  if (key.delete) return "forward";
  return null;
}

export function movePromptCursorHorizontal(state: PromptBufferState, direction: NavDirection): PromptBufferState {
  const cursor = clampPromptCursor(state.cursor, state.text);
  return {
    text: state.text,
    cursor: direction === "previous" ? Math.max(0, cursor - 1) : Math.min(state.text.length, cursor + 1)
  };
}

export function promptVisualLines(text: string, width: number): PromptVisualLine[] {
  const usableWidth = Math.max(1, Math.floor(width));
  const lines: PromptVisualLine[] = [];
  let offset = 0;
  const logicalLines = text.split("\n");
  logicalLines.forEach((logicalLine, logicalIndex) => {
    if (logicalLine.length === 0) {
      lines.push({ text: "", start: offset, end: offset });
    } else {
      let localStart = 0;
      while (localStart < logicalLine.length) {
        const localEnd = Math.min(logicalLine.length, localStart + usableWidth);
        lines.push({
          text: logicalLine.slice(localStart, localEnd),
          start: offset + localStart,
          end: offset + localEnd
        });
        localStart = localEnd;
      }
    }
    offset += logicalLine.length;
    if (logicalIndex < logicalLines.length - 1) offset += 1;
  });
  return lines.length > 0 ? lines : [{ text: "", start: 0, end: 0 }];
}

export function promptCursorLineIndex(lines: PromptVisualLine[], cursor: number): number {
  const boundedCursor = Math.max(0, cursor);
  const exact = lines.findIndex((line) => boundedCursor >= line.start && boundedCursor <= line.end);
  return exact >= 0 ? exact : Math.max(0, lines.length - 1);
}

export function movePromptCursorVertical(
  state: PromptBufferState,
  width: number,
  direction: NavDirection
): PromptBufferState {
  const cursor = clampPromptCursor(state.cursor, state.text);
  const lines = promptVisualLines(state.text, width);
  const currentIndex = promptCursorLineIndex(lines, cursor);
  const targetIndex = direction === "previous"
    ? Math.max(0, currentIndex - 1)
    : Math.min(lines.length - 1, currentIndex + 1);
  const currentLine = lines[currentIndex] ?? lines[0];
  const targetLine = lines[targetIndex] ?? currentLine;
  const column = Math.max(0, cursor - currentLine.start);
  return {
    text: state.text,
    cursor: Math.min(targetLine.end, targetLine.start + column)
  };
}

export function buildPromptView(
  text: string,
  cursor: number,
  width: number,
  visibleCount = promptVisibleLineCount,
  ghostSuffix = ""
): PromptView {
  const lines = promptVisualLines(text, width);
  const boundedCursor = clampPromptCursor(cursor, text);
  const cursorLine = promptCursorLineIndex(lines, boundedCursor);
  const visibleLines = Math.max(1, Math.floor(visibleCount));
  const viewportStart = Math.min(
    Math.max(0, cursorLine - visibleLines + 1),
    Math.max(0, lines.length - visibleLines)
  );
  const visible = lines.slice(viewportStart, viewportStart + visibleLines);
  return {
    lines: visible.map((line, index) => promptRenderLine(
      line,
      boundedCursor,
      ghostSuffix,
      viewportStart + index === cursorLine
    )),
    cursorLine,
    totalLines: lines.length,
    hiddenBefore: viewportStart,
    hiddenAfter: Math.max(0, lines.length - viewportStart - visible.length)
  };
}

export function clampPromptCursor(cursor: number, text: string): number {
  return Math.min(Math.max(0, Math.floor(cursor)), text.length);
}

export function formatRunSummaryTimestamp(value: string): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const month = parsed.toLocaleString("en", { month: "short", timeZone: "UTC" });
  const day = parsed.getUTCDate();
  const hours = parsed.getUTCHours().toString().padStart(2, "0");
  const minutes = parsed.getUTCMinutes().toString().padStart(2, "0");
  return `${month} ${day} ${hours}:${minutes}`;
}

export function findStagePinTarget(stages: UiStageSummary[], input: string): StagePinResult {
  const trimmed = input.trim();
  if (!trimmed) {
    return { ok: false, message: "No stage specified." };
  }

  const position = Number(trimmed);
  if (/^\d+$/.test(trimmed)) {
    if (!Number.isInteger(position) || position < 1 || position > 9) {
      return { ok: false, message: `No stage at position ${trimmed}.` };
    }
    const stage = sidebarStages(stages)[position - 1];
    return stage ? { ok: true, stage } : { ok: false, message: `No stage at position ${position}.` };
  }

  const exact = stages.find((stage) => stage.key === trimmed);
  if (exact) return { ok: true, stage: exact };

  const normalized = trimmed.toLowerCase();
  const labelMatch = stages.find((stage) => stage.label.toLowerCase().includes(normalized));
  if (labelMatch) return { ok: true, stage: labelMatch };

  return { ok: false, message: `No stage: ${trimmed}.` };
}

export function pinnedStageContent(stages: UiStageSummary[], selectedStage: string | null): string {
  if (!selectedStage) return "";
  const pinnedStage = stages.find((stage) => stage.key === selectedStage);
  return pinnedStage?.event?.content || pinnedStage?.summary || "";
}

export function resolveNavCursorMove(
  visibleStages: UiStageSummary[],
  currentKey: string | null,
  direction: NavDirection
): string | null {
  if (visibleStages.length === 0) return null;
  const currentIndex = visibleStages.findIndex((stage) => stage.key === currentKey);
  if (currentIndex === -1) {
    return direction === "previous" ? visibleStages.at(-1)?.key ?? null : visibleStages[0]?.key ?? null;
  }
  const nextIndex = direction === "previous"
    ? Math.max(0, currentIndex - 1)
    : Math.min(visibleStages.length - 1, currentIndex + 1);
  return visibleStages[nextIndex]?.key ?? null;
}

export function resolveNavCursorAfterPrune(visibleStages: UiStageSummary[], previousIndex: number | null): string | null {
  if (visibleStages.length === 0) return null;
  const fallbackIndex = previousIndex === null
    ? visibleStages.length - 1
    : Math.min(Math.max(previousIndex, 0), visibleStages.length - 1);
  return visibleStages[fallbackIndex]?.key ?? null;
}

export function resolvePanelLines({
  showEvents,
  selectedStage,
  pinnedStageLines,
  outputLines,
  eventLines
}: PanelLinesInput): string[] {
  if (showEvents) return eventLines;
  if (selectedStage !== null) {
    return pinnedStageLines.length > 0 ? pinnedStageLines : ["No output for selected stage yet."];
  }
  return outputLines.length > 0 ? outputLines : eventLines;
}

export function stageVisual(status: UiStageStatus, theme: GemTerminalTheme) {
  const icon =
    status === "failed" ? "!" :
    status === "complete" ? "✓" :
    status === "running" ? ">" :
    status === "skipped" ? "-" : "·";
  return {
    icon,
    color: theme.stage[status],
    bold: status === "running" || status === "complete",
    dimColor: status === "pending"
  };
}

export function checkpointDecisionLines(): string[] {
  return [
    "Review retrieved sources",
    "/continue use sources  /redirect <guidance> refine retrieval  /stop end run"
  ];
}

export function buildEventLines(events: UiEvent[], error: string, width: number, notice = ""): string[] {
  const lines: string[] = [];
  const visibleEvents = events
    .filter((event) => event.event_type !== "final_answer" && event.event_type !== "stage_delta")
    .slice(-20);

  for (const event of visibleEvents) {
    lines.push(...wrapPlainText(event.title, width));
    if (event.summary) lines.push(...wrapPlainText(event.summary, width));
    if (event.content && !isDuplicateEventBody(event.summary, event.content)) {
      lines.push(...wrapPlainText(event.content, width));
    }
    lines.push("");
  }

  if (error) {
    lines.push(...wrapPlainText(`Error: ${error}`, width));
  }

  if (notice) {
    lines.push(...wrapPlainText(`Info: ${notice}`, width));
  }

  return lines.length > 0 ? lines : ["No output yet."];
}

function isDuplicateEventBody(summary: string, content: string): boolean {
  const normalizedSummary = normalizeEventBody(summary);
  const normalizedContent = normalizeEventBody(content);
  return normalizedSummary.length > 0 && normalizedSummary === normalizedContent;
}

function normalizeEventBody(value: string): string {
  return value.trim();
}

export function wrapPlainText(text: string, width: number): string[] {
  const usableWidth = Math.max(8, Math.floor(width));
  const sourceLines = text.split("\n");
  const wrapped: string[] = [];
  for (const sourceLine of sourceLines) {
    if (sourceLine.length <= usableWidth) {
      wrapped.push(sourceLine);
      continue;
    }
    let remaining = sourceLine;
    while (remaining.length > usableWidth) {
      const breakAt = Math.max(
        remaining.lastIndexOf(" ", usableWidth),
        remaining.lastIndexOf("/", usableWidth),
        remaining.lastIndexOf("-", usableWidth)
      );
      const index = breakAt >= Math.floor(usableWidth * 0.5) ? breakAt + 1 : usableWidth;
      wrapped.push(remaining.slice(0, index).trimEnd());
      remaining = remaining.slice(index).trimStart();
    }
    wrapped.push(remaining);
  }
  return wrapped;
}

function colorNameForToken(value: string | undefined, fallback: InkColorName | undefined): InkColorName {
  if (!value) return fallback ?? "white";
  const normalized = value.toLowerCase();
  if (normalized.includes("d50032")) return "red";
  if (normalized.includes("52c152")) return "green";
  if (normalized.includes("ffca36")) return "yellow";
  if (normalized.includes("30d6ff")) return "cyan";
  if (normalized.includes("993bff") || normalized.includes("ba82ff") || normalized.includes("500778")) {
    return "magenta";
  }
  if (normalized.includes("fafafa") || normalized.includes("ffffff")) return "white";
  if (normalized.includes("1f1f2e") || normalized.includes("1f102f") || normalized.includes("361a54")) return "blue";
  return fallback ?? "white";
}

function isCheckpointStage(stage: UiStageSummary): boolean {
  return stage.event?.event_type === "checkpoint_requested" ||
    stage.event?.event_type === "checkpoint_decision" ||
    stage.key.toLowerCase().includes("checkpoint");
}

function sessionMemoryPreviewLines(memory: UiSessionContext["memory"]): string[] {
  const sections: Array<[string, unknown]> = [
    ["Goal", memory.task_goal ?? memory.summary],
    ["State", memory.current_state],
    ["Next", memory.next_actions],
    ["Open", memory.open_questions],
    ["Decisions", memory.important_decisions],
    ["Sources", memory.known_sources]
  ];
  const lines: string[] = [];
  for (const [label, value] of sections) {
    const preview = previewMemoryValue(value);
    if (preview) lines.push(`${label}: ${preview}`);
  }
  return lines;
}

function previewMemoryValue(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (!Array.isArray(value)) return "";
  return value
    .filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    .slice(0, 3)
    .join("; ");
}

function formatRecallScore(score: number): string {
  return Number.isInteger(score) ? String(score) : score.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function promptRenderLine(
  line: PromptVisualLine,
  cursor: number,
  ghostSuffix: string,
  isCursorLine = true
): PromptRenderLine {
  if (!isCursorLine) {
    return {
      beforeCursor: line.text,
      cursorText: "",
      afterCursor: "",
      ghostSuffix: ""
    };
  }
  const column = Math.min(line.text.length, Math.max(0, cursor - line.start));
  return {
    beforeCursor: line.text.slice(0, column),
    cursorText: line.text[column] ?? " ",
    afterCursor: line.text.slice(column + (line.text[column] ? 1 : 0)),
    ghostSuffix: cursor === line.end ? ghostSuffix : ""
  };
}
