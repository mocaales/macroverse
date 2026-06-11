interface EmptyStateProps {
  readonly title: string;
  readonly body: string;
}

export function EmptyState({ title, body }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <span className="status-dot" />
      <h2>{title}</h2>
      <p>{body}</p>
    </div>
  );
}
