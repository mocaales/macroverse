import { useEffect, useRef, type MutableRefObject } from "react";
import {
  ColorType,
  createChart,
  CrosshairMode,
  LineSeries,
  LineStyle,
  PriceScaleMode,
  type AutoscaleInfo,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type MouseEventParams,
  type Time
} from "lightweight-charts";

import {
  horizontalZoomRange,
  interpolateRange,
  isRangeSettled,
  normalizedWheelDelta,
  scaleAutoscaleInfo,
  verticalZoom as constrainVerticalZoom,
  type NumericRange
} from "../features/charts/ytdChartInteraction";
import type { AnnualRoiSeries } from "../features/charts/ytdRoi";

type ChartSeriesApi = ISeriesApi<"Line">;

interface SeriesMeta {
  id: number | string;
}

export interface HoverReadout {
  label: string;
  values: Map<number | string, number>;
}

export interface AverageOverlay {
  id: string;
  label: string;
  color: string;
  years: AnnualRoiSeries[];
}

interface FinancialYtdPlotProps {
  readonly annual: AnnualRoiSeries[];
  readonly visible: AnnualRoiSeries[];
  readonly averages: AverageOverlay[];
  readonly onHover: (readout: HoverReadout | null) => void;
  readonly chartApiRef: MutableRefObject<IChartApi | null>;
  readonly currentColor: string;
  readonly historicalColors: string[];
}

function formatPercent(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function averageSeries(years: AnnualRoiSeries[]) {
  const values = new Map<number, number[]>();
  years
    .forEach((item) => item.points.forEach((point) => {
      values.set(point.day, [...(values.get(point.day) || []), point.roi]);
    }));
  return [...values.entries()]
    .sort(([left], [right]) => left - right)
    .map(([day, items]) => ({
      day,
      roi: items.reduce((total, value) => total + value, 0) / items.length
    }));
}

function referenceTime(day: number): Time {
  return new Date(Date.UTC(2001, 0, day + 1)).toISOString().slice(0, 10) as Time;
}

function dayFromTime(time: Time): number | null {
  if (typeof time !== "string") return null;
  const parsed = new Date(`${time}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return null;
  return Math.floor((parsed.getTime() - Date.UTC(2001, 0, 1)) / 86_400_000);
}

function monthDayLabel(day: number) {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" })
    .format(new Date(Date.UTC(2001, 0, day + 1)));
}

function valueFromData(data: unknown) {
  if (!data || typeof data !== "object" || !("value" in data)) return null;
  const value = (data as LineData<Time>).value;
  return typeof value === "number" ? value : null;
}

function createAutoscaleProvider(getZoom: () => number) {
  return (baseImplementation: () => AutoscaleInfo | null) =>
    scaleAutoscaleInfo(baseImplementation(), getZoom());
}

export function FinancialYtdPlot({
  annual,
  visible,
  averages,
  onHover,
  chartApiRef,
  currentColor,
  historicalColors
}: FinancialYtdPlotProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    const latest = annual.at(-1);
    if (!container || !latest || !visible.length) return;

    const colorForYear = (year: number) => {
      if (year === latest.year) return currentColor;
      const index = annual.findIndex((item) => item.year === year);
      return historicalColors[index % historicalColors.length];
    };
    const chart = createChart(container, {
      width: Math.max(container.clientWidth, 320),
      height: 560,
      layout: {
        background: { type: ColorType.Solid, color: "#080c12" },
        textColor: "#738096",
        fontFamily: "IBM Plex Mono, monospace",
        fontSize: 11,
        attributionLogo: false
      },
      grid: {
        vertLines: { color: "rgba(111, 128, 153, 0.07)" },
        horzLines: { color: "rgba(111, 128, 153, 0.09)" }
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: "rgba(198, 210, 227, 0.42)",
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: "#263244"
        },
        horzLine: {
          color: "rgba(198, 210, 227, 0.26)",
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: "#263244"
        }
      },
      rightPriceScale: {
        borderColor: "#202a38",
        mode: PriceScaleMode.Logarithmic,
        scaleMargins: { top: 0.1, bottom: 0.1 },
        entireTextOnly: true
      },
      timeScale: {
        borderColor: "#202a38",
        timeVisible: false,
        secondsVisible: false,
        rightOffset: 0,
        barSpacing: 3,
        minBarSpacing: 0.7,
        fixLeftEdge: true,
        fixRightEdge: true,
        lockVisibleTimeRangeOnResize: true,
        rightBarStaysOnScroll: true,
        tickMarkFormatter: (time: Time) => {
          const day = dayFromTime(time);
          if (day === null) return "";
          const date = new Date(Date.UTC(2001, 0, day + 1));
          return new Intl.DateTimeFormat("en-US", { month: "short", timeZone: "UTC" }).format(date);
        }
      },
      localization: {
        priceFormatter: (indexValue: number) => formatPercent(indexValue - 100)
      },
      handleScroll: {
        mouseWheel: false,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true
      },
      kineticScroll: {
        mouse: true,
        touch: true
      }
    });
    chartApiRef.current = chart;

    const metadata = new Map<ChartSeriesApi, SeriesMeta>();
    visible
      .filter((item) => item.year !== latest.year)
      .forEach((item) => {
        const color = colorForYear(item.year);
        const api = chart.addSeries(LineSeries, {
          title: String(item.year),
          color,
          lineWidth: 3,
          priceLineVisible: false,
          lastValueVisible: visible.length <= 6,
          crosshairMarkerVisible: true,
          crosshairMarkerRadius: 3,
          crosshairMarkerBorderColor: "#080c12",
          crosshairMarkerBackgroundColor: color
        });
        api.setData(item.points.map((point) => ({ time: referenceTime(point.day), value: point.roi + 100 })));
        metadata.set(api, { id: item.year });
      });

    averages.forEach((overlay) => {
      const average = averageSeries(overlay.years);
      if (average.length) {
        const api = chart.addSeries(LineSeries, {
          title: overlay.label,
          color: overlay.color,
          lineWidth: 3,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: true,
          crosshairMarkerVisible: false
        });
        api.setData(average.map((point) => ({ time: referenceTime(point.day), value: point.roi + 100 })));
        metadata.set(api, { id: overlay.id });
      }
    });

    const current = visible.find((item) => item.year === latest.year);
    if (current) {
      const api = chart.addSeries(LineSeries, {
        title: String(current.year),
        color: currentColor,
        lineWidth: 4,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 5,
        crosshairMarkerBorderWidth: 2,
        crosshairMarkerBorderColor: "#080c12",
        crosshairMarkerBackgroundColor: currentColor
      });
      api.setData(current.points.map((point) => ({ time: referenceTime(point.day), value: point.roi + 100 })));
      api.createPriceLine({
        price: 100,
        color: "rgba(202, 213, 229, 0.38)",
        lineWidth: 1,
        lineStyle: LineStyle.Solid,
        axisLabelVisible: false,
        title: ""
      });
      metadata.set(api, { id: current.year });
    }

    const crosshairHandler = (param: MouseEventParams<Time>) => {
      if (!param.time || !param.point) {
        onHover(null);
        return;
      }
      const day = dayFromTime(param.time);
      if (day === null) {
        onHover(null);
        return;
      }
      const values = new Map<number | string, number>();
      metadata.forEach((meta, api) => {
        const value = valueFromData(param.seriesData.get(api));
        if (value !== null) values.set(meta.id, value - 100);
      });
      onHover({ label: monthDayLabel(day), values });
    };
    chart.subscribeCrosshairMove(crosshairHandler);
    chart.timeScale().fitContent();

    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width) chart.applyOptions({ width });
    });
    observer.observe(container);
    const initialLogicalRange = chart.timeScale().getVisibleLogicalRange();
    const fullLogicalRange: NumericRange | null = initialLogicalRange
      ? { from: initialLogicalRange.from, to: initialLogicalRange.to }
      : null;
    let verticalZoom = 1;
    let targetVerticalZoom = 1;
    let renderedLogicalRange: NumericRange | null = fullLogicalRange;
    let targetLogicalRange: NumericRange | null = fullLogicalRange;
    let animationFrame: number | null = null;
    const seriesApis = [...metadata.keys()];
    const autoscaleInfoProvider = createAutoscaleProvider(() => verticalZoom);
    const applyVerticalZoom = () => {
      seriesApis.forEach((api) => api.applyOptions({
        autoscaleInfoProvider
      }));
      chart.priceScale("right").applyOptions({ autoScale: true });
    };
    const easeZoom = () => {
      const smoothing = 0.22;
      let settled = true;

      if (renderedLogicalRange && targetLogicalRange) {
        renderedLogicalRange = interpolateRange(renderedLogicalRange, targetLogicalRange, smoothing);
        chart.timeScale().setVisibleLogicalRange(renderedLogicalRange);
        if (!isRangeSettled(renderedLogicalRange, targetLogicalRange)) settled = false;
      }

      verticalZoom += (targetVerticalZoom - verticalZoom) * smoothing;
      applyVerticalZoom();
      if (Math.abs(targetVerticalZoom - verticalZoom) > 0.001) settled = false;

      if (settled) {
        if (targetLogicalRange) {
          renderedLogicalRange = targetLogicalRange;
          chart.timeScale().setVisibleLogicalRange(targetLogicalRange);
        }
        verticalZoom = targetVerticalZoom;
        applyVerticalZoom();
        animationFrame = null;
        return;
      }
      animationFrame = requestAnimationFrame(easeZoom);
    };
    const scheduleZoom = () => {
      animationFrame ??= requestAnimationFrame(easeZoom);
    };
    const zoomHorizontal = (event: WheelEvent, factor: number) => {
      const range = targetLogicalRange || chart.timeScale().getVisibleLogicalRange();
      if (!range || !fullLogicalRange) return;
      const rect = container.getBoundingClientRect();
      const pointerRatio = (event.clientX - rect.left) / rect.width;
      targetLogicalRange = horizontalZoomRange(range, fullLogicalRange, pointerRatio, factor);
    };
    const containWheel = (event: WheelEvent) => {
      event.preventDefault();
      const delta = normalizedWheelDelta(event.deltaY, event.deltaMode, container.clientHeight);
      const factor = Math.exp(delta * 0.0018);
      const rect = container.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const overXAxis = y >= rect.height - 34;
      const overYAxis = x >= rect.width - 82;
      if (overXAxis && !overYAxis) {
        zoomHorizontal(event, factor);
        scheduleZoom();
        return;
      }
      if (overYAxis && !overXAxis) {
        targetVerticalZoom = constrainVerticalZoom(targetVerticalZoom, factor);
        scheduleZoom();
        return;
      }
      zoomHorizontal(event, factor);
      targetVerticalZoom = constrainVerticalZoom(targetVerticalZoom, factor);
      scheduleZoom();
    };
    const resetTimeScale = () => {
      if (animationFrame !== null) cancelAnimationFrame(animationFrame);
      animationFrame = null;
      verticalZoom = 1;
      targetVerticalZoom = 1;
      applyVerticalZoom();
      chart.timeScale().fitContent();
      const resetRange = chart.timeScale().getVisibleLogicalRange();
      renderedLogicalRange = resetRange ? { from: resetRange.from, to: resetRange.to } : null;
      targetLogicalRange = renderedLogicalRange;
    };
    container.addEventListener("wheel", containWheel, { passive: false });
    container.addEventListener("dblclick", resetTimeScale);

    return () => {
      observer.disconnect();
      if (animationFrame !== null) cancelAnimationFrame(animationFrame);
      container.removeEventListener("wheel", containWheel);
      container.removeEventListener("dblclick", resetTimeScale);
      chart.unsubscribeCrosshairMove(crosshairHandler);
      chart.remove();
      chartApiRef.current = null;
    };
  }, [annual, averages, chartApiRef, currentColor, historicalColors, onHover, visible]);

  return <div className="financial-ytd-plot" data-testid="ytd-chart" ref={containerRef} />;
}
