import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
  accounts: vi.fn(), createAccount: vi.fn(), deleteAccount: vi.fn(), trades: vi.fn(), createTrade: vi.fn(),
  updateTrade: vi.fn(), deleteTrade: vi.fn(), assets: vi.fn(), createAsset: vi.fn(),
  deleteAsset: vi.fn(), dashboard: vi.fn(), totalDashboard: vi.fn(), journalSummary: vi.fn()
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
vi.mock("../components/BalanceLineChart", () => ({
  BalanceLineChart: () => <div data-testid="balance-chart">TradingView balance chart</div>
}));
vi.mock("../components/DailyPnlCalendar", () => ({
  DailyPnlCalendar: () => <div data-testid="daily-pnl-calendar">Daily P&L calendar</div>
}));
vi.mock("../components/MonthlyPerformanceChart", () => ({
  MonthlyPerformanceChart: ({ points }: { points: Array<{ month: string }> }) => (
    <div data-testid="monthly-performance-chart">{points.map((point) => point.month).join(",")}</div>
  )
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
    const summary = {
      currency: "EUR", account_type: "All Accounts", account_count: 0, balance: 0,
      realised_pnl: 0, total_entries: 0, trade_count: 0, winning_trades: 0,
      win_rate: 0, average_trade: 0, best_trade: 0, equity_curve: [], daily_pnl: []
    };
    portfolioApi.dashboard.mockResolvedValue(summary);
    portfolioApi.totalDashboard.mockResolvedValue(summary);
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
    portfolioApi.accounts.mockResolvedValue([{ name: "Trading", starting_balance: 1000, type: "Trading Account", currency: "USD" }]);
    portfolioApi.dashboard.mockResolvedValue({
      currency: "USD", account_type: "Trading Account", account_count: 1, balance: 1100,
      realised_pnl: 60, total_entries: 4, trade_count: 3, winning_trades: 1,
      win_rate: 33.3, average_trade: 20, best_trade: 100,
      equity_curve: [
        { date: "2025-12-01", balance: 1000 },
        { date: "2026-01-01", balance: 1200 },
        { date: "2026-01-15", balance: 900 },
        { date: "2026-01-31", balance: 1100 }
      ],
      daily_pnl: [
        { date: "2026-01-01", pnl: 100, trade_count: 1 },
        { date: "2026-01-02", pnl: -40, trade_count: 1 }
      ]
    });
    portfolioApi.trades.mockResolvedValue([
      {
        id: "trade-1",
        account: "Trading",
        trade_time: "2026-01-01T00:00:00Z",
        action: "Trade",
        type: "Long",
        symbol: "BTC",
        pnl: 100,
        notes: ""
      },
      {
        id: "trade-2", account: "Trading", trade_time: "2026-01-02T00:00:00Z",
        action: "Trade", type: "Short", symbol: "ETH", pnl: -40, notes: ""
      },
      {
        id: "trade-3", account: "Trading", trade_time: "2026-01-03T00:00:00Z",
        action: "Trade", type: "Long", symbol: "BTC", pnl: 0, notes: ""
      },
      {
        id: "cash-1", account: "Trading", trade_time: "2026-01-04T00:00:00Z",
        action: "Deposit", type: null, symbol: "CASH", pnl: 500, notes: ""
      }
    ]);
    portfolioApi.createTrade.mockResolvedValue({});
    portfolioApi.createAccount.mockResolvedValue({ name: "New", starting_balance: 0, type: "Trading Account", currency: "EUR" });
    renderPage(<DashboardPage />);
    await screen.findByRole("option", { name: "Trading · Trading Account" });
    fireEvent.change(screen.getByLabelText("Account"), { target: { value: "Trading" } });
    expect(await screen.findByText("Balance through time")).toBeInTheDocument();
    expect(await screen.findByTestId("balance-chart")).toBeInTheDocument();
    expect(screen.getByTestId("daily-pnl-calendar")).toBeInTheDocument();
    expect(await screen.findByText("Realized trading performance")).toBeInTheDocument();
    expect(screen.getByTestId("monthly-performance-chart")).toHaveTextContent("2026-01");
    const realisedPnlMetric = screen.getByText("Realized trade P&L").closest("article");
    expect(realisedPnlMetric).not.toBeNull();
    expect(realisedPnlMetric).toHaveTextContent("-$40.00");
    const performanceMetric = screen.getByText("Performance").closest("article");
    expect(performanceMetric).not.toBeNull();
    await waitFor(() => expect(performanceMetric).toHaveTextContent("+22.22%"));
    const monthlyRange = screen.getByLabelText("Monthly performance range");
    fireEvent.click(within(monthlyRange).getByRole("button", { name: "3M" }));
    expect(screen.getByText("What is driving performance")).toBeInTheDocument();
    expect(screen.getByLabelText("1 wins, 1 losses, 1 break-even")).toBeInTheDocument();
    expect(screen.getByText("2.50x")).toBeInTheDocument();
    expect(screen.getAllByText("ETH")).toHaveLength(2);
    expect(screen.queryByText("Ledger operations")).not.toBeInTheDocument();

    const performancePeriod = screen.getByLabelText("Performance period");
    fireEvent.click(within(performancePeriod).getByRole("button", { name: "All" }));
    expect(performanceMetric).toHaveTextContent("+10.00%");
    expect(realisedPnlMetric).toHaveTextContent("+$60.00");
    expect(screen.queryByText("Max drawdown")).not.toBeInTheDocument();
    fireEvent.click(within(performancePeriod).getByRole("button", { name: "7 Days" }));
    expect(performanceMetric).toHaveTextContent("+0.00%");
    expect(realisedPnlMetric).toHaveTextContent("$0.00");
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-01-01" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-01-31" } });
    expect(performanceMetric).toHaveTextContent("-8.33%");
    expect(realisedPnlMetric).toHaveTextContent("+$60.00");

    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:report") });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    const clickReport = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    fireEvent.click(screen.getByRole("button", { name: /Download report/ }));
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(clickReport).toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Symbol"), { target: { value: "btc" } });
    fireEvent.change(screen.getByLabelText("Realised P&L"), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit entry" }));
    await waitFor(() => expect(portfolioApi.createTrade).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /New account/ }));
    fireEvent.change(screen.getByLabelText("Account name"), { target: { value: "New" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(portfolioApi.createAccount).toHaveBeenCalled());
  });

  it("renders a total portfolio containing trading accounts", async () => {
    portfolioApi.accounts.mockResolvedValue([
      { name: "Primary", starting_balance: 500, type: "Trading Account", currency: "EUR" },
      { name: "Broker", starting_balance: 500, type: "Trading Account", currency: "EUR" }
    ]);
    portfolioApi.totalDashboard.mockResolvedValue({
      currency: "EUR", account_type: "All Accounts", account_count: 2, balance: 1000,
      realised_pnl: 0, total_entries: 0, trade_count: 0, winning_trades: 0,
      win_rate: 0, average_trade: 0, best_trade: 0,
      equity_curve: [{ date: "2026-01-01", balance: 1000 }],
      daily_pnl: [],
      accounts: [
        { name: "Primary", type: "Trading Account", currency: "EUR", balance: 600 },
        { name: "Broker", type: "Trading Account", currency: "EUR", balance: 400 }
      ]
    });
    portfolioApi.dashboard.mockResolvedValue({
      currency: "EUR", account_type: "Trading Account", account_count: 1, balance: 600,
      realised_pnl: 100, total_entries: 1, trade_count: 1, winning_trades: 1,
      win_rate: 100, average_trade: 100, best_trade: 100,
      equity_curve: [{ date: "2026-01-01", balance: 600 }],
      daily_pnl: [{ date: "2026-01-01", pnl: 100, trade_count: 1 }]
    });
    portfolioApi.trades.mockResolvedValue([{
      id: "c1", account: "Primary", trade_time: "2026-01-01", action: "Trade",
      type: "Long", symbol: "BTC", pnl: 100, notes: ""
    }]);
    renderPage(<DashboardPage />);
    expect(await screen.findByText("Total balance through time")).toBeInTheDocument();
    expect(screen.queryByLabelText("Currency")).not.toBeInTheDocument();
    expect(screen.getByText("Broker")).toBeInTheDocument();
    expect(screen.getByText("€600.00")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Account"), { target: { value: "Primary" } });
    expect(await screen.findByText("Realized trading performance")).toBeInTheDocument();
  });

  it("confirms account deletion from the portfolio list", async () => {
    portfolioApi.accounts.mockResolvedValue([
      { name: "Emergency", starting_balance: 500, type: "Trading Account", currency: "EUR" }
    ]);
    portfolioApi.totalDashboard.mockResolvedValue({
      currency: "EUR", account_type: "All Accounts", account_count: 1, balance: 500,
      realised_pnl: 0, total_entries: 0, trade_count: 0, winning_trades: 0,
      win_rate: 0, average_trade: 0, best_trade: 0, equity_curve: [], daily_pnl: []
    });
    portfolioApi.deleteAccount.mockResolvedValue({ message: "deleted" });

    renderPage(<DashboardPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Delete Emergency" }));
    expect(screen.getByRole("dialog", { name: "Emergency" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Delete Emergency" }));
    fireEvent.click(screen.getByRole("button", { name: "Close delete account dialog" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Delete Emergency" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete account" }));

    await waitFor(() => expect(portfolioApi.deleteAccount).toHaveBeenCalledWith("Emergency", expect.anything()));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("filters, edits, and deletes journal entries", async () => {
    portfolioApi.accounts.mockResolvedValue([{ name: "Trading", starting_balance: 1000, type: "Trading Account", currency: "USD" }]);
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

  it("blocks the journal when no trading account exists", async () => {
    portfolioApi.accounts.mockResolvedValue([]);

    renderPage(<JournalPage />);

    expect(await screen.findByText("Trading account required")).toBeInTheDocument();
    expect(portfolioApi.trades).not.toHaveBeenCalled();
    expect(portfolioApi.journalSummary).not.toHaveBeenCalled();
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
