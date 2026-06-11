export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-state">
      <span className="status-dot" />
      <h2>{title}</h2>
      <p>{body}</p>
    </div>
  );
}
