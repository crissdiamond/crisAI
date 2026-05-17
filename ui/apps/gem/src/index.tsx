#!/usr/bin/env node
import chalk from "chalk";
import React, { useMemo, useState } from "react";
import { EventSource } from "eventsource";
import { Box, render, Text, useInput, useStdin, useStdout } from "ink";
import {
  CrisaiRuntimeClient,
  deriveStageSummaries,
  isCheckpointWaiting,
  isTerminalEvent,
  latestFinalContent,
  resolveThemePalette,
  type UiEvent,
  type UiRunState,
  type UiSessionState,
  type UiStageSummary
} from "@crisai/contracts";
import {
  buildEventLines,
  checkpointDecisionLines,
  clampScrollTop,
  defaultGemTerminalTheme,
  fallbackGemHeight,
  fallbackGemWidth,
  gemTerminalThemeFromPalette,
  minimumGemHeight,
  minimumGemWidth,
  promptPanelHeight,
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
  theme
}: {
  stage: UiStageSummary;
  sidebarWidth: number;
  theme: GemTerminalTheme;
}) {
  const visual = stageVisual(stage.status, theme);
  const shortLabel = truncateStageLabel(stage.label, sidebarWidth);

  return (
    <Text
      bold={visual.bold}
      color={visual.color}
      dimColor={visual.dimColor}
      wrap="truncate-end"
    >
      [{visual.icon} {shortLabel}]
    </Text>
  );
}

// --- Main app ---

function GemApp() {
  const { stdout } = useStdout();
  const { isRawModeSupported } = useStdin();
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

  const [prompt, setPrompt] = useState("");
  const [run, setRun] = useState<UiRunState | null>(null);
  const [events, setEvents] = useState<UiEvent[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [terminalTheme, setTerminalTheme] = useState(defaultGemTerminalTheme);
  const [session, setSession] = useState("default");
  const [sessions, setSessions] = useState<string[]>(["default"]);
  const [scrollTop, setScrollTop] = useState(0);
  const [showEvents, setShowEvents] = useState(false);
  const [commandHistory, setCommandHistory] = useState<string[]>([]);
  const [historyCursor, setHistoryCursor] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const status = useMemo(() => events.at(-1)?.status ?? run?.status ?? "idle", [events, run]);
  const statusMetrics = useMemo(() => buildStatusMetrics(events, now), [events, now]);
  const stages = useMemo(() => deriveStageSummaries(events, run?.expected_stages ?? []), [events, run]);
  const checkpointWaiting = useMemo(() => isCheckpointWaiting(events), [events]);
  const finalContent = useMemo(() => latestFinalContent(run, events), [run, events]);
  const finalLines = useMemo(() => renderMarkdownLines(finalContent, outputPanelWidth), [finalContent, outputPanelWidth]);
  const liveStageEvent = useMemo(() => latestLiveStageEvent(events), [events]);
  const liveLines = useMemo(
    () => renderMarkdownLines(liveStageEvent?.content ?? "", outputPanelWidth),
    [liveStageEvent, outputPanelWidth]
  );
  const eventLines = useMemo(
    () => buildEventLines(events, error, outputPanelWidth, notice),
    [events, error, notice, outputPanelWidth]
  );
  const outputLines = finalLines.length > 0 ? finalLines : liveLines;
  const panelLines = showEvents ? eventLines : outputLines.length > 0 ? outputLines : eventLines;
  const contentH = resolvePanelContentHeight(transcriptHeight);
  const maxScroll = Math.max(0, panelLines.length - contentH);
  const canScrollPanel = panelLines.length > contentH;
  const isLiveOutput = finalLines.length === 0 && liveLines.length > 0;

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
    setScrollTop((current) => clampScrollTop(current, panelLines.length, contentH));
  }, [panelLines.length, contentH]);

  useInput((input, key) => {
    // Scroll the bounded transcript pane whenever visible content exceeds it.
    if (canScrollPanel) {
      if (key.upArrow) { setScrollTop((prev) => Math.max(0, prev - 1)); return; }
      if (key.downArrow) { setScrollTop((prev) => Math.min(maxScroll, prev + 1)); return; }
      if (key.pageUp) { setScrollTop((prev) => Math.max(0, prev - Math.max(1, contentH - 1))); return; }
      if (key.pageDown) { setScrollTop((prev) => Math.min(maxScroll, prev + Math.max(1, contentH - 1))); return; }
    } else {
      if (key.upArrow && commandHistory.length > 0) {
        const next = historyCursor === null ? commandHistory.length - 1 : Math.max(0, historyCursor - 1);
        setHistoryCursor(next);
        setPrompt(commandHistory[next] ?? "");
        return;
      }
      if (key.downArrow && commandHistory.length > 0) {
        if (historyCursor === null) return;
        const next = historyCursor + 1;
        if (next >= commandHistory.length) {
          setHistoryCursor(null);
          setPrompt("");
        } else {
          setHistoryCursor(next);
          setPrompt(commandHistory[next] ?? "");
        }
        return;
      }
    }

    if (key.tab && (outputLines.length > 0 || eventLines.length > 0)) {
      setShowEvents((prev) => !prev);
      setScrollTop(0);
      return;
    }

    if (key.return && prompt.trim()) {
      const command = prompt.trim();
      setCommandHistory((current) => current.at(-1) === command ? current : [...current, command].slice(-100));
      setHistoryCursor(null);
      if (checkpointWaiting && command.startsWith("/")) {
        void handleCheckpointCommand(command);
      } else if (command === "/sessions" || command.startsWith("/session ")) {
        void handleSessionCommand(command);
      } else {
        void startRun(command);
      }
      setPrompt("");
      return;
    }
    if (key.backspace || key.delete) {
      setHistoryCursor(null);
      setPrompt((prev) => prev.slice(0, -1));
      return;
    }
    if (!key.ctrl && input) {
      setHistoryCursor(null);
      setPrompt((prev) => prev + input);
    }
  }, { isActive: inputActive });

  function applySessionState(state: UiSessionState) {
    setSession(state.current_session);
    setSessions(state.sessions.length > 0 ? state.sessions : [state.current_session]);
  }

  async function startRun(message: string) {
    try {
      setError("");
      setNotice("");
      setEvents([]);
      setScrollTop(0);
      setShowEvents(false);
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

  async function handleSessionCommand(command: string) {
    try {
      setError("");
      setNotice("");
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

  async function handleCheckpointCommand(command: string) {
    try {
      setError("");
      setNotice("");
      if (!run) return;
      if (command === "/continue") {
        await runtime.submitCheckpoint(run.run_id, { action: "continue" });
        return;
      }
      if (command === "/stop") {
        await runtime.submitCheckpoint(run.run_id, { action: "stop" });
        return;
      }
      if (command.startsWith("/redirect ")) {
        await runtime.submitCheckpoint(run.run_id, {
          action: "redirect",
          redirect_instruction: command.replace(/^\/redirect\s+/, "")
        });
        return;
      }
      setError("Checkpoint commands: /continue, /stop, or /redirect <guidance>.");
    } catch (reason) {
      setError(formatRuntimeError(reason));
    }
  }

  return (
    <Box flexDirection="column" width={viewportWidth} height={viewportHeight}>
      <Box height={3} borderStyle="single" borderColor={terminalTheme.accent} paddingX={1}>
        <Text bold>crisAI Gem</Text>
        <Text> | {status}</Text>
        <Text> | {session}</Text>
        {checkpointWaiting ? <Text color={terminalTheme.checkpoint.label}> | decision needed</Text> : null}
        {isLiveOutput ? <Text color={terminalTheme.stage.running}> | streaming</Text> : null}
        <Text dimColor wrap="truncate-end">{showEvents ? " | tab: output" : " | tab: events"}</Text>
      </Box>

      <Box height={transcriptHeight + 2} flexDirection="row">
        <Box width={stageSidebarWidth} borderStyle="single" borderColor={terminalTheme.border} paddingX={1} flexDirection="column">
          <Text bold>Stages</Text>
          {stages.length === 0 ? <Text dimColor>No stages yet.</Text> : null}
          {stages.slice(-12).map((stage, index) => (
            <StageItem
              key={`${stage.key}-${index}`}
              stage={stage}
              sidebarWidth={stageSidebarWidth}
              theme={terminalTheme}
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
          <Text dimColor>Prompt</Text>
        )}
        <Text wrap="truncate-end">{"> "}{prompt}</Text>
      </Box>

      <Box paddingX={1}>
        <Text dimColor wrap="truncate-end">
          {`${statusMetrics.model} | ${statusMetrics.elapsed} | tokens:${statusMetrics.tokens} | cost:${statusMetrics.cost} | `}
          {checkpointWaiting
            ? "decision: /continue use sources | /stop end run | /redirect refine"
            : canScrollPanel
              ? `↑↓/PgUp/PgDn scroll · tab: ${showEvents ? "output" : "events"} · /session <name>`
              : `mode:auto | session:${session} | sessions:${sessions.length} | ↑↓ history | /session <name>`}
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
