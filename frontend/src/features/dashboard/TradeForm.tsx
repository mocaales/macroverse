import { useState, type FormEvent } from "react";
import type { ActionType } from "../../types";

interface TradeFormProps {
  readonly account: string;
  readonly onSubmit: (payload: {
    account: string;
    trade_time: string;
    action: ActionType;
    type?: string;
    symbol: string;
    pnl: number;
  }) => void;
  readonly busy: boolean;
}

function signedAmount(action: ActionType, tradeResult: "profit" | "loss" | "flat", amount: number) {
  if (action === "Withdraw" || (action === "Trade" && tradeResult === "loss")) return -amount;
  if (action === "Trade" && tradeResult === "flat") return 0;
  return amount;
}

export function TradeForm({
  account,
  onSubmit,
  busy
}: TradeFormProps) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [action, setAction] = useState<ActionType>("Trade");
  const [direction, setDirection] = useState("Long");
  const [symbol, setSymbol] = useState("");
  const [amount, setAmount] = useState("");
  const [tradeResult, setTradeResult] = useState<"profit" | "loss" | "flat">("profit");

  const numericAmount = Math.abs(Number(amount) || 0);
  let displayedAmount = amount;
  if (action === "Trade" && tradeResult === "loss" && amount) {
    displayedAmount = `-${numericAmount}`;
  }
  const pnl = signedAmount(action, tradeResult, numericAmount);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit({
      account,
      trade_time: date,
      action,
      type: action === "Trade" ? direction : undefined,
      symbol: action === "Trade" ? symbol.toUpperCase() : "CASH",
      pnl
    });
    setAmount("");
  };

  return (
    <form className="stack" onSubmit={submit}>
      <div className="form-grid two">
        <label>
          <span>Entry date</span>
          <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </label>
        <label>
          <span>Action</span>
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
            <span>Direction</span>
            <select value={direction} onChange={(event) => setDirection(event.target.value)}>
              <option>Long</option>
              <option>Short</option>
            </select>
          </label>
          <label>
            <span>Symbol</span>
            <input required value={symbol} placeholder="BTCUSDT" onChange={(event) => setSymbol(event.target.value)} />
          </label>
        </div>
      )}
      {action === "Trade" && (
        <label>
          <span>Trade result</span>
          <select value={tradeResult} onChange={(event) => setTradeResult(event.target.value as typeof tradeResult)}>
            <option value="profit">Profitable</option>
            <option value="loss">Not profitable</option>
            <option value="flat">Break-even</option>
          </select>
        </label>
      )}
      <label>
        <span>{action === "Trade" ? "Realised P&L" : "Amount"}</span>
        <input
          type="number"
          step="0.01"
          min={action === "Trade" ? undefined : 0}
          placeholder={action === "Trade" && tradeResult === "loss" ? "-0.00" : "0.00"}
          value={displayedAmount}
          onChange={(event) => setAmount(event.target.value.replace("-", ""))}
        />
      </label>
      <button className="button primary" disabled={busy}>
        Submit entry
      </button>
    </form>
  );
}
