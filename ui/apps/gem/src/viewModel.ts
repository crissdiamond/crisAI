import type { UiEvent, UiStageStatus, UiStageSummary } from "@crisai/contracts";

export const fallbackGemWidth = 132;
export const fallbackGemHeight = 40;
export const minimumGemWidth = 80;
export const minimumGemHeight = 24;
export const minimumStageSidebarWidth = 20;
export const maximumStageSidebarWidth = 34;
export const promptPanelHeight = 5;

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
  return stages.slice(-12);
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
    if (event.content) lines.push(...wrapPlainText(event.content, width));
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
