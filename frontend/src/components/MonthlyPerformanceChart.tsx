import { useEffect, useRef, useState } from "react";
import {
  ColorType,
  createChart,
  CrosshairMode,
  HistogramSeries,
  LineStyle,
  type HistogramData,
  type Time
} from "lightweight-charts";
import type { CurrencyCode } from "../types";

export interface MonthlyPerformancePoint {
  month: string;
  trades: number;
  value: number;
}

interface TooltipState {
  left: number;
  month: string;
  top: number;
  trades: number;
  value: number;
}

function chartTime(month: string): Time {
  return `${month}-01` as Time;
}

function monthLabel(time: Time) {
  if (typeof time !== "string") return "";
  return new Intl.DateTimeFormat("en-US", { month: "long", timeZone: "UTC", year: "numeric" })
    .format(new Date(`${time}T00:00:00Z`));
}

function formatMoney(value: number, currency: CurrencyCode, decimals = 0) {
  return new Intl.NumberFormat("en-US", {
    currency,
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
    style: "currency"
  }).format(value);
}

export function MonthlyPerformanceChart({ currency, points }: { readonly currency: CurrencyCode; readonly points: MonthlyPerformancePoint[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    setTooltip(null);
    if (!container || !points.length) return;
    const details = new Map(points.map((point) => [String(chartTime(point.month)), point]));
    const chart = createChart(container, {
      width: Math.max(container.clientWidth, 320),
      height: Math.max(container.clientHeight, 260),
      layout: {
        attributionLogo: false,
        background: { color: "#080b10", type: ColorType.Solid },
        fontFamily: "IBM Plex Mono, monospace",
        fontSize: 11,
        textColor: "#8290a6"
      },
      grid: {
        horzLines: { color: "rgba(111, 128, 153, 0.10)" },
        vertLines: { color: "rgba(111, 128, 153, 0.05)" }
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        horzLine: { color: "rgba(198, 210, 227, 0.24)", labelBackgroundColor: "#0d1118", style: LineStyle.Dashed, width: 1 },
        vertLine: { color: "rgba(198, 210, 227, 0.36)", labelBackgroundColor: "#0d1118", style: LineStyle.Dashed, width: 1 }
      },
      handleScale: false,
      handleScroll: false,
      localization: { priceFormatter: (value: number) => formatMoney(value, currency) },
      rightPriceScale: { borderColor: "#202a38", scaleMargins: { bottom: .16, top: .16 } },
      timeScale: {
        barSpacing: 46,
        borderColor: "#202a38",
        fixLeftEdge: true,
        fixRightEdge: true,
        minBarSpacing: 18,
        tickMarkFormatter: (time: Time) => typeof time === "string"
          ? new Intl.DateTimeFormat("en-US", { month: "short", timeZone: "UTC" }).format(new Date(`${time}T00:00:00Z`))
          : ""
      }
    });
    const series = chart.addSeries(HistogramSeries, {
      base: 0,
      priceFormat: { formatter: (value: number) => formatMoney(value, currency, 2), type: "custom" },
      priceLineVisible: false,
      title: "Monthly return"
    });
    series.setData(points.map<HistogramData<Time>>((point) => ({
      color: point.value >= 0 ? "rgba(25, 212, 146, 0.82)" : "rgba(255, 92, 114, 0.82)",
      time: chartTime(point.month),
      value: point.value
    })));
    chart.timeScale().fitContent();
    chart.subscribeCrosshairMove((param) => {
      if (!param.point || !param.time) {
        setTooltip(null);
        return;
      }
      const value = param.seriesData.get(series) as HistogramData<Time> | undefined;
      const detail = details.get(String(param.time));
      if (!value || !detail) {
        setTooltip(null);
        return;
      }
      setTooltip({
        left: Math.min(Math.max(param.point.x + 16, 10), container.clientWidth - 174),
        month: monthLabel(param.time),
        top: Math.min(Math.max(param.point.y + 16, 10), container.clientHeight - 112),
        trades: detail.trades,
        value: value.value
      });
    });
    const observer = new ResizeObserver((entries) => {
      const { height, width } = entries[0]?.contentRect || {};
      if (height && width) chart.applyOptions({ height, width });
    });
    observer.observe(container);
    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [currency, points]);

  return (
    <div className="monthly-performance-chart" data-testid="monthly-performance-chart" ref={containerRef}>
      {tooltip && (
        <div className="monthly-chart-tooltip" style={{ left: tooltip.left, top: tooltip.top }}>
          <span>{tooltip.month}</span>
          <strong className={tooltip.value >= 0 ? "positive" : "negative"}>
            {tooltip.value >= 0 ? "+" : ""}{formatMoney(tooltip.value, currency, 2)}
          </strong>
          <small>{tooltip.trades} closed trade{tooltip.trades === 1 ? "" : "s"}</small>
        </div>
      )}
    </div>
  );
}
