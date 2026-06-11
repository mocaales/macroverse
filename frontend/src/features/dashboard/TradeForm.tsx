import { useState, type FormEvent } from "react";
import type { ActionType } from "../../types";

export function TradeForm({
  account,
  onSubmit,
  busy
}: {
  account: string;
  onSubmit: (payload: {
    account: string;
    trade_time: string;
    action: ActionType;
    type?: string;
    symbol: string;
    pnl: number;
  }) => void;
  busy: boolean;
}) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [action, setAction] = useState<ActionType>("Trade");
  const [direction, setDirection] = useState("Long");
  const [symbol, setSymbol] = useState("");
  const [amount, setAmount] = useState(0);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit({
      account,
      trade_time: date,
      action,
      type: action === "Trade" ? direction : undefined,
      symbol: action === "Trade" ? symbol.toUpperCase() : "CASH",
      pnl: action === "Withdraw" ? -Math.abs(amount) : amount
    });
    setAmount(0);
  };

  return (
    <form className="stack" onSubmit={submit}>
      <div className="form-grid two">
        <label>
          Entry date
          <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </label>
        <label>
          Action
          <select value={action} onChange={(event) => setAction(event.target.value as ActionType)}>
            <option>Trade</option>
            <option>Deposit</option>
            <option>Withdraw</option>
          </select>
        </label>
      </div>
      {action === "Trade" && (
        <div className="form-grid two">
          <label>
            Direction
            <select value={direction} onChange={(event) => setDirection(event.target.value)}>
              <option>Long</option>
              <option>Short</option>
            </select>
          </label>
          <label>
            Symbol
            <input required value={symbol} placeholder="BTCUSDT" onChange={(event) => setSymbol(event.target.value)} />
          </label>
        </div>
      )}
      <label>
        {action === "Trade" ? "Realised P&L" : "Amount"}
        <input
          type="number"
          step="0.01"
          min={action === "Trade" ? undefined : 0}
          value={amount}
          onChange={(event) => setAmount(Number(event.target.value))}
        />
      </label>
      <button className="button primary" disabled={busy}>
        Submit entry
      </button>
    </form>
  );
}
