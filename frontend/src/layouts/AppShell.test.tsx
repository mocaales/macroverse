import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  user: null as null | {
    uid: string;
    email: string;
    role: "admin" | "user";
    email_verified: boolean;
  }
}));
vi.mock("../features/auth/AuthProvider", () => ({ useAuth: () => ({ ...auth, loading: false, logout: vi.fn() }) }));
vi.mock("../features/auth/AuthDialog", () => ({
  AuthDialog: ({ open, onClose }: { open: boolean; onClose: () => void }) =>
    open ? <button onClick={onClose}>Close mocked dialog</button> : null
}));
const portfolioApi = vi.hoisted(() => ({ accounts: vi.fn() }));
vi.mock("../api/queries", () => ({ portfolioApi }));

import { AppShell } from "./AppShell";

function renderShell() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <QueryClientProvider client={client}>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<p>Dashboard content</p>} />
          </Route>
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe("AppShell", () => {
  beforeEach(() => {
    auth.user = null;
    portfolioApi.accounts.mockResolvedValue([]);
  });

  it("renders navigation and opens the account dialog", () => {
    renderShell();
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeInTheDocument();
    expect(screen.getByText("Dashboard content")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Sign in/ }));
    fireEvent.click(screen.getByRole("button", { name: "Close mocked dialog" }));
    expect(screen.queryByText("Close mocked dialog")).not.toBeInTheDocument();
  });

  it("shows the authenticated email without journal access before an account exists", async () => {
    auth.user = { uid: "u-1", email: "user@example.com", role: "user", email_verified: true };
    portfolioApi.accounts.mockResolvedValue([]);
    renderShell();
    expect(screen.getByText("user@example.com")).toBeInTheDocument();
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
    await screen.findByText("Dashboard content");
    expect(screen.queryByText("Journal")).not.toBeInTheDocument();
  });

  it("shows journal navigation when a trading account exists", async () => {
    auth.user = { uid: "u-1", email: "user@example.com", role: "user", email_verified: true };
    portfolioApi.accounts.mockResolvedValue([
      { name: "Broker", starting_balance: 100, type: "Trading Account", currency: "EUR" }
    ]);
    renderShell();
    expect(await screen.findByText("Journal")).toBeInTheDocument();
  });

  it("shows administration navigation only to the admin", () => {
    auth.user = {
      uid: "admin-uid",
      email: "admin@example.com",
      role: "admin",
      email_verified: false
    };
    renderShell();
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });
});
