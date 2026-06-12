export type UiEventType =
  | "run_created"
  | "routing_decision"
  | "task_contract"
  | "stage_started"
  | "stage_delta"
  | "stage_output"
  | "stage_completed"
  | "stage_skipped"
  | "stage_failed"
  | "checkpoint_requested"
  | "checkpoint_decision"
  | "final_answer"
  | "run_failed"
  | "run_completed";

export type UiEvent = {
  schema_version: "ui_event_v1";
  event_type: UiEventType;
  run_id: string;
  timestamp: string;
  session: string;
  status: string;
  title: string;
  summary: string;
  content: string;
  verbose_content: string;
  mode: string | null;
  agent_id: string | null;
  stage: string | null;
  metadata: Record<string, unknown>;
};

export type UiProviderUsage = {
  requests?: number;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  cached_tokens?: number;
  reasoning_tokens?: number;
};

export type UiExecutionTime = {
  started_at?: string;
  ended_at?: string;
  duration_ms?: number;
};

export type UiStreamingObservability = {
  attempted?: boolean;
  fallback?: boolean;
  fallback_reason?: string;
};

export type UiStageObservability = {
  schema_version: "ui_stage_observability_v1";
  provider_usage?: UiProviderUsage;
  execution_time?: UiExecutionTime;
  streaming?: UiStreamingObservability;
};

export type UiObservabilityAggregate = {
  provider_usage: Required<UiProviderUsage>;
  duration_ms: number | null;
  stage_count: number;
};

export type UiRunRequest = {
  message: string;
  mode?: string;
  agent?: string;
  review?: boolean;
  verbose?: boolean;
  session?: string;
  retrieval_checkpoint?: boolean | null;
};

export type UiRunState = {
  schema_version: "ui_run_state_v1";
  run_id: string;
  session: string;
  status: string;
  decision: Record<string, unknown>;
  expected_stages: UiExpectedStage[];
  events: UiEvent[];
  final_output: string;
  error: string;
  metadata?: UiRunMetadata;
};

export type UiRunMetadata = {
  snapshot_schema_version?: string;
  created_at?: string;
  updated_at?: string;
  completed_at?: string;
  message_summary?: string;
  trace_run_id?: string;
  request_contract?: Record<string, unknown>;
  [key: string]: unknown;
};

export type UiRunSummary = {
  run_id: string;
  session: string;
  status: string;
  created_at: string;
  updated_at: string;
  completed_at: string;
  message_summary: string;
  mode: string;
  agent: string;
  expected_stages: UiExpectedStage[];
  event_count: number;
  stage_count: number;
  final_answer_summary: string;
  final_answer_length: number;
  error: string;
  display_order: number;
};

export type UiRunHistory = {
  schema_version: "ui_run_history_v1";
  session: string;
  runs: UiRunSummary[];
};

export type UiRunDetail = UiRunState & {
  metadata: UiRunMetadata;
};

export type UiHistoryEntry = {
  role: string;
  content: string;
};

export type UiSessionMemory = {
  schema_version?: string;
  task_goal?: string;
  current_state?: string;
  scope?: string[];
  assumptions?: string[];
  constraints?: string[];
  important_decisions?: string[];
  rejected_options?: string[];
  source_findings?: string[];
  known_sources?: string[];
  active_artefacts?: string[];
  open_questions?: string[];
  next_actions?: string[];
  last_outputs?: string[];
  do_not_repeat?: string[];
  summary?: string;
  known_sources_count?: number;
  updated_at?: string | null;
  [key: string]: unknown;
};

export type UiSessionRecallResult = {
  field: string;
  content: string;
  score: number;
  provenance: string;
  matched_terms: string[];
};

export type UiSessionContext = {
  schema_version: "ui_session_context_v1";
  session: string;
  baseline_brief: string;
  memory: UiSessionMemory;
  budget: {
    baseline_chars: number;
    baseline_char_limit: number;
    recall_limit: number;
    recall_count: number;
    truncated: boolean;
  };
  recall_query: string;
  recall_results: UiSessionRecallResult[];
};

export type UiSessionState = {
  sessions: string[];
  current_session: string;
  history: UiHistoryEntry[];
  memory?: UiSessionMemory;
};

export type UiWorkspaceRoots = {
  roots: Record<string, string>;
};

export type UiWorkspaceFileRecord = {
  path: string;
  name: string;
  size: number;
  editable: boolean;
};

export type UiWorkspaceTree = {
  root: string;
  path: string;
  files: UiWorkspaceFileRecord[];
};

export type UiWorkspaceFile = {
  path: string;
  content: string;
};

export type UiWorkspaceSaveResult = {
  path: string;
  saved: boolean;
};

export type UiWorkspaceRenameResult = {
  path: string;
  renamed: boolean;
};

export type UiWorkspaceUploadTarget = "task_inputs" | "knowledge_intake";

export type UiWorkspaceUploadRequest = {
  target: UiWorkspaceUploadTarget;
  session?: string;
  filename: string;
  content_base64: string;
};

export type UiWorkspaceUploadResult = {
  path: string;
  filename: string;
  size: number;
  target: string;
  uploaded: boolean;
};

export type UiExpectedStage = {
  key?: string;
  label?: string;
  [key: string]: unknown;
};

export type UiStageStatus = "pending" | "running" | "complete" | "skipped" | "failed";

export type UiStageSummary = {
  key: string;
  label: string;
  status: UiStageStatus;
  summary: string;
  event?: UiEvent;
};

export type UiTheme = {
  schema_version: "ui_theme_v1";
  default_theme?: string;
  themes: Record<string, { palette: Record<string, string> }>;
  surfaces: Record<string, Record<string, unknown>>;
};

export type CheckpointDecision = {
  action: "continue" | "redirect" | "stop";
  redirect_instruction?: string;
};

export type CrisaiClientOptions = {
  baseUrl?: string;
  apiToken?: string;
  eventSourceFactory?: (url: string) => EventSource;
};

export type UiEventSubscription = {
  close: () => void;
};

export const terminalEventTypes: UiEventType[] = ["run_completed", "run_failed"];
export const checkpointEventTypes: UiEventType[] = ["checkpoint_requested"];

const defaultBaseUrl = "http://127.0.0.1:8000";

export function isTerminalEvent(event: UiEvent): boolean {
  return terminalEventTypes.includes(event.event_type);
}

export function isCheckpointWaiting(events: UiEvent[]): boolean {
  const lastCheckpoint = [...events].reverse().find((event) =>
    event.event_type === "checkpoint_requested" || event.event_type === "checkpoint_decision"
  );
  return lastCheckpoint?.event_type === "checkpoint_requested";
}

export function deriveStageSummaries(events: UiEvent[], expectedStages: UiExpectedStage[] = []): UiStageSummary[] {
  const stages = new Map<string, UiStageSummary>();
  for (const stage of expectedStages) {
    const key = String(stage.key ?? stage.label ?? "").trim();
    if (!key) continue;
    stages.set(key, {
      key,
      label: String(stage.label ?? key),
      status: "pending",
      summary: ""
    });
  }

  for (const event of events) {
    const key = String(event.agent_id ?? event.stage ?? "").trim();
    if (!key) continue;
    const current = stages.get(key) ?? {
      key,
      label: key.replaceAll("_", " "),
      status: "pending" as UiStageStatus,
      summary: ""
    };
    const status = stageStatusFromEvent(event, current.status);
    stages.set(key, {
      ...current,
      status,
      summary: event.summary || event.content || current.summary,
      event
    });
  }

  return [...stages.values()];
}

export function latestFinalContent(state: UiRunState | null, events: UiEvent[]): string {
  const finalEvent = [...events].reverse().find((event) => event.event_type === "final_answer");
  return finalEvent?.content || state?.final_output || "";
}

export function latestLiveStageEvent<T extends Pick<UiEvent, "event_type">>(events: T[]): T | null {
  const terminal = [...events]
    .reverse()
    .find((event) => event.event_type === "run_completed" || event.event_type === "run_failed");
  if (terminal) return null;
  return [...events]
    .reverse()
    .find((event) => event.event_type === "stage_started" || event.event_type === "stage_delta") ?? null;
}

export function extractStageObservability(event: UiEvent): UiStageObservability | null {
  const observability = recordValue(event.metadata.observability);
  if (observability?.schema_version !== "ui_stage_observability_v1") {
    return null;
  }

  const providerUsage = providerUsageValue(observability.provider_usage);
  const executionTime = executionTimeValue(observability.execution_time);
  const streaming = streamingValue(observability.streaming);
  return {
    schema_version: "ui_stage_observability_v1",
    ...(providerUsage ? { provider_usage: providerUsage } : {}),
    ...(executionTime ? { execution_time: executionTime } : {}),
    ...(streaming ? { streaming } : {})
  };
}

export function aggregateStageObservability(events: UiEvent[]): UiObservabilityAggregate {
  const latestByStage = new Map<string, UiStageObservability>();
  for (const event of events) {
    const observability = extractStageObservability(event);
    if (!observability) continue;
    const stageIdentity = String(event.agent_id || event.stage || "").trim();
    if (!stageIdentity) continue;
    latestByStage.set(stageIdentity, observability);
  }

  const usage: Required<UiProviderUsage> = {
    requests: 0,
    input_tokens: 0,
    output_tokens: 0,
    total_tokens: 0,
    cached_tokens: 0,
    reasoning_tokens: 0
  };
  let durationMs = 0;
  let hasDuration = false;
  let stageCount = 0;

  for (const observability of latestByStage.values()) {
    stageCount += 1;
    if (observability.provider_usage) {
      usage.requests += observability.provider_usage.requests ?? 0;
      usage.input_tokens += observability.provider_usage.input_tokens ?? 0;
      usage.output_tokens += observability.provider_usage.output_tokens ?? 0;
      usage.total_tokens += observability.provider_usage.total_tokens ?? 0;
      usage.cached_tokens += observability.provider_usage.cached_tokens ?? 0;
      usage.reasoning_tokens += observability.provider_usage.reasoning_tokens ?? 0;
    }
    if (observability.execution_time?.duration_ms !== undefined) {
      durationMs += observability.execution_time.duration_ms;
      hasDuration = true;
    }
  }

  return {
    provider_usage: usage,
    duration_ms: hasDuration ? durationMs : null,
    stage_count: stageCount
  };
}

export function resolveThemePalette(theme: UiTheme, preferredTheme?: string): Record<string, string> {
  const themeName = preferredTheme ?? theme.default_theme ?? Object.keys(theme.themes)[0];
  return theme.themes[themeName]?.palette ?? {};
}

export function cssVariablesForSurface(theme: UiTheme, surface: string, preferredTheme?: string): Record<string, string> {
  const palette = resolveThemePalette(theme, preferredTheme);
  const surfaceConfig = theme.surfaces[surface] ?? {};
  const mapping = surfaceConfig.css_variables;
  if (!isRecord(mapping)) return {};
  const variables: Record<string, string> = {};
  for (const [cssName, paletteName] of Object.entries(mapping)) {
    if (typeof paletteName !== "string") continue;
    const value = palette[paletteName];
    if (value) {
      variables[`--${cssName}`] = value;
    }
  }
  return variables;
}

function stageStatusFromEvent(event: UiEvent, fallback: UiStageStatus): UiStageStatus {
  if (event.event_type === "stage_started" || event.event_type === "stage_delta") return "running";
  if (event.event_type === "stage_completed" || event.event_type === "stage_output" || event.event_type === "final_answer") {
    return "complete";
  }
  if (event.event_type === "stage_skipped") return "skipped";
  if (event.event_type === "stage_failed" || event.event_type === "run_failed") return "failed";
  return fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function recordValue(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null;
}

function providerUsageValue(value: unknown): UiProviderUsage | undefined {
  const record = recordValue(value);
  if (!record) return undefined;
  const usage: UiProviderUsage = {};
  copyFiniteInteger(record, usage, "requests");
  copyFiniteInteger(record, usage, "input_tokens");
  copyFiniteInteger(record, usage, "output_tokens");
  copyFiniteInteger(record, usage, "total_tokens");
  copyFiniteInteger(record, usage, "cached_tokens");
  copyFiniteInteger(record, usage, "reasoning_tokens");
  return Object.keys(usage).length > 0 ? usage : undefined;
}

function executionTimeValue(value: unknown): UiExecutionTime | undefined {
  const record = recordValue(value);
  if (!record) return undefined;
  const executionTime: UiExecutionTime = {};
  const startedAt = stringValue(record.started_at);
  const endedAt = stringValue(record.ended_at);
  const durationMs = finiteNonNegativeNumber(record.duration_ms);
  if (startedAt) executionTime.started_at = startedAt;
  if (endedAt) executionTime.ended_at = endedAt;
  if (durationMs !== null) executionTime.duration_ms = durationMs;
  return Object.keys(executionTime).length > 0 ? executionTime : undefined;
}

function streamingValue(value: unknown): UiStreamingObservability | undefined {
  const record = recordValue(value);
  if (!record) return undefined;
  const streaming: UiStreamingObservability = {};
  if (typeof record.attempted === "boolean") {
    streaming.attempted = record.attempted;
  }
  if (typeof record.fallback === "boolean") {
    streaming.fallback = record.fallback;
  }
  const fallbackReason = stringValue(record.fallback_reason);
  if (fallbackReason) {
    streaming.fallback_reason = fallbackReason;
  }
  return Object.keys(streaming).length > 0 ? streaming : undefined;
}

function copyFiniteInteger<T extends keyof UiProviderUsage>(
  source: Record<string, unknown>,
  target: UiProviderUsage,
  key: T
): void {
  const value = finiteNonNegativeInteger(source[key]);
  if (value !== null) {
    target[key] = value;
  }
}

function finiteNonNegativeInteger(value: unknown): number | null {
  const numberValue = typeof value === "number" ? value : typeof value === "string" ? Number(value) : NaN;
  return Number.isFinite(numberValue) && numberValue >= 0 ? Math.floor(numberValue) : null;
}

function finiteNonNegativeNumber(value: unknown): number | null {
  const numberValue = typeof value === "number" ? value : typeof value === "string" ? Number(value) : NaN;
  return Number.isFinite(numberValue) && numberValue >= 0 ? numberValue : null;
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export class CrisaiRuntimeClient {
  readonly baseUrl: string;
  private apiToken?: string;
  private readonly eventSourceFactory?: (url: string) => EventSource;

  constructor(options: CrisaiClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? defaultBaseUrl).replace(/\/$/, "");
    this.apiToken = options.apiToken;
    this.eventSourceFactory = options.eventSourceFactory;
  }

  setApiToken(apiToken?: string): void {
    const nextToken = apiToken?.trim();
    this.apiToken = nextToken || undefined;
  }

  async startRun(request: UiRunRequest): Promise<UiRunState> {
    const response = await fetch(`${this.baseUrl}/api/v1/runs`, {
      method: "POST",
      headers: this.requestHeaders({ json: true }),
      body: JSON.stringify({
        mode: "auto",
        agent: "auto",
        review: false,
        verbose: false,
        session: "default",
        ...request
      })
    });
    return this.readJson(response);
  }

  async getRun(runId: string): Promise<UiRunState> {
    const response = await fetch(`${this.baseUrl}/api/v1/runs/${encodeURIComponent(runId)}`, {
      headers: this.requestHeaders()
    });
    return this.readJson(response);
  }

  async submitCheckpoint(runId: string, decision: CheckpointDecision): Promise<{ status: string; action: string }> {
    const response = await fetch(`${this.baseUrl}/api/v1/runs/${encodeURIComponent(runId)}/checkpoint`, {
      method: "POST",
      headers: this.requestHeaders({ json: true }),
      body: JSON.stringify({
        redirect_instruction: "",
        ...decision
      })
    });
    return this.readJson(response);
  }

  async getTheme(): Promise<UiTheme> {
    const response = await fetch(`${this.baseUrl}/api/v1/ui/theme`, {
      headers: this.requestHeaders()
    });
    return this.readJson(response);
  }

  async listSessions(): Promise<UiSessionState> {
    const response = await fetch(`${this.baseUrl}/api/v1/sessions`, {
      headers: this.requestHeaders()
    });
    return this.readJson(response);
  }

  async createSession(session: string): Promise<UiSessionState> {
    const response = await fetch(`${this.baseUrl}/api/v1/sessions`, {
      method: "POST",
      headers: this.requestHeaders({ json: true }),
      body: JSON.stringify({ session })
    });
    return this.readJson(response);
  }

  async getSession(session: string): Promise<UiSessionState> {
    const response = await fetch(`${this.baseUrl}/api/v1/sessions/${encodeURIComponent(session)}`, {
      headers: this.requestHeaders()
    });
    return this.readJson(response);
  }

  async getSessionContext(session: string, query?: string, limit?: number): Promise<UiSessionContext> {
    const params = new URLSearchParams();
    if (query) {
      params.set("query", query);
    }
    if (limit !== undefined) {
      params.set("limit", String(limit));
    }
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const response = await fetch(`${this.baseUrl}/api/v1/sessions/${encodeURIComponent(session)}/context${suffix}`, {
      headers: this.requestHeaders()
    });
    return this.readJson(response);
  }

  async listSessionRuns(session: string, limit?: number): Promise<UiRunHistory> {
    const query = new URLSearchParams();
    if (limit !== undefined) {
      query.set("limit", String(limit));
    }
    const queryString = query.toString();
    const suffix = queryString ? `?${queryString}` : "";
    const response = await fetch(`${this.baseUrl}/api/v1/sessions/${encodeURIComponent(session)}/runs${suffix}`, {
      headers: this.requestHeaders()
    });
    return this.readJson(response);
  }

  async getSessionRun(session: string, runId: string): Promise<UiRunDetail> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/sessions/${encodeURIComponent(session)}/runs/${encodeURIComponent(runId)}`,
      {
        headers: this.requestHeaders()
      }
    );
    return this.readJson(response);
  }

  async getWorkspaceRoots(): Promise<UiWorkspaceRoots> {
    const response = await fetch(`${this.baseUrl}/api/v1/workspace/roots`, {
      headers: this.requestHeaders()
    });
    return this.readJson(response);
  }

  async getWorkspaceTree(rootName: string): Promise<UiWorkspaceTree> {
    const response = await fetch(`${this.baseUrl}/api/v1/workspace/tree/${encodeURIComponent(rootName)}`, {
      headers: this.requestHeaders()
    });
    return this.readJson(response);
  }

  async getWorkspaceFile(path: string): Promise<UiWorkspaceFile> {
    const query = new URLSearchParams({ path });
    const response = await fetch(`${this.baseUrl}/api/v1/workspace/file?${query.toString()}`, {
      headers: this.requestHeaders()
    });
    return this.readJson(response);
  }

  async saveWorkspaceFile(path: string, content: string): Promise<UiWorkspaceSaveResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/workspace/file`, {
      method: "POST",
      headers: this.requestHeaders({ json: true }),
      body: JSON.stringify({ path, content })
    });
    return this.readJson(response);
  }

  async renameWorkspaceFile(path: string, newName: string): Promise<UiWorkspaceRenameResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/workspace/rename`, {
      method: "POST",
      headers: this.requestHeaders({ json: true }),
      body: JSON.stringify({ path, new_name: newName })
    });
    return this.readJson(response);
  }

  async uploadWorkspaceFile(request: UiWorkspaceUploadRequest): Promise<UiWorkspaceUploadResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/workspace/upload`, {
      method: "POST",
      headers: this.requestHeaders({ json: true }),
      body: JSON.stringify(request)
    });
    return this.readJson(response);
  }

  subscribe(runId: string, onEvent: (event: UiEvent) => void, onError?: (error: Event) => void): UiEventSubscription {
    const url = `${this.baseUrl}/api/v1/runs/${encodeURIComponent(runId)}/events`;
    if (this.apiToken) {
      return this.subscribeWithFetch(url, onEvent, onError);
    }
    const createEventSource = this.eventSourceFactory ?? ((target) => new EventSource(target));
    const source = createEventSource(url);
    const eventTypes: UiEventType[] = [
      "run_created",
      "routing_decision",
      "task_contract",
      "stage_started",
      "stage_delta",
      "stage_output",
      "stage_completed",
      "stage_skipped",
      "stage_failed",
      "checkpoint_requested",
      "checkpoint_decision",
      "final_answer",
      "run_failed",
      "run_completed"
    ];
    for (const eventType of eventTypes) {
      source.addEventListener(eventType, (message) => {
        onEvent(JSON.parse((message as MessageEvent).data) as UiEvent);
      });
    }
    if (onError) {
      source.onerror = onError;
    }
    return source;
  }

  private requestHeaders(options: { json?: boolean } = {}): HeadersInit {
    const headers: Record<string, string> = {};
    if (options.json) {
      headers["content-type"] = "application/json";
    }
    if (this.apiToken) {
      headers.authorization = `Bearer ${this.apiToken}`;
    }
    return headers;
  }

  private subscribeWithFetch(
    url: string,
    onEvent: (event: UiEvent) => void,
    onError?: (error: Event) => void
  ): UiEventSubscription {
    const controller = new AbortController();
    void this.readEventStream(url, controller.signal, onEvent).catch(() => {
      if (!controller.signal.aborted && onError) {
        onError(new Event("error"));
      }
    });
    return {
      close: () => controller.abort()
    };
  }

  private async readEventStream(
    url: string,
    signal: AbortSignal,
    onEvent: (event: UiEvent) => void
  ): Promise<void> {
    const response = await fetch(url, {
      headers: this.requestHeaders(),
      signal
    });
    if (!response.ok) {
      await this.readJson(response);
      return;
    }
    if (!response.body) {
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (!signal.aborted) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const data = frame
          .split(/\r?\n/)
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (data) {
          onEvent(JSON.parse(data) as UiEvent);
        }
      }
    }
  }

  private async readJson<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`crisAI runtime request failed (${response.status}): ${body}`);
    }
    return response.json() as Promise<T>;
  }
}
