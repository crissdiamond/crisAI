import { type UiStageSummary } from "@crisai/contracts";

export function StageRail({
  stages,
  selectedStage,
  activeStage,
  onSelectStage
}: {
  stages: UiStageSummary[];
  selectedStage: string | null;
  activeStage: string | null;
  onSelectStage: (key: string) => void;
}) {
  return (
    <aside className="stage-rail" aria-label="Workflow steps">
      <h2>Steps</h2>
      {stages.length === 0 ? <p className="stage-empty">No steps yet.</p> : null}
      {stages.map((stage) => {
        const isSelected = selectedStage === stage.key;
        const isActive = activeStage === stage.key;
        // The button shows a fixed label + status only — never the streaming
        // output — so it keeps a constant size while an agent is producing text.
        return (
          <button
            key={stage.key}
            type="button"
            className={
              `stage stage-${stage.status}` +
              (isSelected ? " stage-selected" : "") +
              (isActive ? " stage-active" : "")
            }
            aria-pressed={isSelected}
            aria-current={isActive ? "step" : undefined}
            onClick={() => onSelectStage(stage.key)}
          >
            <strong>{stage.label}</strong>
            <span className="stage-status">
              <span className="stage-status-dot" aria-hidden="true" />
              {isActive && stage.status !== "complete" ? "live" : stage.status}
            </span>
          </button>
        );
      })}
    </aside>
  );
}
