import { render, screen } from "@testing-library/react";
import { MemoryRouter, Outlet } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("./layouts/AppShell", () => ({ AppShell: () => <Outlet /> }));
vi.mock("./pages/DashboardPage", () => ({ DashboardPage: () => <p>Dashboard route</p> }));
vi.mock("./pages/JournalPage", () => ({ JournalPage: () => <p>Journal route</p> }));
vi.mock("./pages/ChartsPage", () => ({ ChartsPage: () => <p>Charts route</p> }));
vi.mock("./pages/AdminPage", () => ({ AdminPage: () => <p>Admin route</p> }));

import App from "./App";

describe("App routing", () => {
  it("redirects the legacy dashboard route", async () => {
    render(<MemoryRouter initialEntries={["/dashboard"]}><App /></MemoryRouter>);
    expect(await screen.findByText("Dashboard route")).toBeInTheDocument();
  });

  it("renders unknown routes through the not-found page", async () => {
    render(<MemoryRouter initialEntries={["/missing"]}><App /></MemoryRouter>);
    expect(await screen.findByText("Route not found")).toBeInTheDocument();
  });

  it("renders the admin route", async () => {
    render(<MemoryRouter initialEntries={["/admin"]}><App /></MemoryRouter>);
    expect(await screen.findByText("Admin route")).toBeInTheDocument();
  });
});
