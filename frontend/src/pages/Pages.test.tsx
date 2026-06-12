import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  user: {
    uid: "u-1",
    email: "user@example.com",
    role: "user" as "admin" | "user",
    email_verified: true
  },
  loading: false,
  logout: vi.fn()
}));
const portfolioApi = vi.hoisted(() => ({
  accounts: vi.fn(), createAccount: vi.fn(), trades: vi.fn(), createTrade: vi.fn(),
  updateTrade: vi.fn(), deleteTrade: vi.fn(), assets: vi.fn(), createAsset: vi.fn(),
  deleteAsset: vi.fn(), dashboard: vi.fn(), journalSummary: vi.fn()
}));
const chartsApi = vi.hoisted(() => ({
  charts: vi.fn(), favourites: vi.fn(), toggleFavourite: vi.fn(), series: vi.fn()
}));

vi.mock("../features/auth/AuthProvider", () => ({ useAuth: () => auth }));
vi.mock("../api/queries", () => ({ portfolioApi, chartsApi }));
vi.mock("../api/client", () => ({ getApiError: () => "Request failed." }));
vi.mock("../components/Plot", () => ({
  Plot: ({ data }: { data: Array<{ name?: string }> }) => <div data-testid="plot">{data.map((item) => item.name).join(",")}</div>
}));
vi.mock("../components/YearToDateRoiChart", () => ({
  YearToDateRoiChart: () => <div data-testid="ytd-chart">Professional YTD chart</div>
}));

import { ChartsPage } from "./ChartsPage";
import { DashboardPage } from "./DashboardPage";
import { JournalPage } from "./JournalPage";
import { NotFoundPage } from "./NotFoundPage";

function renderPage(element: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<MemoryRouter><QueryClientProvider client={client}>{element}</QueryClientProvider></MemoryRouter>);
}

describe("application pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    auth.user = { uid: "u-1", email: "user@example.com", role: "user", email_verified: true };
    portfolioApi.accounts.mockResolvedValue([]);
    portfolioApi.trades.mockResolvedValue([]);
    portfolioApi.assets.mockResolvedValue([]);
    portfolioApi.dashboard.mockResolvedValue({ balance: 0, realised_pnl: 0, trade_count: 0, winning_trades: 0, win_rate: 0, average_trade: 0, best_trade: 0, equity_curve: [] });
    portfolioApi.journalSummary.mockResolvedValue({ total_entries: 0, trade_count: 0, realised_pnl: 0, win_rate: 0, average_trade: 0 });
    chartsApi.charts.mockResolvedValue([]);
    chartsApi.favourites.mockResolvedValue([]);
    chartsApi.series.mockResolvedValue([]);
  });

  it("filters charts, opens available data, and toggles favourites", async () => {
    chartsApi.charts.mockResolvedValue([
      { name: "Bitcoin ROI", slug: "year_to_date_roi", category: "Crypto", quick: ["Growth"], assets: ["BTC"], summary: "Annual returns", available: true },
      { name: "Yield Curve", slug: "yield", category: "Macro", quick: ["Rates"], assets: [], summary: "Treasury rates", available: false }
    ]);
    chartsApi.series.mockResolvedValue([{ name: "BTC", points: [{ date: "2025-01-01", value: 100 }, { date: "2025-02-01", value: 110 }] }]);
    chartsApi.toggleFavourite.mockResolvedValue(["Bitcoin ROI"]);
    renderPage(<ChartsPage />);
    expect(await screen.findByText("Bitcoin ROI")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Search charts"), { target: { value: "yield" } });
    expect(screen.queryByText("Bitcoin ROI")).not.toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Search charts"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Crypto" }));
    fireEvent.click(screen.getByText("Bitcoin ROI"));
    expect(await screen.findByTestId("ytd-chart")).toHaveTextContent("Professional YTD chart");
    fireEvent.click(screen.getByRole("button", { name: "" }));
    await waitFor(() => expect(chartsApi.toggleFavourite).toHaveBeenCalledWith("Bitcoin ROI", expect.anything()));
    fireEvent.click(screen.getByText("Back to charts"));
  });

  it("shows unavailable chart migration state", async () => {
    chartsApi.charts.mockResolvedValue([
      { name: "Yield Curve", slug: "yield", category: "Macro", quick: ["Rates"], assets: [], summary: "Treasury rates", available: false }
    ]);
    renderPage(<ChartsPage />);
    fireEvent.click(await screen.findByText("Yield Curve"));
    expect(screen.getByText("Chart is being migrated")).toBeInTheDocument();
  });

  it("supports dashboard trading and account creation", async () => {
    portfolioApi.accounts.mockResolvedValue([{ name: "Trading", starting_balance: 1000, type: "Trading" }]);
    portfolioApi.dashboard.mockResolvedValue({ balance: 1100, realised_pnl: 100, trade_count: 1, winning_trades: 1, win_rate: 100, average_trade: 100, best_trade: 100, equity_curve: [{ date: "2026-01-01", balance: 1100 }] });
    portfolioApi.createTrade.mockResolvedValue({});
    portfolioApi.createAccount.mockResolvedValue({ name: "New", starting_balance: 0, type: "Trading" });
    renderPage(<DashboardPage />);
    expect(await screen.findByText("Balance through time")).toBeInTheDocument();
    expect(await screen.findByTestId("plot")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /New account/ }));
    fireEvent.change(screen.getByLabelText("Account name"), { target: { value: "New" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(portfolioApi.createAccount).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText("Symbol"), { target: { value: "btc" } });
    fireEvent.change(screen.getByLabelText("Realised P&L"), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit entry" }));
    await waitFor(() => expect(portfolioApi.createTrade).toHaveBeenCalled());
  });

  it("renders investing assets and overall accounts", async () => {
    portfolioApi.accounts.mockResolvedValue([{ name: "Invest", starting_balance: 1, type: "Investing" }]);
    portfolioApi.assets.mockResolvedValue([{ id: "a1", account: "Invest", symbol: "BTC", quantity: 1, display_quantity: 1, unit: "units" }]);
    portfolioApi.createAsset.mockResolvedValue({});
    portfolioApi.deleteAsset.mockResolvedValue({});
    const view = renderPage(<DashboardPage />);
    expect(await screen.findByText("1 open positions")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Ticker symbol"), { target: { value: "eth" } });
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Add asset" }));
    await waitFor(() => expect(portfolioApi.createAsset).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "" }));
    await waitFor(() => expect(portfolioApi.deleteAsset).toHaveBeenCalledWith("a1", expect.anything()));

    view.unmount();
    portfolioApi.accounts.mockResolvedValue([{ name: "All", starting_balance: 0, type: "Overall" }, { name: "Broker", starting_balance: 500, type: "Trading" }]);
    renderPage(<DashboardPage />);
    expect(await screen.findByText("All portfolio accounts")).toBeInTheDocument();
    expect(screen.getByText("Broker")).toBeInTheDocument();
  });

  it("filters, edits, and deletes journal entries", async () => {
    portfolioApi.accounts.mockResolvedValue([{ name: "Trading", starting_balance: 1000, type: "Trading" }]);
    portfolioApi.trades.mockResolvedValue([
      { id: "t1", account: "Trading", trade_time: "2026-01-02", action: "Trade", type: "Long", symbol: "BTC", pnl: 50, notes: "" },
      { id: "t2", account: "Trading", trade_time: "2026-01-01", action: "Trade", type: "Short", symbol: "ETH", pnl: -20, notes: "" }
    ]);
    portfolioApi.updateTrade.mockResolvedValue({});
    portfolioApi.deleteTrade.mockResolvedValue({});
    renderPage(<JournalPage />);
    expect(await screen.findByText("2 ledger entries")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Search symbol"), { target: { value: "eth" } });
    expect(screen.getByText("1 ledger entries")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Search symbol"), { target: { value: "" } });
    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[2], { target: { value: "loss" } });
    expect(screen.getByText("1 ledger entries")).toBeInTheDocument();
    fireEvent.change(selects[2], { target: { value: "All" } });
    fireEvent.change(selects[3], { target: { value: "oldest" } });

    const buttons = screen.getAllByRole("button", { name: "" });
    fireEvent.click(buttons[0]);
    fireEvent.change(screen.getByLabelText("Date"), { target: { value: "2026-02-01" } });
    fireEvent.change(screen.getByLabelText("Direction"), { target: { value: "Short" } });
    fireEvent.change(screen.getByLabelText("Symbol"), { target: { value: "sol" } });
    fireEvent.change(screen.getByLabelText("P&L"), { target: { value: "35" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(portfolioApi.updateTrade).toHaveBeenCalled());
    fireEvent.click(screen.getAllByRole("button", { name: "" })[1]);
    await waitFor(() => expect(portfolioApi.deleteTrade).toHaveBeenCalled());
  });

  it("requires authentication and renders the not-found route", () => {
    auth.user = null as never;
    const view = renderPage(<DashboardPage />);
    expect(screen.getByText("Authentication required")).toBeInTheDocument();
    view.unmount();
    renderPage(<NotFoundPage />);
    expect(screen.getByText("Route not found")).toBeInTheDocument();
  });
});
