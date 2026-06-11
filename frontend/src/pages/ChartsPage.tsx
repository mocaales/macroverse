import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Search, Star } from "lucide-react";
import { chartsApi } from "../api/queries";
import { EmptyState } from "../components/EmptyState";
import { Plot } from "../components/Plot";
import { useAuth } from "../features/auth/AuthProvider";
import type { ChartDefinition, ChartSeries } from "../types";

function transformSeries(chart: ChartDefinition, series: ChartSeries[]) {
  if (chart.slug !== "year_to_date_roi") return series;
  const rows = series[0]?.points || [];
  const years = new Map<string, typeof rows>();
  rows.forEach((point) => {
    const year = point.date.slice(0, 4);
    years.set(year, [...(years.get(year) || []), point]);
  });
  return [...years.entries()].slice(-8).map(([year, points]) => {
    const start = points[0]?.value || 1;
    return { name: year, points: points.map((point) => ({ date: point.date.slice(5), value: (point.value / start - 1) * 100 })) };
  });
}

function chartContent(
  chart: ChartDefinition,
  series: ChartSeries[],
  isLoading: boolean,
  isError: boolean
) {
  if (!chart.available) {
    return (
      <EmptyState
        title="Chart is being migrated"
        body="The original chart remains in the legacy reference while its data model is moved to the API."
      />
    );
  }
  if (isLoading) {
    return <EmptyState title="Loading market data" body="External sources can take several seconds to respond." />;
  }
  if (isError) {
    return (
      <EmptyState
        title="Market data unavailable"
        body="Check the backend API keys and external data-provider connectivity."
      />
    );
  }
  const displaySeries = transformSeries(chart, series);
  return (
    <Plot
      data={displaySeries.map((item) => ({
        x: item.points.map((point) => point.date),
        y: item.points.map((point) => point.value),
        name: item.name,
        type: "scatter",
        mode: "lines",
        line: { width: 1.7 }
      }))}
      layout={{
        autosize: true, height: 610, margin: { l: 64, r: 20, t: 30, b: 48 },
        paper_bgcolor: "transparent", plot_bgcolor: "transparent",
        font: { color: "#7e899f", family: "IBM Plex Mono" },
        xaxis: { gridcolor: "#1b2230" }, yaxis: { gridcolor: "#1b2230" },
        legend: { orientation: "h", y: 1.08 }
      }}
      config={{ responsive: true, displaylogo: false }}
      useResizeHandler style={{ width: "100%" }}
    />
  );
}

export function ChartsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [selected, setSelected] = useState<ChartDefinition | null>(null);
  const charts = useQuery({ queryKey: ["charts"], queryFn: chartsApi.charts });
  const favourites = useQuery({ queryKey: ["chart-favourites"], queryFn: chartsApi.favourites, enabled: Boolean(user) });
  const series = useQuery({
    queryKey: ["chart-series", selected?.slug],
    queryFn: () => chartsApi.series(selected!.slug),
    enabled: Boolean(selected?.available)
  });
  const toggle = useMutation({
    mutationFn: chartsApi.toggleFavourite,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chart-favourites"] })
  });
  const filtered = useMemo(() => (charts.data || []).filter((chart) => {
    if (category !== "All" && chart.category !== category) return false;
    return `${chart.name} ${chart.summary}`.toLowerCase().includes(search.toLowerCase());
  }), [charts.data, search, category]);

  if (selected) {
    return (
      <div className="page">
        <button className="text-button back-button" onClick={() => setSelected(null)}><ArrowLeft size={16} /> Back to charts</button>
        <section className="page-toolbar">
          <div><p className="eyebrow">{selected.category} · {selected.quick.join(", ")}</p><h1>{selected.name}</h1><p className="page-subtitle">{selected.summary}</p></div>
          {user && <button className="icon-button starred" onClick={() => toggle.mutate(selected.name)}><Star size={18} fill={favourites.data?.includes(selected.name) ? "currentColor" : "none"} /></button>}
        </section>
        <section className="panel chart-detail">
          {chartContent(selected, series.data || [], series.isLoading, series.isError)}
        </section>
      </div>
    );
  }

  return (
    <div className="page">
      <section className="page-toolbar">
        <div><p className="eyebrow">Research library</p><h1>Market charts</h1><p className="page-subtitle">Macro and crypto datasets in a focused analytical workspace.</p></div>
      </section>
      <div className="chart-filters">
        <label className="search-field"><Search size={16} /><input placeholder="Search charts" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
        <div className="segmented">
          {["All", "Macro", "Crypto"].map((item) => <button className={category === item ? "active" : ""} onClick={() => setCategory(item)} key={item}>{item}</button>)}
        </div>
      </div>
      <section className="chart-catalog">
        {filtered.map((chart, index) => (
          <article className="chart-row" key={chart.slug} style={{ animationDelay: `${index * 45}ms` }}>
            <button className="chart-open" onClick={() => setSelected(chart)}>
              <span className="chart-index">{String(index + 1).padStart(2, "0")}</span>
              <span><small>{chart.category} · {chart.assets.join(", ") || "Rates"}</small><strong>{chart.name}</strong><p>{chart.summary}</p></span>
              <span className={`availability ${chart.available ? "" : "pending"}`}>{chart.available ? "Open dataset" : "Migration pending"}</span>
            </button>
            {user && <button className="icon-button" onClick={() => toggle.mutate(chart.name)} aria-label={`Favourite ${chart.name}`}><Star size={17} fill={favourites.data?.includes(chart.name) ? "currentColor" : "none"} /></button>}
          </article>
        ))}
      </section>
    </div>
  );
}
