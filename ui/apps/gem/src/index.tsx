#!/usr/bin/env node
import React, { useMemo, useState } from "react";
import { EventSource } from "eventsource";
import { Box, render, Text, useInput } from "ink";
import {
  CrisaiRuntimeClient,
  deriveStageSummaries,
  isCheckpointWaiting,
  isTerminalEvent,
  latestFinalContent,
  resolveThemePalette,
  type UiEvent,
  type UiRunState,
  type UiStageSummary
} from "@crisai/contracts";

const runtime = new CrisaiRuntimeClient({
  baseUrl: process.env.CRISAI_RUNTIME_URL ?? "http://127.0.0.1:8000",
  eventSourceFactory: (url) => new EventSource(url) as unknown as globalThis.EventSource
});

function GemApp() {
  const [prompt, setPrompt] = useState("");
  const [run, setRun] = useState<UiRunState | null>(null);
  const [events, setEvents] = useState<UiEvent[]>([]);
  const [error, setError] = useState("");
  const [accent, setAccent] = useState("magenta");
  const status = useMemo(() => events.at(-1)?.status ?? run?.status ?? "idle", [events, run]);
  const stages = useMemo(() => deriveStageSummaries(events, run?.expected_stages ?? []), [events, run]);
  const checkpointWaiting = useMemo(() => isCheckpointWaiting(events), [events]);
  const finalContent = useMemo(() => latestFinalContent(run, events), [run, events]);

  React.useEffect(() => {
    runtime
      .getTheme()
      .then((theme) => {
        const palette = resolveThemePalette(theme);
        setAccent(palette.accent_bright ? "magenta" : "blue");
      })
      .catch(() => undefined);
  }, []);

  useInput((input, key) => {
    if (key.return && prompt.trim()) {
      const command = prompt.trim();
      if (checkpointWaiting && command.startsWith("/")) {
        void handleCheckpointCommand(command);
      } else {
        void startRun(command);
      }
      setPrompt("");
      return;
    }
    if (key.backspace || key.delete) {
      setPrompt((current) => current.slice(0, -1));
      return;
    }
    if (!key.ctrl && input) {
      setPrompt((current) => current + input);
    }
  });

  async function startRun(message: string) {
    try {
      setError("");
      setEvents([]);
      const started = await runtime.startRun({ message, mode: "auto", session: "default" });
      setRun(started);
      setEvents(started.events);
      const source = runtime.subscribe(
        started.run_id,
        (event) => {
          setEvents((current) => dedupeEvents([...current, event]));
          if (isTerminalEvent(event)) {
            source.close();
            runtime.getRun(started.run_id).then(setRun).catch((reason: unknown) => setError(String(reason)));
          }
        },
        () => setError("Runtime event stream disconnected.")
      );
    } catch (reason) {
      setError(String(reason));
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
        <Text> | status: {status}</Text>
        {checkpointWaiting ? <Text color="yellow"> | checkpoint waiting</Text> : null}
      </Box>

      <Box flexGrow={1} flexDirection="row">
        <Box width={28} borderStyle="single" borderColor="blue" paddingX={1} flexDirection="column">
          <Text bold>Stages</Text>
          {stages.length === 0 ? <Text dimColor>No stages yet.</Text> : null}
          {stages.slice(-12).map((stage) => <StageLine key={stage.key} stage={stage} />)}
        </Box>

        <Box flexGrow={1} borderStyle="single" borderColor="white" paddingX={1} flexDirection="column">
          {events.length === 0 ? <Text dimColor>No output yet.</Text> : null}
          {events.filter((event) => event.event_type !== "final_answer").slice(-10).map((event, index) => (
            <Box key={`${event.event_type}-${event.timestamp}-${index}`} flexDirection="column" marginBottom={1}>
              <Text bold>{event.title}</Text>
              {event.summary ? <Text>{event.summary}</Text> : null}
              {event.content ? <Text dimColor>{event.content}</Text> : null}
            </Box>
          ))}
          {finalContent ? (
            <Box flexDirection="column" marginBottom={1}>
              <Text bold color="green">Final answer</Text>
              <Text>{finalContent}</Text>
            </Box>
          ) : null}
          {error ? <Text color="red">{error}</Text> : null}
        </Box>
      </Box>

      <Box borderStyle="single" borderColor={accent} paddingX={1}>
        <Text>{"> "}{prompt}</Text>
      </Box>

      <Box paddingX={1}>
        <Text dimColor>
          {checkpointWaiting
            ? "checkpoint: /continue | /redirect <guidance> | /stop"
            : "mode:auto | session:default | Enter to run | Ctrl+C to exit"}
        </Text>
      </Box>
    </Box>
  );
}

function StageLine({ stage }: { stage: UiStageSummary }) {
  const marker = stage.status === "failed" ? "!" : stage.status === "complete" ? "✓" : stage.status === "running" ? ">" : "•";
  const color = stage.status === "failed" ? "red" : stage.status === "complete" ? "green" : stage.status === "running" ? "yellow" : undefined;
  return (
    <Text color={color}>
      {marker} {stage.label}
    </Text>
  );
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
