export type UiEventType =
  | "run_created"
  | "routing_decision"
  | "task_contract"
  | "stage_started"
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
};

export type UiHistoryEntry = {
  role: string;
  content: string;
};

export type UiSessionMemory = {
  schema_version?: string;
  summary?: string;
  known_sources_count?: number;
  updated_at?: string | null;
  [key: string]: unknown;
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
  eventSourceFactory?: (url: string) => EventSource;
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
  if (event.event_type === "stage_started") return "running";
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

export class CrisaiRuntimeClient {
  readonly baseUrl: string;
  private readonly eventSourceFactory?: (url: string) => EventSource;

  constructor(options: CrisaiClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? defaultBaseUrl).replace(/\/$/, "");
    this.eventSourceFactory = options.eventSourceFactory;
  }

  async startRun(request: UiRunRequest): Promise<UiRunState> {
    const response = await fetch(`${this.baseUrl}/api/v1/runs`, {
      method: "POST",
      headers: { "content-type": "application/json" },
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
    const response = await fetch(`${this.baseUrl}/api/v1/runs/${encodeURIComponent(runId)}`);
    return this.readJson(response);
  }

  async submitCheckpoint(runId: string, decision: CheckpointDecision): Promise<{ status: string; action: string }> {
    const response = await fetch(`${this.baseUrl}/api/v1/runs/${encodeURIComponent(runId)}/checkpoint`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        redirect_instruction: "",
        ...decision
      })
    });
    return this.readJson(response);
  }

  async getTheme(): Promise<UiTheme> {
    const response = await fetch(`${this.baseUrl}/api/v1/ui/theme`);
    return this.readJson(response);
  }

  async listSessions(): Promise<UiSessionState> {
    const response = await fetch(`${this.baseUrl}/api/v1/sessions`);
    return this.readJson(response);
  }

  async createSession(session: string): Promise<UiSessionState> {
    const response = await fetch(`${this.baseUrl}/api/v1/sessions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ session })
    });
    return this.readJson(response);
  }

  async getSession(session: string): Promise<UiSessionState> {
    const response = await fetch(`${this.baseUrl}/api/v1/sessions/${encodeURIComponent(session)}`);
    return this.readJson(response);
  }

  async getWorkspaceRoots(): Promise<UiWorkspaceRoots> {
    const response = await fetch(`${this.baseUrl}/api/v1/workspace/roots`);
    return this.readJson(response);
  }

  async getWorkspaceTree(rootName: string): Promise<UiWorkspaceTree> {
    const response = await fetch(`${this.baseUrl}/api/v1/workspace/tree/${encodeURIComponent(rootName)}`);
    return this.readJson(response);
  }

  async getWorkspaceFile(path: string): Promise<UiWorkspaceFile> {
    const query = new URLSearchParams({ path });
    const response = await fetch(`${this.baseUrl}/api/v1/workspace/file?${query.toString()}`);
    return this.readJson(response);
  }

  async saveWorkspaceFile(path: string, content: string): Promise<UiWorkspaceSaveResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/workspace/file`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path, content })
    });
    return this.readJson(response);
  }

  subscribe(runId: string, onEvent: (event: UiEvent) => void, onError?: (error: Event) => void): EventSource {
    const url = `${this.baseUrl}/api/v1/runs/${encodeURIComponent(runId)}/events`;
    const createEventSource = this.eventSourceFactory ?? ((target) => new EventSource(target));
    const source = createEventSource(url);
    const eventTypes: UiEventType[] = [
      "run_created",
      "routing_decision",
      "task_contract",
      "stage_started",
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

  private async readJson<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`crisAI runtime request failed (${response.status}): ${body}`);
    }
    return response.json() as Promise<T>;
  }
}
