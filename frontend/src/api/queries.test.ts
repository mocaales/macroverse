import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn()
}));

vi.mock("./client", () => ({ api }));

import { chartsApi, portfolioApi } from "./queries";

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
});
