import { type UiStageSummary } from "@crisai/contracts";

export function StageRail({
  stages,
  selectedStage,
  onSelectStage
}: {
  stages: UiStageSummary[];
  selectedStage: string | null;
  onSelectStage: (key: string) => void;
}) {
  return (
    <aside className="stage-rail" aria-label="Workflow steps">
      <h2>Steps</h2>
      {stages.length === 0 ? <p className="stage-empty">No steps yet.</p> : null}
      {stages.map((stage) => (
        <button
          key={stage.key}
          type="button"
          className={`stage stage-${stage.status}${selectedStage === stage.key ? " stage-selected" : ""}`}
          aria-pressed={selectedStage === stage.key}
          onClick={() => onSelectStage(stage.key)}
        >
          <strong>{stage.label}</strong>
          <span className="stage-status">
            <span className="stage-status-dot" aria-hidden="true" />
            {stage.status}
          </span>
          {stage.summary ? <small>{stage.summary}</small> : null}
        </button>
      ))}
    </aside>
  );
}
