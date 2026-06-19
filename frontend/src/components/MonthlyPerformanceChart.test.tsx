import { act } from "react";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const applyOptions = vi.fn();
  const fitContent = vi.fn();
  const remove = vi.fn();
  const setData = vi.fn();
  const subscribeCrosshairMove = vi.fn();
  const addSeries = vi.fn((...args: unknown[]) => {
    void args;
    return { setData };
  });
  const createChart = vi.fn((...args: unknown[]) => {
    void args;
    return {
      addSeries,
      applyOptions,
      remove,
      subscribeCrosshairMove,
      timeScale: () => ({ fitContent })
    };
  });
  return { addSeries, applyOptions, createChart, fitContent, remove, setData, subscribeCrosshairMove };
});

vi.mock("lightweight-charts", () => ({
  ColorType: { Solid: "solid" },
  createChart: mocks.createChart,
  CrosshairMode: { Normal: 0 },
  HistogramSeries: "HistogramSeries",
  LineStyle: { Dashed: 2 }
}));

class ResizeObserverMock {
  static instances: ResizeObserverMock[] = [];
  callback: ResizeObserverCallback;
  disconnect = vi.fn();
  observe = vi.fn();

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
    ResizeObserverMock.instances.push(this);
  }
}

vi.stubGlobal("ResizeObserver", ResizeObserverMock);

import { MonthlyPerformanceChart } from "./MonthlyPerformanceChart";

const points = [
  { month: "2026-01", trades: 4, value: 10 },
  { month: "2026-02", trades: 1, value: -5.25 }
];

interface ChartOptionsUnderTest {
  localization: { priceFormatter: (value: number) => string };
  timeScale: { tickMarkFormatter: (time: unknown) => string };
}

interface SeriesOptionsUnderTest {
  priceFormat: { formatter: (value: number) => string };
}

describe("MonthlyPerformanceChart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    ResizeObserverMock.instances = [];
  });

  it("renders percentage histogram data and hover details", () => {
    render(<MonthlyPerformanceChart currency="USD" points={points} />);

    expect(mocks.createChart).toHaveBeenCalled();
    expect(mocks.addSeries).toHaveBeenCalledWith("HistogramSeries", expect.objectContaining({ base: 0 }));
    expect(mocks.setData).toHaveBeenCalledWith([
      expect.objectContaining({ time: "2026-01-01", value: 10 }),
      expect.objectContaining({ time: "2026-02-01", value: -5.25 })
    ]);
    expect(mocks.fitContent).toHaveBeenCalled();
    const chartOptions = mocks.createChart.mock.calls[0][1] as ChartOptionsUnderTest;
    const seriesOptions = mocks.addSeries.mock.calls[0][1] as SeriesOptionsUnderTest;
    expect(chartOptions.localization.priceFormatter(5)).toBe("$5");
    expect(chartOptions.localization.priceFormatter(-5)).toBe("-$5");
    expect(chartOptions.timeScale.tickMarkFormatter("2026-02-01")).toBe("Feb");
    expect(chartOptions.timeScale.tickMarkFormatter({ month: 2, year: 2026 })).toBe("");
    expect(seriesOptions.priceFormat.formatter(2.345)).toBe("$2.35");
    expect(seriesOptions.priceFormat.formatter(-2.345)).toBe("-$2.35");

    const chart = screen.getByTestId("monthly-performance-chart");
    Object.defineProperty(chart, "clientHeight", { configurable: true, value: 330 });
    Object.defineProperty(chart, "clientWidth", { configurable: true, value: 800 });
    const series = mocks.addSeries.mock.results[0].value;
    const crosshairHandler = mocks.subscribeCrosshairMove.mock.calls[0][0];
    act(() => crosshairHandler({
      point: { x: 300, y: 100 },
      seriesData: new Map([[series, { time: "2026-02-01", value: -5.25 }]]),
      time: "2026-02-01"
    }));

    expect(screen.getByText("February 2026")).toBeInTheDocument();
    expect(screen.getByText("-$5.25")).toBeInTheDocument();
    expect(screen.getByText("1 closed trade")).toBeInTheDocument();
  });

  it("handles crosshair exit, resizing, empty data, and cleanup", () => {
    const view = render(<MonthlyPerformanceChart currency="EUR" points={points} />);
    const crosshairHandler = mocks.subscribeCrosshairMove.mock.calls[0][0];
    act(() => crosshairHandler({ point: undefined, seriesData: new Map(), time: undefined }));
    const series = mocks.addSeries.mock.results[0].value;
    act(() => crosshairHandler({
      point: { x: 20, y: 20 },
      seriesData: new Map([[series, { time: "2026-03-01", value: 2 }]]),
      time: "2026-03-01"
    }));
    ResizeObserverMock.instances[0].callback([
      { contentRect: { height: 280, width: 620 } } as ResizeObserverEntry
    ], ResizeObserverMock.instances[0] as unknown as ResizeObserver);
    expect(mocks.applyOptions).toHaveBeenCalledWith({ height: 280, width: 620 });
    view.unmount();
    expect(mocks.remove).toHaveBeenCalled();
    expect(ResizeObserverMock.instances[0].disconnect).toHaveBeenCalled();

    mocks.createChart.mockClear();
    render(<MonthlyPerformanceChart currency="EUR" points={[]} />);
    expect(mocks.createChart).not.toHaveBeenCalled();
  });
});
