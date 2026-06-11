export interface Metric {
  label: string;
  value: string;
  detail?: string;
  tone?: "positive" | "negative" | "neutral";
}

export function MetricStrip({ metrics }: { metrics: Metric[] }) {
  return (
    <section className="metric-strip">
      {metrics.map((metric) => (
        <div className="metric" key={metric.label}>
          <span>{metric.label}</span>
          <strong className={metric.tone || "neutral"}>{metric.value}</strong>
          {metric.detail && <small>{metric.detail}</small>}
        </div>
      ))}
    </section>
  );
}
