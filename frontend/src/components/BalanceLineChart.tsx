import { useEffect, useRef } from "react";
import {
  ColorType,
  createChart,
  CrosshairMode,
  LineSeries,
  LineStyle,
  type AutoscaleInfo,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type Time
} from "lightweight-charts";

import {
  horizontalZoomRange,
  interpolateRange,
  isRangeSettled,
  normalizedWheelDelta,
  verticalZoom as constrainVerticalZoom,
  type NumericRange
} from "../features/charts/ytdChartInteraction";
import type { CurrencyCode, DashboardSummary } from "../types";

type BalancePoint = DashboardSummary["equity_curve"][number];
type BalanceSeries = ISeriesApi<"Line">;

interface BalanceLineChartProps {
  readonly currency: CurrencyCode;
  readonly points: BalancePoint[];
}

function chartTime(value: string): Time {
  return utcDay(value).toISOString().slice(0, 10) as Time;
}

function utcDay(value: string) {
  const parsed = new Date(value);
  return new Date(Date.UTC(parsed.getUTCFullYear(), parsed.getUTCMonth(), parsed.getUTCDate()));
}

function formatMoney(value: number, currency: CurrencyCode) {
  return new Intl.NumberFormat("en-US", {
    currency,
    maximumFractionDigits: Math.abs(value) >= 1_000 ? 0 : 2,
    style: "currency"
  }).format(value);
}

function expandSinglePoint(points: BalancePoint[]) {
  if (points.length !== 1) return points;
  const start = utcDay(points[0].date);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 1);
  return [
    { ...points[0], date: start.toISOString() },
    { ...points[0], date: end.toISOString() }
  ];
}

function scaleLinearAutoscaleInfo(base: AutoscaleInfo | null, zoom: number): AutoscaleInfo | null {
  const range = base?.priceRange;
  if (!base || !range) return base;
  const center = (range.minValue + range.maxValue) / 2;
  const halfSpan = Math.max((range.maxValue - range.minValue) / 2, 1) * zoom;
  return {
    ...base,
    priceRange: {
      minValue: center - halfSpan,
      maxValue: center + halfSpan
    }
  };
}

function createAutoscaleProvider(getZoom: () => number) {
  return (baseImplementation: () => AutoscaleInfo | null) =>
    scaleLinearAutoscaleInfo(baseImplementation(), getZoom());
}

export function BalanceLineChart({ currency, points }: BalanceLineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    const seriesPoints = expandSinglePoint(points);
    if (!container || !seriesPoints.length) return;

    const latest = seriesPoints.at(-1);
    const lineColor = (latest?.balance || 0) >= 0 ? "#19d492" : "#ff5c72";
    const chart = createChart(container, {
      width: Math.max(container.clientWidth, 320),
      height: 390,
      layout: {
        background: { type: ColorType.Solid, color: "#080c12" },
        textColor: "#8290a6",
        fontFamily: "IBM Plex Mono, monospace",
        fontSize: 11,
        attributionLogo: false
      },
      grid: {
        vertLines: { color: "rgba(111, 128, 153, 0.07)" },
        horzLines: { color: "rgba(111, 128, 153, 0.10)" }
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
        entireTextOnly: true,
        scaleMargins: { top: 0.14, bottom: 0.16 }
      },
      timeScale: {
        borderColor: "#202a38",
        fixLeftEdge: true,
        fixRightEdge: true,
        lockVisibleTimeRangeOnResize: true,
        rightBarStaysOnScroll: true,
        rightOffset: 2,
        barSpacing: 24,
        minBarSpacing: 4,
        timeVisible: false,
        secondsVisible: false,
        tickMarkFormatter: (time: Time) => {
          if (typeof time !== "string") return "";
          return new Intl.DateTimeFormat("en-US", { day: "numeric", month: "short", timeZone: "UTC" })
            .format(new Date(`${time}T00:00:00Z`));
        }
      },
      localization: {
        priceFormatter: (value: number) => formatMoney(value, currency)
      },
      handleScroll: {
        horzTouchDrag: true,
        mouseWheel: false,
        pressedMouseMove: true,
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
    chartRef.current = chart;

    const series = chart.addSeries(LineSeries, {
      color: lineColor,
      crosshairMarkerBackgroundColor: lineColor,
      crosshairMarkerBorderColor: "#080c12",
      crosshairMarkerBorderWidth: 2,
      crosshairMarkerRadius: 5,
      lastValueVisible: true,
      lineWidth: 3,
      priceFormat: {
        type: "custom",
        formatter: (value: number) => formatMoney(value, currency)
      },
      priceLineColor: lineColor,
      priceLineStyle: LineStyle.Solid,
      priceLineVisible: true,
      title: "Balance"
    });
    series.setData(seriesPoints.map<LineData<Time>>((point) => ({
      time: chartTime(point.date),
      value: point.balance
    })));
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
    const autoscaleInfoProvider = createAutoscaleProvider(() => verticalZoom);
    const applyVerticalZoom = (api: BalanceSeries) => {
      api.applyOptions({ autoscaleInfoProvider });
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
      applyVerticalZoom(series);
      if (Math.abs(targetVerticalZoom - verticalZoom) > 0.001) settled = false;
      if (settled) {
        if (targetLogicalRange) {
          renderedLogicalRange = targetLogicalRange;
          chart.timeScale().setVisibleLogicalRange(targetLogicalRange);
        }
        verticalZoom = targetVerticalZoom;
        applyVerticalZoom(series);
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
    const resetScale = () => {
      if (animationFrame !== null) cancelAnimationFrame(animationFrame);
      animationFrame = null;
      verticalZoom = 1;
      targetVerticalZoom = 1;
      applyVerticalZoom(series);
      chart.timeScale().fitContent();
      const resetRange = chart.timeScale().getVisibleLogicalRange();
      renderedLogicalRange = resetRange ? { from: resetRange.from, to: resetRange.to } : null;
      targetLogicalRange = renderedLogicalRange;
    };
    container.addEventListener("wheel", containWheel, { passive: false });
    container.addEventListener("dblclick", resetScale);

    return () => {
      observer.disconnect();
      if (animationFrame !== null) cancelAnimationFrame(animationFrame);
      container.removeEventListener("wheel", containWheel);
      container.removeEventListener("dblclick", resetScale);
      chart.remove();
      chartRef.current = null;
    };
  }, [currency, points]);

  return <div className="balance-line-chart" data-testid="balance-chart" ref={containerRef} />;
}
