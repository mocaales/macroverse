import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const setData = vi.fn();
  const fitContent = vi.fn();
  const setVisibleLogicalRange = vi.fn();
  const chartApplyOptions = vi.fn();
  const chartRemove = vi.fn();
  const priceScaleApplyOptions = vi.fn();
  const seriesApplyOptions = vi.fn();
  const getVisibleLogicalRange = vi.fn(() => ({ from: 0, to: 30 }));
  const addSeries = vi.fn((...args: unknown[]) => {
    void args;
    return {
      applyOptions: seriesApplyOptions,
      setData
    };
  });
  const createChart = vi.fn((...args: unknown[]) => {
    void args;
    return {
      addSeries,
      applyOptions: chartApplyOptions,
      priceScale: () => ({ applyOptions: priceScaleApplyOptions }),
      remove: chartRemove,
      timeScale: () => ({
        fitContent,
        getVisibleLogicalRange,
        setVisibleLogicalRange
      })
    };
  });
  return {
    addSeries,
    chartApplyOptions,
    chartRemove,
    createChart,
    fitContent,
    getVisibleLogicalRange,
    priceScaleApplyOptions,
    seriesApplyOptions,
    setData,
    setVisibleLogicalRange
  };
});

vi.mock("lightweight-charts", () => ({
  ColorType: { Solid: "solid" },
  createChart: mocks.createChart,
  CrosshairMode: { Normal: 0 },
  LineSeries: "LineSeries",
  LineStyle: { Dashed: 2, Solid: 0 }
}));

class ResizeObserverMock {
  static instances: ResizeObserverMock[] = [];
  callback: ResizeObserverCallback;
  observe = vi.fn();
  disconnect = vi.fn();

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
    ResizeObserverMock.instances.push(this);
  }
}

vi.stubGlobal("ResizeObserver", ResizeObserverMock);

import { BalanceLineChart } from "./BalanceLineChart";

interface ChartOptionsUnderTest {
  localization: {
    priceFormatter: (value: number) => string;
  };
  timeScale: {
    tickMarkFormatter: (time: unknown) => string;
  };
}

interface SeriesOptionsUnderTest {
  color: string;
  priceFormat: {
    formatter: (value: number) => string;
  };
}

describe("BalanceLineChart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    ResizeObserverMock.instances = [];
  });

  it("renders a lightweight balance chart and expands single-point data", () => {
    render(<BalanceLineChart currency="EUR" points={[{ date: "2026-06-13T00:00:00Z", balance: 10 }]} />);

    expect(screen.getByTestId("balance-chart")).toBeInTheDocument();
    expect(mocks.createChart).toHaveBeenCalled();
    expect(mocks.addSeries).toHaveBeenCalled();
    expect(mocks.setData).toHaveBeenCalledWith([
      { time: "2026-06-13", value: 10 },
      { time: "2026-06-14", value: 10 }
    ]);
    expect(mocks.fitContent).toHaveBeenCalled();
  });

  it("does not create a chart without balance data", () => {
    render(<BalanceLineChart currency="EUR" points={[]} />);

    expect(screen.getByTestId("balance-chart")).toBeInTheDocument();
    expect(mocks.createChart).not.toHaveBeenCalled();
  });

  it("formats axis labels and negative balances for the active currency", () => {
    render(<BalanceLineChart currency="USD" points={[
      { date: "2026-06-13T21:59:58.038Z", balance: -1_250.5 },
      { date: "2026-06-14T00:00:00Z", balance: -900 }
    ]} />);

    const chartOptions = mocks.createChart.mock.calls[0][1] as ChartOptionsUnderTest;
    const seriesOptions = mocks.addSeries.mock.calls[0][1] as SeriesOptionsUnderTest;
    expect(chartOptions.localization.priceFormatter(1250)).toBe("$1,250");
    expect(chartOptions.timeScale.tickMarkFormatter("2026-06-13")).toBe("Jun 13");
    expect(chartOptions.timeScale.tickMarkFormatter({ year: 2026, month: 6, day: 13 })).toBe("");
    expect(seriesOptions.color).toBe("#ff5c72");
    expect(seriesOptions.priceFormat.formatter(-12.34)).toBe("-$12.34");
    expect(mocks.setData).toHaveBeenCalledWith([
      { time: "2026-06-13", value: -1250.5 },
      { time: "2026-06-14", value: -900 }
    ]);
  });

  it("resizes with the container observer", () => {
    render(<BalanceLineChart currency="EUR" points={[
      { date: "2026-06-13T00:00:00Z", balance: 10 },
      { date: "2026-06-14T00:00:00Z", balance: 15 }
    ]} />);

    ResizeObserverMock.instances[0].callback([
      { contentRect: { width: 720 } } as ResizeObserverEntry
    ], ResizeObserverMock.instances[0] as unknown as ResizeObserver);
    ResizeObserverMock.instances[0].callback([
      { contentRect: { width: 0 } } as ResizeObserverEntry
    ], ResizeObserverMock.instances[0] as unknown as ResizeObserver);

    expect(mocks.chartApplyOptions).toHaveBeenCalledWith({ width: 720 });
    expect(mocks.chartApplyOptions).toHaveBeenCalledTimes(1);
  });

  it("contains wheel zoom inside the chart surface", async () => {
    render(<BalanceLineChart currency="EUR" points={[
      { date: "2026-06-13T00:00:00Z", balance: 10 },
      { date: "2026-06-14T00:00:00Z", balance: 15 }
    ]} />);

    const chart = screen.getByTestId("balance-chart");
    vi.spyOn(chart, "getBoundingClientRect").mockReturnValue({
      bottom: 390,
      height: 390,
      left: 0,
      right: 800,
      top: 0,
      width: 800,
      x: 0,
      y: 0,
      toJSON: () => ({})
    });
    fireEvent.wheel(chart, { clientX: 400, clientY: 190, deltaY: 90 });

    await waitFor(() => expect(mocks.setVisibleLogicalRange).toHaveBeenCalled());
  });

  it("supports axis-specific zoom and double-click reset", async () => {
    render(<BalanceLineChart currency="EUR" points={[
      { date: "2026-06-13T00:00:00Z", balance: 10 },
      { date: "2026-06-14T00:00:00Z", balance: 15 }
    ]} />);

    const chart = screen.getByTestId("balance-chart");
    vi.spyOn(chart, "getBoundingClientRect").mockReturnValue({
      bottom: 390,
      height: 390,
      left: 0,
      right: 800,
      top: 0,
      width: 800,
      x: 0,
      y: 0,
      toJSON: () => ({})
    });
    fireEvent.wheel(chart, { clientX: 400, clientY: 380, deltaY: -90 });
    fireEvent.wheel(chart, { clientX: 790, clientY: 190, deltaY: 90 });
    await waitFor(() => expect(mocks.seriesApplyOptions).toHaveBeenCalled());

    fireEvent.dblClick(chart);

    expect(mocks.fitContent).toHaveBeenCalledTimes(2);
    expect(mocks.priceScaleApplyOptions).toHaveBeenCalledWith({ autoScale: true });
  });

  it("cleans chart resources on unmount", () => {
    const { unmount } = render(<BalanceLineChart currency="EUR" points={[
      { date: "2026-06-13T00:00:00Z", balance: 10 },
      { date: "2026-06-14T00:00:00Z", balance: 15 }
    ]} />);

    unmount();

    expect(ResizeObserverMock.instances[0].disconnect).toHaveBeenCalled();
    expect(mocks.chartRemove).toHaveBeenCalled();
  });
});
