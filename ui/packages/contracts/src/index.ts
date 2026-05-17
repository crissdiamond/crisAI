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
  expected_stages: Array<Record<string, unknown>>;
  events: UiEvent[];
  final_output: string;
  error: string;
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

const defaultBaseUrl = "http://127.0.0.1:8000";

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
