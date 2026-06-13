import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, BookOpen, ChartNoAxesCombined, CircleUserRound, ShieldCheck } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { portfolioApi } from "../api/queries";
import { AuthDialog } from "../features/auth/AuthDialog";
import { useAuth } from "../features/auth/AuthProvider";

export function AppShell() {
  const [authOpen, setAuthOpen] = useState(false);
  const { user } = useAuth();
  const accounts = useQuery({
    queryKey: ["accounts"],
    queryFn: portfolioApi.accounts,
    enabled: Boolean(user)
  });
  const hasTradingAccount = accounts.data?.some((account) => account.type === "Trading Account") ?? false;

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
          {hasTradingAccount && (
            <NavLink to="/journal">
              <BookOpen size={16} /> Journal
            </NavLink>
          )}
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
