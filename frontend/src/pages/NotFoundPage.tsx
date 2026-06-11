import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="empty-state">
      <p className="eyebrow">404</p>
      <h1>Route not found</h1>
      <Link className="button primary" to="/">
        Return to dashboard
      </Link>
    </div>
  );
}
