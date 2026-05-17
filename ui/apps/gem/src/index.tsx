#!/usr/bin/env node
import React, { useMemo, useState } from "react";
import { EventSource } from "eventsource";
import { Box, render, Text, useInput } from "ink";
import { CrisaiRuntimeClient, type UiEvent, type UiRunState } from "@crisai/contracts";

const runtime = new CrisaiRuntimeClient({
  baseUrl: process.env.CRISAI_RUNTIME_URL ?? "http://127.0.0.1:8000",
  eventSourceFactory: (url) => new EventSource(url) as unknown as globalThis.EventSource
});

function GemApp() {
  const [prompt, setPrompt] = useState("");
  const [run, setRun] = useState<UiRunState | null>(null);
  const [events, setEvents] = useState<UiEvent[]>([]);
  const [error, setError] = useState("");
  const status = useMemo(() => events.at(-1)?.status ?? run?.status ?? "idle", [events, run]);

  useInput((input, key) => {
    if (key.return && prompt.trim()) {
      void startRun(prompt);
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
          setEvents((current) => [...current, event]);
          if (event.event_type === "run_completed" || event.event_type === "run_failed") {
            source.close();
          }
        },
        () => setError("Runtime event stream disconnected.")
      );
    } catch (reason) {
      setError(String(reason));
    }
  }

  return (
    <Box flexDirection="column" height="100%">
      <Box borderStyle="single" borderColor="magenta" paddingX={1}>
        <Text bold>crisAI Gem</Text>
        <Text> | status: {status}</Text>
      </Box>

      <Box flexGrow={1} flexDirection="row">
        <Box width={28} borderStyle="single" borderColor="blue" paddingX={1} flexDirection="column">
          <Text bold>Stages</Text>
          {events.filter((event) => event.agent_id || event.stage).slice(-12).map((event, index) => (
            <Text key={`${event.event_type}-${event.timestamp}-${index}`}>
              {event.event_type === "stage_failed" ? "!" : "•"} {event.agent_id ?? event.stage}
            </Text>
          ))}
        </Box>

        <Box flexGrow={1} borderStyle="single" borderColor="white" paddingX={1} flexDirection="column">
          {events.length === 0 ? <Text dimColor>No output yet.</Text> : null}
          {events.slice(-10).map((event, index) => (
            <Box key={`${event.event_type}-${event.timestamp}-${index}`} flexDirection="column" marginBottom={1}>
              <Text bold>{event.title}</Text>
              {event.summary ? <Text>{event.summary}</Text> : null}
              {event.content ? <Text dimColor>{event.content}</Text> : null}
            </Box>
          ))}
          {error ? <Text color="red">{error}</Text> : null}
        </Box>
      </Box>

      <Box borderStyle="single" borderColor="magenta" paddingX={1}>
        <Text>{"> "}{prompt}</Text>
      </Box>

      <Box paddingX={1}>
        <Text dimColor>mode:auto | session:default | Enter to run | Ctrl+C to exit</Text>
      </Box>
    </Box>
  );
}

render(<GemApp />);
