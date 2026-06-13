import { useMemo, useState } from "react";
import { MetricStrip } from "../../components/MetricStrip";
import type { CurrencyCode } from "../../types";

const money = (value: number, currency: CurrencyCode) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency }).format(value);

interface RiskCalculatorProps {
  readonly initialBalance: number;
  readonly currency?: CurrencyCode;
}

export function RiskCalculator({ initialBalance, currency = "USD" }: RiskCalculatorProps) {
  const [portfolio, setPortfolio] = useState(Math.max(initialBalance, 0));
  const [risk, setRisk] = useState(1);
  const [stop, setStop] = useState(2);
  const [leverage, setLeverage] = useState(3);
  const [reward, setReward] = useState(2);
  const result = useMemo(() => {
    const maximumLoss = portfolio * (risk / 100);
    const margin = maximumLoss * (100 / (stop * leverage));
    return {
      maximumLoss,
      margin,
      position: margin * leverage,
      target: maximumLoss * reward
    };
  }, [portfolio, risk, stop, leverage, reward]);

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Risk planning</p>
          <h2>Position sizing calculator</h2>
        </div>
      </div>
      <div className="form-grid five">
        <label>
          <span>Portfolio</span>
          <input type="number" min="0" value={portfolio} onChange={(event) => setPortfolio(Number(event.target.value))} />
        </label>
        <label>
          <span>Risk %</span>
          <input type="number" min="0.01" step="0.1" value={risk} onChange={(event) => setRisk(Number(event.target.value))} />
        </label>
        <label>
          <span>Stop %</span>
          <input type="number" min="0.01" step="0.1" value={stop} onChange={(event) => setStop(Number(event.target.value))} />
        </label>
        <label>
          <span>Leverage</span>
          <input type="number" min="1" value={leverage} onChange={(event) => setLeverage(Number(event.target.value))} />
        </label>
        <label>
          <span>Reward ratio</span>
          <input type="number" min="0.1" step="0.1" value={reward} onChange={(event) => setReward(Number(event.target.value))} />
        </label>
      </div>
      <MetricStrip
        metrics={[
          { label: "Recommended margin", value: money(result.margin, currency) },
          { label: "Position size", value: money(result.position, currency) },
          { label: "Maximum loss", value: money(result.maximumLoss, currency), tone: "negative" },
          { label: "Target profit", value: money(result.target, currency), tone: "positive" }
        ]}
      />
    </section>
  );
}
