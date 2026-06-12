import { latestLiveStageEvent, type UiEvent } from "@crisai/contracts";

export { latestLiveStageEvent };

/** Return the most recent readable output a given stage produced. */
export function stageOutputContent(events: UiEvent[], stageKey: string, verbose: boolean): string {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if ((event.agent_id ?? event.stage ?? "") !== stageKey) continue;
    const content = verbose && event.verbose_content ? event.verbose_content : event.content;
    if (content && content.trim()) return content;
  }
  return "";
}

export type MarkdownInlineToken =
  | { type: "text"; value: string }
  | { type: "strong"; value: string }
  | { type: "code"; value: string };

export type MarkdownBlock =
  | { type: "heading"; level: number; children: MarkdownInlineToken[] }
  | { type: "paragraph"; children: MarkdownInlineToken[] }
  | { type: "list"; items: MarkdownInlineToken[][] }
  | { type: "code"; value: string }
  | { type: "table"; headers: MarkdownInlineToken[][]; rows: MarkdownInlineToken[][][] };

export const normalTranscriptHiddenEventTypes = new Set<UiEvent["event_type"]>([
  "run_created",
  "routing_decision",
  "task_contract",
  "checkpoint_decision",
  "run_completed"
]);

export function shouldShowTranscriptEvent(event: Pick<UiEvent, "event_type">, verbose: boolean): boolean {
  if (event.event_type === "final_answer" || event.event_type === "stage_delta") {
    return false;
  }
  if (verbose) {
    return true;
  }
  return !normalTranscriptHiddenEventTypes.has(event.event_type);
}

export function liveStageDisplayName(event: Pick<UiEvent, "agent_id" | "stage" | "title">): string {
  return event.title || humanizeLabel(event.agent_id ?? event.stage ?? "stage");
}

// Plain-language names for each raw event type. The raw snake_case
// `event_type` is never shown to users; this map provides a friendly label.
const eventTypeDisplayNames: Record<UiEvent["event_type"], string> = {
  run_created: "Run started",
  routing_decision: "Routing",
  task_contract: "Task setup",
  stage_started: "Step started",
  stage_delta: "Step output",
  stage_output: "Step output",
  stage_completed: "Step complete",
  stage_skipped: "Step skipped",
  stage_failed: "Step failed",
  checkpoint_requested: "Review sources",
  checkpoint_decision: "Decision",
  final_answer: "Final answer",
  run_failed: "Run failed",
  run_completed: "Run complete"
};

/**
 * Returns a human-readable label for an event card.
 *
 * Prefers the event's own `title` when present and non-empty, otherwise falls
 * back to the humanized event type. The raw snake_case `event_type` is never
 * returned.
 */
export function eventDisplayTitle(event: Pick<UiEvent, "event_type" | "title">): string {
  if (event.title && event.title.trim()) {
    return event.title;
  }
  return eventTypeDisplayNames[event.event_type] ?? humanizeLabel(event.event_type);
}

export function liveRunStatus(
  checkpointWaiting: boolean,
  liveStageEvent: Pick<UiEvent, "agent_id" | "stage" | "title"> | null
): string {
  if (checkpointWaiting) {
    return "Decision needed: review retrieved sources.";
  }
  if (liveStageEvent) {
    return `Running ${liveStageDisplayName(liveStageEvent)}.`;
  }
  return "";
}

export function parseMarkdownBlocks(content: string): MarkdownBlock[] {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: MarkdownBlock[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    const heading = /^(#{1,4})\s+(.+)$/.exec(line);
    if (heading) {
      blocks.push({
        type: "heading",
        level: Math.min(heading[1].length + 2, 6),
        children: parseInlineMarkdown(heading[2])
      });
      index += 1;
      continue;
    }

    if (/^```/.test(line)) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !/^```/.test(lines[index])) {
        codeLines.push(lines[index]);
        index += 1;
      }
      blocks.push({ type: "code", value: codeLines.join("\n") });
      index += 1;
      continue;
    }

    if (isMarkdownTableStart(lines, index)) {
      const tableLines: string[] = [];
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        tableLines.push(lines[index]);
        index += 1;
      }
      blocks.push(parseMarkdownTable(tableLines));
      continue;
    }

    if (/^\s*[-*]\s+/.test(line)) {
      const items: MarkdownInlineToken[][] = [];
      while (index < lines.length && /^\s*[-*]\s+/.test(lines[index])) {
        items.push(parseInlineMarkdown(lines[index].replace(/^\s*[-*]\s+/, "")));
        index += 1;
      }
      blocks.push({ type: "list", items });
      continue;
    }

    const paragraphLines = [line.trim()];
    index += 1;
    while (
      index < lines.length &&
      lines[index].trim() &&
      !/^(#{1,4})\s+/.test(lines[index]) &&
      !/^```/.test(lines[index]) &&
      !/^\s*[-*]\s+/.test(lines[index]) &&
      !isMarkdownTableStart(lines, index)
    ) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ type: "paragraph", children: parseInlineMarkdown(paragraphLines.join(" ")) });
  }
  return blocks;
}

/**
 * Title-cases a snake_case identifier for display.
 *
 * `fallback` is returned when `value` is empty after normalisation; callers in a
 * stage context use the default "Stage", while session-memory callers pass
 * "Memory" to keep their original empty-label wording.
 */
export function humanizeLabel(value: string, fallback = "Stage"): string {
  const label = value.replaceAll("_", " ").trim();
  return label ? label.charAt(0).toUpperCase() + label.slice(1) : fallback;
}

export function parseInlineMarkdown(value: string): MarkdownInlineToken[] {
  const nodes: MarkdownInlineToken[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(value)) !== null) {
    if (match.index > lastIndex) {
      nodes.push({ type: "text", value: value.slice(lastIndex, match.index) });
    }
    const token = match[0];
    if (token.startsWith("**")) {
      nodes.push({ type: "strong", value: token.slice(2, -2) });
    } else {
      nodes.push({ type: "code", value: token.slice(1, -1) });
    }
    lastIndex = match.index + token.length;
  }
  if (lastIndex < value.length) {
    nodes.push({ type: "text", value: value.slice(lastIndex) });
  }
  return nodes;
}

function isMarkdownTableStart(lines: string[], index: number): boolean {
  return Boolean(
    lines[index]?.includes("|") &&
      lines[index + 1]?.includes("|") &&
      /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[index + 1])
  );
}

function parseMarkdownTable(lines: string[]): MarkdownBlock {
  const [headerLine, , ...bodyLines] = lines;
  const headers = splitMarkdownTableRow(headerLine).map(parseInlineMarkdown);
  const rows = bodyLines.map((row) => splitMarkdownTableRow(row).map(parseInlineMarkdown));
  return { type: "table", headers, rows };
}

function splitMarkdownTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}
