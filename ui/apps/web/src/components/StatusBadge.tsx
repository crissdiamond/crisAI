export function StatusBadge({ status }: { status: string }) {
  return (
    <div className={`status-badge status-badge--${status.replace(/_/g, "-")}`}>
      <span className="status-dot" aria-hidden="true" />
      <span>{status.replace(/_/g, " ")}</span>
    </div>
  );
}
