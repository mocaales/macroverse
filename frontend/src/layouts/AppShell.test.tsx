import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({ user: null as null | { uid: string; email: string } }));
vi.mock("../features/auth/AuthProvider", () => ({ useAuth: () => ({ ...auth, loading: false, logout: vi.fn() }) }));
vi.mock("../features/auth/AuthDialog", () => ({
  AuthDialog: ({ open, onClose }: { open: boolean; onClose: () => void }) =>
    open ? <button onClick={onClose}>Close mocked dialog</button> : null
}));

import { AppShell } from "./AppShell";

function renderShell() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<p>Dashboard content</p>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe("AppShell", () => {
  it("renders navigation and opens the account dialog", () => {
    renderShell();
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeInTheDocument();
    expect(screen.getByText("Dashboard content")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Sign in/ }));
    fireEvent.click(screen.getByRole("button", { name: "Close mocked dialog" }));
    expect(screen.queryByText("Close mocked dialog")).not.toBeInTheDocument();
  });

  it("shows the authenticated email", () => {
    auth.user = { uid: "u-1", email: "user@example.com" };
    renderShell();
    expect(screen.getByText("user@example.com")).toBeInTheDocument();
  });
});
