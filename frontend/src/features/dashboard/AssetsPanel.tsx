import { useState, type FormEvent } from "react";
import { Trash2 } from "lucide-react";
import type { Asset } from "../../types";

export function AssetsPanel({
  account,
  assets,
  onCreate,
  onDelete,
  busy
}: {
  account: string;
  assets: Asset[];
  onCreate: (payload: Omit<Asset, "id" | "created_at">) => void;
  onDelete: (id: string) => void;
  busy: boolean;
}) {
  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState(0);
  const [unit, setUnit] = useState("units");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!symbol || quantity <= 0) return;
    onCreate({ account, symbol: symbol.toUpperCase(), quantity, display_quantity: quantity, unit });
    setSymbol("");
    setQuantity(0);
  };

  return (
    <section className="split-layout">
      <div className="panel">
        <p className="eyebrow">Portfolio</p>
        <h2>Add asset</h2>
        <form className="stack" onSubmit={submit}>
          <label>
            Ticker symbol
            <input required value={symbol} placeholder="BTC-USD" onChange={(event) => setSymbol(event.target.value)} />
          </label>
          <label>
            Quantity
            <input type="number" min="0" step="0.000001" value={quantity} onChange={(event) => setQuantity(Number(event.target.value))} />
          </label>
          <label>
            Unit
            <select value={unit} onChange={(event) => setUnit(event.target.value)}>
              <option value="units">units</option>
              <option value="oz">oz (troy)</option>
              <option value="g">grams</option>
            </select>
          </label>
          <button className="button primary" disabled={busy}>Add asset</button>
        </form>
      </div>
      <div className="panel">
        <p className="eyebrow">Holdings</p>
        <h2>{assets.length} open positions</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Symbol</th><th>Quantity</th><th>Unit</th><th /></tr></thead>
            <tbody>
              {assets.map((asset) => (
                <tr key={asset.id}>
                  <td className="symbol">{asset.symbol}</td>
                  <td>{asset.display_quantity.toLocaleString()}</td>
                  <td>{asset.unit}</td>
                  <td><button className="icon-button" onClick={() => onDelete(asset.id)}><Trash2 size={15} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
