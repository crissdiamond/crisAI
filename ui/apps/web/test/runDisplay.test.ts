import assert from "node:assert/strict";
import test from "node:test";
import {
  latestLiveStageEvent,
  liveRunStatus,
  liveStageDisplayName,
  parseMarkdownBlocks,
  shouldShowTranscriptEvent
} from "../src/runDisplay.js";

test("normal transcript hides internal transport while verbose keeps debug events", () => {
  assert.equal(shouldShowTranscriptEvent({ event_type: "routing_decision" }, false), false);
  assert.equal(shouldShowTranscriptEvent({ event_type: "task_contract" }, false), false);
  assert.equal(shouldShowTranscriptEvent({ event_type: "run_completed" }, false), false);
  assert.equal(shouldShowTranscriptEvent({ event_type: "routing_decision" }, true), true);
  assert.equal(shouldShowTranscriptEvent({ event_type: "checkpoint_requested" }, false), true);
  assert.equal(shouldShowTranscriptEvent({ event_type: "stage_output" }, false), true);
});

test("stream deltas and final answers stay out of transcript event list", () => {
  assert.equal(shouldShowTranscriptEvent({ event_type: "stage_delta" }, true), false);
  assert.equal(shouldShowTranscriptEvent({ event_type: "final_answer" }, true), false);
});

test("live stage helper selects active stage starts and stream deltas until a terminal event arrives", () => {
  const started = { event_type: "stage_started" as const, content: "", title: "Plan", agent_id: "retrieval_planner" };
  const firstDelta = {
    event_type: "stage_delta" as const,
    content: "Searching",
    title: "Plan",
    agent_id: "retrieval_planner"
  };
  const secondDelta = {
    event_type: "stage_delta" as const,
    content: "Reading",
    title: "Read",
    agent_id: "context_retrieval"
  };

  assert.equal(latestLiveStageEvent([started]), started);
  assert.equal(latestLiveStageEvent([started, firstDelta, secondDelta]), secondDelta);
  assert.equal(latestLiveStageEvent([started, firstDelta, { event_type: "run_completed" as const }]), null);
  assert.equal(latestLiveStageEvent([started, firstDelta, { event_type: "run_failed" as const }]), null);
});

test("live stage labels and status stay user-facing", () => {
  assert.equal(liveStageDisplayName({ title: "Retrieve sources", agent_id: "context_retrieval" }), "Retrieve sources");
  assert.equal(liveStageDisplayName({ agent_id: "context_retrieval" }), "Context retrieval");
  assert.equal(liveRunStatus(false, { title: "Retrieve sources" }), "Running Retrieve sources.");
  assert.equal(liveRunStatus(true, { title: "Retrieve sources" }), "Decision needed: review retrieved sources.");
  assert.equal(liveRunStatus(false, null), "");
});

test("final answer markdown parses into semantic blocks", () => {
  const blocks = parseMarkdownBlocks(`# Recommendation

Use **Option A** with \`gateway\`.

- Read source
- Confirm owner

| Area | Decision |
| --- | --- |
| API | Proceed |

\`\`\`
status: ok
\`\`\`
`);

  assert.deepEqual(blocks.map((block) => block.type), ["heading", "paragraph", "list", "table", "code"]);
  assert.deepEqual(blocks[0], {
    type: "heading",
    level: 3,
    children: [{ type: "text", value: "Recommendation" }]
  });
  assert.equal(blocks[1].type, "paragraph");
  if (blocks[1].type === "paragraph") {
    assert.deepEqual(blocks[1].children, [
      { type: "text", value: "Use " },
      { type: "strong", value: "Option A" },
      { type: "text", value: " with " },
      { type: "code", value: "gateway" },
      { type: "text", value: "." }
    ]);
  }
  assert.equal(blocks[3].type, "table");
  if (blocks[3].type === "table") {
    assert.equal(blocks[3].headers.length, 2);
    assert.equal(blocks[3].rows.length, 1);
  }
});
