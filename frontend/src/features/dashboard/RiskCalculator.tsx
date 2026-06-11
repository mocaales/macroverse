import { useMemo, useState } from "react";
import { MetricStrip } from "../../components/MetricStrip";

const money = (value: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);

interface RiskCalculatorProps {
  readonly initialBalance: number;
}

export function RiskCalculator({ initialBalance }: RiskCalculatorProps) {
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
          { label: "Recommended margin", value: money(result.margin) },
          { label: "Position size", value: money(result.position) },
          { label: "Maximum loss", value: money(result.maximumLoss), tone: "negative" },
          { label: "Target profit", value: money(result.target), tone: "positive" }
        ]}
      />
    </section>
  );
}
