import { useMemo, useRef, useState } from "react";
import type { IChartApi } from "lightweight-charts";
import { ChevronDown, Focus, RotateCcw } from "lucide-react";

import {
  buildAnnualRoiSeries,
  matchesPresidentialCycle,
  presidentialCycle,
  type AnnualRoiSeries,
  type PresidentialCycle
} from "../features/charts/ytdRoi";
import type { ChartSeries } from "../types";
import {
  FinancialYtdPlot,
  type AverageOverlay,
  type HoverReadout
} from "./FinancialYtdPlot";

interface YearToDateRoiChartProps {
  readonly series: ChartSeries[];
}

type YearRange = 5 | 10 | "all";
type AveragePreset = Exclude<PresidentialCycle, "all"> | "all" | "custom";

const CURRENT_COLOR = "#46d7e8";
const HISTORICAL_COLORS = [
  "#f97316", "#a78bfa", "#22c55e", "#e879f9",
  "#60a5fa", "#facc15", "#fb7185", "#2dd4bf",
  "#c084fc", "#84cc16", "#f59e0b", "#38bdf8",
  "#f472b6", "#4ade80", "#eab308", "#818cf8"
];

const CYCLE_FILTERS: Array<{ value: PresidentialCycle; label: string }> = [
  { value: "all", label: "All cycles" },
  { value: "post-election", label: "Post-election" },
  { value: "midterm", label: "Midterm" },
  { value: "pre-election", label: "Pre-election" },
  { value: "election", label: "Election" }
];

const AVERAGE_OPTIONS: Array<{ id: AveragePreset; label: string; color: string }> = [
  { id: "all", label: "All years", color: "#f4b942" },
  { id: "election", label: "Election years", color: "#ef8354" },
  { id: "post-election", label: "Post-election years", color: "#2dd4bf" },
  { id: "midterm", label: "Midterm years", color: "#a78bfa" },
  { id: "pre-election", label: "Pre-election years", color: "#60a5fa" },
  { id: "custom", label: "Custom years", color: "#f472b6" }
];

function formatPercent(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatUsd(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value >= 1_000 ? 0 : 2
  }).format(value);
}

function seriesColor(year: number, annual: AnnualRoiSeries[], currentYear: number) {
  if (year === currentYear) return CURRENT_COLOR;
  const index = annual.findIndex((item) => item.year === year);
  return HISTORICAL_COLORS[index % HISTORICAL_COLORS.length];
}

function yearsForAverage(
  preset: AveragePreset,
  years: AnnualRoiSeries[],
  customYears: Set<number>,
  currentYear?: number
) {
  if (preset === "custom") return years.filter((item) => customYears.has(item.year));
  if (preset === "all") return years.filter((item) => item.year !== currentYear);
  return years.filter((item) => matchesPresidentialCycle(item.year, preset));
}

export function YearToDateRoiChart({ series }: YearToDateRoiChartProps) {
  const annual = useMemo(() => buildAnnualRoiSeries(series), [series]);
  const latest = annual.at(-1);
  const [range, setRange] = useState<YearRange>(10);
  const [cycle, setCycle] = useState<PresidentialCycle>("all");
  const [selectedYears, setSelectedYears] = useState<Set<number> | null>(null);
  const [activeAverages, setActiveAverages] = useState<Set<AveragePreset>>(() => new Set(["all"]));
  const [customAverageYears, setCustomAverageYears] = useState<Set<number>>(() => new Set());
  const [averageMenuOpen, setAverageMenuOpen] = useState(false);
  const [hover, setHover] = useState<HoverReadout | null>(null);
  const chartApiRef = useRef<IChartApi | null>(null);

  const rangeYears = useMemo(
    () => range === "all" ? annual : annual.slice(-range),
    [annual, range]
  );
  const filteredYears = useMemo(
    () => rangeYears.filter((item) => matchesPresidentialCycle(item.year, cycle)),
    [cycle, rangeYears]
  );
  const visible = useMemo(
    () => selectedYears === null
      ? filteredYears
      : filteredYears.filter((item) => selectedYears.has(item.year)),
    [filteredYears, selectedYears]
  );
  const averages = useMemo<AverageOverlay[]>(
    () => AVERAGE_OPTIONS.flatMap((option) => {
      if (!activeAverages.has(option.id)) return [];
      const years = yearsForAverage(option.id, rangeYears, customAverageYears, latest?.year);
      if (!years.length) return [];
      return [{ id: option.id, label: `AVG ${option.label}`, color: option.color, years }];
    }),
    [activeAverages, customAverageYears, latest?.year, rangeYears]
  );
  const currentPoints = latest?.points || [];
  const currentRoi = currentPoints.at(-1)?.roi || 0;
  const currentPrice = currentPoints.at(-1)?.price || 0;
  const readoutYears = [...visible].reverse();

  function resetLineSelections() {
    setSelectedYears(null);
    setHover(null);
  }

  function selectRange(next: YearRange) {
    setRange(next);
    resetLineSelections();
  }

  function selectCycle(next: PresidentialCycle) {
    setCycle(next);
    resetLineSelections();
  }

  function toggleYear(year: number) {
    setSelectedYears((current) => {
      const next = new Set(current || filteredYears.map((item) => item.year));
      if (next.has(year) && next.size > 1) next.delete(year);
      else next.add(year);
      return next;
    });
  }

  function toggleAverage(preset: AveragePreset) {
    setActiveAverages((current) => {
      const next = new Set(current);
      if (next.has(preset)) next.delete(preset);
      else next.add(preset);
      return next;
    });
  }

  function toggleCustomAverageYear(year: number) {
    setCustomAverageYears((current) => {
      const next = new Set(current);
      if (next.has(year)) next.delete(year);
      else next.add(year);
      return next;
    });
    setActiveAverages((current) => new Set(current).add("custom"));
  }

  function focusCurrentYear() {
    if (!latest || !filteredYears.some((item) => item.year === latest.year)) return;
    setSelectedYears(new Set([latest.year]));
    setHover(null);
  }

  function resetComparison() {
    setRange(10);
    setCycle("all");
    setSelectedYears(null);
    setActiveAverages(new Set(["all"]));
    setCustomAverageYears(new Set());
    setAverageMenuOpen(false);
    setHover(null);
    chartApiRef.current?.timeScale().fitContent();
  }

  return (
    <section className="ytd-terminal">
      <header className="ytd-terminal-header">
        <div className="ytd-instrument">
          <span className="ytd-symbol">₿</span>
          <div>
            <div className="ytd-title-line">
              <h2>Bitcoin</h2>
              <span>BTC / USD</span>
              <i>1D</i>
              <i>LOG</i>
            </div>
            <p>Indexed performance · January 1 = 100 · logarithmic scale</p>
          </div>
        </div>
        <div className="ytd-live-value">
          <span><i /> Database live</span>
          <strong>{formatUsd(currentPrice)}</strong>
          <em className={currentRoi >= 0 ? "positive" : "negative"}>{formatPercent(currentRoi)} YTD</em>
        </div>
      </header>

      <div className="ytd-toolbar">
        <div className="ytd-range" aria-label="Comparison range">
          {([5, 10, "all"] as YearRange[]).map((item) => (
            <button
              aria-pressed={range === item}
              className={range === item ? "active" : ""}
              key={item}
              onClick={() => selectRange(item)}
            >
              {item === "all" ? "All years" : `Last ${item}`}
            </button>
          ))}
        </div>
        <div className="ytd-actions">
          <div className="average-menu">
            <button
              aria-expanded={averageMenuOpen}
              className={activeAverages.size ? "active" : ""}
              onClick={() => setAverageMenuOpen((open) => !open)}
            >
              Add average
              {activeAverages.size > 0 && <b>{activeAverages.size}</b>}
              <ChevronDown size={14} />
            </button>
            {averageMenuOpen && (
              <div className="average-menu-popover">
                <header>
                  <span>Preconfigured averages</span>
                  <small>Multiple selections allowed</small>
                </header>
                {AVERAGE_OPTIONS.filter((option) => option.id !== "custom").map((option) => {
                  const years = yearsForAverage(option.id, rangeYears, customAverageYears, latest?.year);
                  return (
                    <button
                      aria-pressed={activeAverages.has(option.id)}
                      className={activeAverages.has(option.id) ? "selected" : ""}
                      key={option.id}
                      onClick={() => toggleAverage(option.id)}
                    >
                      <i style={{ borderColor: option.color, background: activeAverages.has(option.id) ? option.color : "transparent" }} />
                      <span>{option.label}<small>{years.map((item) => item.year).join(", ") || "No years in range"}</small></span>
                    </button>
                  );
                })}
                <div className="custom-average-section">
                  <button
                    aria-pressed={activeAverages.has("custom")}
                    className={activeAverages.has("custom") ? "selected" : ""}
                    onClick={() => toggleAverage("custom")}
                  >
                    <i />
                    <span>Custom years<small>{customAverageYears.size} selected</small></span>
                  </button>
                  <div>
                    {rangeYears.slice().reverse().map((item) => (
                      <button
                        aria-label={`Include ${item.year} in custom average`}
                        aria-pressed={customAverageYears.has(item.year)}
                        className={customAverageYears.has(item.year) ? "selected" : ""}
                        key={item.year}
                        onClick={() => toggleCustomAverageYear(item.year)}
                      >
                        {item.year}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
          <button disabled={!latest || !filteredYears.some((item) => item.year === latest.year)} onClick={focusCurrentYear}><Focus size={14} /> Focus current</button>
          <button onClick={resetComparison}><RotateCcw size={14} /> Reset</button>
        </div>
      </div>

      <div className="ytd-cycle-filter">
        <span>Presidential cycle</span>
        <div>
          {CYCLE_FILTERS.map((item) => (
            <button
              aria-pressed={cycle === item.value}
              className={cycle === item.value ? "active" : ""}
              key={item.value}
              onClick={() => selectCycle(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <strong>{filteredYears.length} years</strong>
      </div>

      <div className="ytd-readout" aria-live="polite">
        <span className="ytd-readout-date">{hover?.label || "Latest"}</span>
        <div>
          {readoutYears.map((item) => {
            const value = hover?.values.get(item.year) ?? item.points.at(-1)?.roi ?? 0;
            return (
              <span className={item.year === latest?.year ? "current" : ""} key={item.year}>
                <i style={{ background: seriesColor(item.year, annual, latest?.year || 0) }} />
                {item.year}
                <strong className={value >= 0 ? "positive" : "negative"}>{formatPercent(value)}</strong>
              </span>
            );
          })}
          {averages.map((average) => (
            <span className="average" key={average.id}>
              <i style={{ background: average.color }} />
              {average.label}
              <strong>{hover?.values.get(average.id) !== undefined ? formatPercent(hover.values.get(average.id) || 0) : "—"}</strong>
            </span>
          ))}
        </div>
      </div>

      <FinancialYtdPlot
        annual={annual}
        averages={averages}
        chartApiRef={chartApiRef}
        currentColor={CURRENT_COLOR}
        historicalColors={HISTORICAL_COLORS}
        onHover={setHover}
        visible={visible}
      />

      <footer className="ytd-footer">
        <div className="ytd-year-selector" aria-label="Visible years">
          {filteredYears.slice().reverse().map((item) => {
            const selected = selectedYears === null || selectedYears.has(item.year);
            const roi = item.points.at(-1)?.roi || 0;
            return (
              <button
                aria-pressed={selected}
                className={`${selected ? "selected" : ""} ${item.year === latest?.year ? "current" : ""}`}
                key={item.year}
                onClick={() => toggleYear(item.year)}
                title={`${presidentialCycle(item.year)} year`}
              >
                <i style={{ background: seriesColor(item.year, annual, latest?.year || 0) }} />
                <span>{item.year}<small>{presidentialCycle(item.year)}</small></span>
                <strong className={roi >= 0 ? "positive" : "negative"}>{formatPercent(roi)}</strong>
              </button>
            );
          })}
        </div>
        <div className="ytd-chart-note">
          X-axis: width · Y-axis: height · plot: both · double-click: reset
          <a href="https://www.tradingview.com/" rel="noreferrer" target="_blank">Charts by TradingView</a>
        </div>
      </footer>
    </section>
  );
}
