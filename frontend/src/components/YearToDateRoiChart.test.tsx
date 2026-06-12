import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const setData = vi.fn();
  const fitContent = vi.fn();
  const setVisibleLogicalRange = vi.fn();
  const remove = vi.fn();
  const addSeries = vi.fn(() => ({
    setData,
    applyOptions: vi.fn(),
    createPriceLine: vi.fn()
  }));
  const createChart = vi.fn(() => ({
    addSeries,
    applyOptions: vi.fn(),
    priceScale: () => ({ applyOptions: vi.fn() }),
    remove,
    subscribeCrosshairMove: vi.fn(),
    unsubscribeCrosshairMove: vi.fn(),
    timeScale: () => ({
      fitContent,
      getVisibleLogicalRange: () => ({ from: 0, to: 364 }),
      setVisibleLogicalRange
    })
  }));
  return { addSeries, createChart, fitContent, remove, setData, setVisibleLogicalRange };
});

vi.mock("lightweight-charts", () => ({
  ColorType: { Solid: "solid" },
  createChart: mocks.createChart,
  CrosshairMode: { Normal: 0 },
  LineSeries: "LineSeries",
  LineStyle: { Dashed: 2, Solid: 0 },
  PriceScaleMode: { Logarithmic: 1 }
}));

class ResizeObserverMock {
  observe = vi.fn();
  disconnect = vi.fn();
}

vi.stubGlobal("ResizeObserver", ResizeObserverMock);

import { buildAnnualRoiSeries, presidentialCycle } from "../features/charts/ytdRoi";
import { YearToDateRoiChart } from "./YearToDateRoiChart";

const series = [{
  name: "BTC / USD",
  points: [
    { date: "2022-01-01", value: 30_000 },
    { date: "2022-06-01", value: 24_000 },
    { date: "2023-01-01", value: 16_000 },
    { date: "2023-06-01", value: 25_600 },
    { date: "2024-01-01", value: 40_000 },
    { date: "2024-02-29", value: 50_000 },
    { date: "2024-03-01", value: 60_000 },
    { date: "2025-01-01", value: 50_000 },
    { date: "2025-06-01", value: 75_000 },
    { date: "2026-01-01", value: 60_000 },
    { date: "2026-06-01", value: 54_000 }
  ]
}];

describe("YearToDateRoiChart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("normalizes each year to its first close and removes leap day", () => {
    const annual = buildAnnualRoiSeries(series);

    expect(annual.map((item) => item.year)).toEqual([2022, 2023, 2024, 2025, 2026]);
    expect(annual[2].points).toHaveLength(2);
    expect(annual[2].points[1]).toMatchObject({ day: 59, roi: 50 });
    expect(annual[3].points.at(-1)?.roi).toBe(50);
    expect(annual[4].points.at(-1)?.roi).toBeCloseTo(-10);
    expect(presidentialCycle(2024)).toBe("election");
    expect(presidentialCycle(2025)).toBe("post-election");
    expect(presidentialCycle(2026)).toBe("midterm");
    expect(presidentialCycle(2027)).toBe("pre-election");
  });

  it("renders a financial chart with compact comparison controls", () => {
    render(<YearToDateRoiChart series={series} />);

    expect(screen.getByText("$54,000")).toBeInTheDocument();
    expect(screen.getAllByText("-10.00%").length).toBeGreaterThan(0);
    expect(screen.getByTestId("ytd-chart")).toBeInTheDocument();
    expect(mocks.createChart).toHaveBeenCalled();
    expect(mocks.setData).toHaveBeenCalled();
    expect(mocks.setData.mock.calls.flat().flat()).toEqual(expect.arrayContaining([
      expect.objectContaining({ value: 100 })
    ]));
    expect(screen.getByText("LOG")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Charts by TradingView" })).toBeInTheDocument();
  });

  it("supports range, cycle filters, line selection, average overlays, and reset actions", () => {
    render(<YearToDateRoiChart series={series} />);

    fireEvent.click(screen.getByRole("button", { name: "All years" }));
    const visibleYears = within(screen.getByLabelText("Visible years"));
    expect(visibleYears.getByRole("button", { name: /2022/ })).toBeInTheDocument();

    fireEvent.click(visibleYears.getByRole("button", { name: /2025/ }));
    expect(visibleYears.getByRole("button", { name: /2025/ })).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(screen.getByRole("button", { name: "Midterm" }));
    expect(screen.getByText("2 years")).toBeInTheDocument();
    expect(visibleYears.queryByRole("button", { name: /2025/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Add average/ }));
    fireEvent.click(screen.getByRole("button", { name: /Midterm years/ }));
    expect(screen.getByRole("button", { name: /Midterm years/ })).toHaveAttribute("aria-pressed", "true");

    const include2026 = screen.getByRole("button", { name: "Include 2026 in custom average" });
    fireEvent.click(include2026);
    expect(include2026).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: /Focus current/ }));
    expect(visibleYears.getByRole("button", { name: /2026/ })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: /Reset/ }));
    expect(screen.getByRole("button", { name: "All cycles" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Add average/ })).toHaveTextContent("1");
    expect(mocks.fitContent).toHaveBeenCalled();
  });
});
