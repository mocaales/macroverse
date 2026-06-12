import { useState } from "react";
import { BarChart3, BookOpen, ChartNoAxesCombined, CircleUserRound, ShieldCheck } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { AuthDialog } from "../features/auth/AuthDialog";
import { useAuth } from "../features/auth/AuthProvider";

export function AppShell() {
  const [authOpen, setAuthOpen] = useState(false);
  const { user } = useAuth();

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to="/" className="brand">
          <span className="brand-mark">M</span>
          <span>Macroverse</span>
        </NavLink>
        <nav aria-label="Main navigation">
          <NavLink to="/" end>
            <BarChart3 size={16} /> Dashboard
          </NavLink>
          <NavLink to="/journal">
            <BookOpen size={16} /> Journal
          </NavLink>
          <NavLink to="/charts">
            <ChartNoAxesCombined size={16} /> Charts
          </NavLink>
          {user?.role === "admin" && (
            <NavLink to="/admin">
              <ShieldCheck size={16} /> Admin
            </NavLink>
          )}
        </nav>
        <button className="profile-button" onClick={() => setAuthOpen(true)}>
          <CircleUserRound size={18} />
          <span>{user?.email || "Sign in"}</span>
        </button>
      </header>
      <main className="workspace">
        <Outlet />
      </main>
      <AuthDialog open={authOpen} onClose={() => setAuthOpen(false)} />
    </div>
  );
}
