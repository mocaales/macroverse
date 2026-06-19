import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn()
}));

vi.mock("./client", () => ({ api }));

import { adminApi, authApi, chartsApi, portfolioApi } from "./queries";

describe("API queries", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("passes optional account filters to portfolio requests", async () => {
    api.get.mockResolvedValueOnce({ data: [] });

    await portfolioApi.trades("Long Term");

    expect(api.get).toHaveBeenCalledWith("/portfolio/trades", {
      params: { account: "Long Term" }
    });
  });

  it("encodes account and chart path segments", async () => {
    api.get.mockResolvedValue({ data: {} });
    api.post.mockResolvedValue({ data: [] });

    await portfolioApi.dashboard("Crypto / Main");
    await chartsApi.toggleFavourite("Treasury spread / 10Y");

    expect(api.get).toHaveBeenCalledWith("/portfolio/dashboard/Crypto%20%2F%20Main");
    expect(api.post).toHaveBeenCalledWith("/charts/favourites/Treasury%20spread%20%2F%2010Y");
  });

  it("covers every portfolio and chart endpoint", async () => {
    api.get.mockResolvedValue({ data: [] });
    api.post.mockResolvedValue({ data: {} });
    api.put.mockResolvedValue({ data: {} });
    api.delete.mockResolvedValue({ data: { message: "deleted" } });

    await portfolioApi.accounts();
    await portfolioApi.createAccount({ name: "Main", type: "Trading Account", starting_balance: 0, currency: "EUR" });
    await portfolioApi.deleteAccount("Main / EUR");
    await portfolioApi.createTrade({ account: "Main", trade_time: "2026-01-01", action: "Trade", symbol: "BTC", pnl: 1 });
    await portfolioApi.updateTrade({ id: "t1", pnl: 2 });
    await portfolioApi.deleteTrade("t1");
    await portfolioApi.assets("Main");
    await portfolioApi.createAsset({ account: "Main", symbol: "BTC", quantity: 1, unit: "units", display_quantity: 1 });
    await portfolioApi.deleteAsset("a1");
    await portfolioApi.totalDashboard("EUR");
    await portfolioApi.journalSummary("Main / USD");
    await chartsApi.charts();
    await chartsApi.favourites();
    await chartsApi.series("yield curve");
    await authApi.me();
    await adminApi.users();
    await adminApi.deleteUser("user-1");

    expect(api.put).toHaveBeenCalledWith("/portfolio/trades/t1", { pnl: 2 });
    expect(api.delete).toHaveBeenCalledWith("/portfolio/accounts/Main%20%2F%20EUR");
    expect(api.get).toHaveBeenCalledWith("/portfolio/dashboard", { params: { currency: "EUR" } });
    expect(api.get).toHaveBeenCalledWith("/portfolio/journal/Main%20%2F%20USD/summary");
    expect(api.get).toHaveBeenCalledWith("/charts/yield curve/series");
    expect(api.delete).toHaveBeenCalledWith("/admin/users/user-1");
  });
});
