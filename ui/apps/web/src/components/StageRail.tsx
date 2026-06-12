import { type UiStageSummary } from "@crisai/contracts";

export function StageRail({ stages }: { stages: UiStageSummary[] }) {
  return (
    <aside className="stage-rail" aria-label="Workflow steps">
      <h2>Steps</h2>
      {stages.length === 0 ? <p>No steps yet.</p> : null}
      {stages.map((stage) => (
        <article key={stage.key} className={`stage stage-${stage.status}`}>
          <strong>{stage.label}</strong>
          <span className="stage-status">
            <span className="stage-status-dot" aria-hidden="true" />
            {stage.status}
          </span>
          {stage.summary ? <small>{stage.summary}</small> : null}
        </article>
      ))}
    </aside>
  );
}
