#!/usr/bin/env node
import chalk from "chalk";
import React, { useMemo, useState } from "react";
import { EventSource } from "eventsource";
import { Box, render, Text, useInput, useStdout } from "ink";
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

const runtimeBaseUrl = process.env.CRISAI_RUNTIME_URL ?? "http://127.0.0.1:8000";

const runtime = new CrisaiRuntimeClient({
  baseUrl: runtimeBaseUrl,
  apiToken: process.env.CRISAI_API_KEY ?? process.env.CRISAI_API_TOKEN,
  eventSourceFactory: (url) => new EventSource(url) as unknown as globalThis.EventSource
});

// --- Markdown rendering ---

function renderMarkdownLines(text: string): string[] {
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
      result.push("  " + chalk.cyan(raw));
      continue;
    }

    if (raw.startsWith("### ")) { result.push(chalk.bold(raw.slice(4))); continue; }
    if (raw.startsWith("## "))  { result.push(chalk.bold.underline(raw.slice(3))); continue; }
    if (raw.startsWith("# "))   { result.push(chalk.bold.underline(raw.slice(2))); continue; }

    if (/^[-*_]{3,}$/.test(raw.trim())) {
      result.push(chalk.dim("─".repeat(40)));
      continue;
    }

    if (raw.startsWith("> ")) {
      result.push(chalk.dim("│ ") + chalk.italic(renderInline(raw.slice(2))));
      continue;
    }

    const ulMatch = raw.match(/^(  )?[-*+] (.*)/);
    if (ulMatch) {
      const indent = ulMatch[1] ? "    " : "  ";
      result.push(indent + chalk.yellow("•") + " " + renderInline(ulMatch[2]));
      continue;
    }

    const olMatch = raw.match(/^(\d+)\. (.*)/);
    if (olMatch) {
      result.push("  " + chalk.yellow(olMatch[1] + ".") + " " + renderInline(olMatch[2]));
      continue;
    }

    if (raw.startsWith("    ")) {
      result.push("  " + chalk.cyan(raw.trimStart()));
      continue;
    }

    result.push(renderInline(raw));
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
        <Text key={scrollTop + i}>{line || " "}</Text>
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

function StageLine({ stage }: { stage: UiStageSummary }) {
  const marker =
    stage.status === "failed" ? "!" :
    stage.status === "complete" ? "✓" :
    stage.status === "running" ? ">" : "•";
  const color =
    stage.status === "failed" ? "red" :
    stage.status === "complete" ? "green" :
    stage.status === "running" ? "yellow" : undefined;
  return <Text color={color}>{marker} {stage.label}</Text>;
}

// --- Main app ---

function GemApp() {
  const { stdout } = useStdout();
  // header(3) + main-borders(2) + prompt(3) + hints(1) = 9 fixed rows
  const transcriptHeight = Math.max(8, (stdout?.rows ?? 24) - 9);

  const [prompt, setPrompt] = useState("");
  const [run, setRun] = useState<UiRunState | null>(null);
  const [events, setEvents] = useState<UiEvent[]>([]);
  const [error, setError] = useState("");
  const [accent, setAccent] = useState("magenta");
  const [session, setSession] = useState("default");
  const [sessions, setSessions] = useState<string[]>(["default"]);
  const [scrollTop, setScrollTop] = useState(0);
  const [showEvents, setShowEvents] = useState(false);
  const [commandHistory, setCommandHistory] = useState<string[]>([]);
  const [historyCursor, setHistoryCursor] = useState<number | null>(null);

  const status = useMemo(() => events.at(-1)?.status ?? run?.status ?? "idle", [events, run]);
  const stages = useMemo(() => deriveStageSummaries(events, run?.expected_stages ?? []), [events, run]);
  const checkpointWaiting = useMemo(() => isCheckpointWaiting(events), [events]);
  const finalContent = useMemo(() => latestFinalContent(run, events), [run, events]);
  const finalLines = useMemo(() => renderMarkdownLines(finalContent), [finalContent]);
  const liveStageEvent = useMemo(() => latestLiveStageEvent(events), [events]);
  const liveLines = useMemo(() => renderMarkdownLines(liveStageEvent?.content ?? ""), [liveStageEvent]);
  const outputLines = finalLines.length > 0 ? finalLines : liveLines;
  const contentH = Math.max(1, transcriptHeight - 1);
  const maxScroll = Math.max(0, outputLines.length - contentH);
  const inScrollMode = outputLines.length > 0 && !showEvents;
  const isLiveOutput = finalLines.length === 0 && liveLines.length > 0;

  React.useEffect(() => {
    runtime
      .getTheme()
      .then((theme) => {
        const palette = resolveThemePalette(theme);
        setAccent(palette.accent_bright ? "magenta" : "blue");
      })
      .catch(() => undefined);
  }, []);

  React.useEffect(() => {
    runtime
      .listSessions()
      .then(applySessionState)
      .catch((reason: unknown) => setError(formatRuntimeError(reason)));
  }, []);

  useInput((input, key) => {
    // Scroll output pane when a streamed or final answer is showing.
    if (inScrollMode) {
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

    if (key.tab && outputLines.length > 0) {
      setShowEvents((prev) => !prev);
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
  });

  function applySessionState(state: UiSessionState) {
    setSession(state.current_session);
    setSessions(state.sessions.length > 0 ? state.sessions : [state.current_session]);
  }

  async function startRun(message: string) {
    try {
      setError("");
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
      if (command === "/sessions") {
        const state = await runtime.listSessions();
        applySessionState(state);
        setError(`sessions: ${state.sessions.join(", ")}`);
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
  }

  return (
    <Box flexDirection="column" height="100%">
      <Box borderStyle="single" borderColor={accent} paddingX={1}>
        <Text bold>crisAI Gem</Text>
        <Text> | {status}</Text>
        <Text> | {session}</Text>
        {checkpointWaiting ? <Text color="yellow"> | checkpoint</Text> : null}
        {isLiveOutput ? <Text color="yellow"> | streaming</Text> : null}
        {inScrollMode ? <Text dimColor> | tab: events</Text> : null}
      </Box>

      <Box flexGrow={1} flexDirection="row">
        <Box width={28} borderStyle="single" borderColor="blue" paddingX={1} flexDirection="column">
          <Text bold>Stages</Text>
          {stages.length === 0 ? <Text dimColor>No stages yet.</Text> : null}
          {stages.slice(-12).map((stage) => <StageLine key={stage.key} stage={stage} />)}
        </Box>

        <Box flexGrow={1} borderStyle="single" borderColor="white" paddingX={1} flexDirection="column">
          {inScrollMode ? (
            <ScrollPane lines={outputLines} height={transcriptHeight} scrollTop={scrollTop} />
          ) : (
            <>
              {events.length === 0 ? <Text dimColor>No output yet.</Text> : null}
              {events
                .filter((event) => event.event_type !== "final_answer" && event.event_type !== "stage_delta")
                .slice(-10)
                .map((event, index) => (
                  <Box key={`${event.event_type}-${event.timestamp}-${index}`} flexDirection="column" marginBottom={1}>
                    <Text bold>{event.title}</Text>
                    {event.summary ? <Text>{event.summary}</Text> : null}
                    {event.content ? <Text dimColor>{event.content}</Text> : null}
                  </Box>
                ))}
              {finalLines.length > 0 ? (
                <Text dimColor>Answer ready — press tab to read</Text>
              ) : liveLines.length > 0 ? (
                <Text dimColor>Streaming output — press tab to follow</Text>
              ) : null}
              {error ? <Text color="red">{error}</Text> : null}
            </>
          )}
        </Box>
      </Box>

      <Box borderStyle="single" borderColor={accent} paddingX={1}>
        <Text>{"> "}{prompt}</Text>
      </Box>

      <Box paddingX={1}>
        <Text dimColor>
          {checkpointWaiting
            ? "checkpoint: /continue | /redirect <guidance> | /stop"
            : inScrollMode
              ? `↑↓/PgUp/PgDn scroll · tab: events · /session <name>`
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
