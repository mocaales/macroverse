import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2, X } from "lucide-react";
import { portfolioApi } from "../api/queries";
import { getApiError } from "../api/client";
import { AccountSelector } from "../components/AccountSelector";
import { EmptyState } from "../components/EmptyState";
import { MetricStrip } from "../components/MetricStrip";
import { useAuth } from "../features/auth/AuthProvider";
import type { CurrencyCode, Trade } from "../types";

const money = (value = 0, currency: CurrencyCode = "EUR") =>
  new Intl.NumberFormat("en-US", { style: "currency", currency }).format(value);

export function JournalPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState("");
  const [search, setSearch] = useState("");
  const [action, setAction] = useState("All");
  const [result, setResult] = useState("All");
  const [sort, setSort] = useState("newest");
  const [editing, setEditing] = useState<Trade | null>(null);
  const [error, setError] = useState("");
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: portfolioApi.accounts, enabled: Boolean(user) });
  const tradingAccounts = (accounts.data || []).filter((account) => account.type === "Trading Account");
  const selectedAccount = tradingAccounts.find((account) => account.name === selected);
  const trades = useQuery({ queryKey: ["trades", selected], queryFn: () => portfolioApi.trades(selected), enabled: Boolean(user && selected) });
  const summary = useQuery({
    queryKey: ["journal-summary", selected],
    queryFn: () => portfolioApi.journalSummary(selected),
    enabled: Boolean(user && selected)
  });

  useEffect(() => {
    if (!selected && tradingAccounts.length) setSelected(tradingAccounts[0].name);
  }, [selected, tradingAccounts]);

  useEffect(() => {
    if (selected && accounts.isSuccess && !selectedAccount) {
      setSelected(tradingAccounts[0]?.name || "");
    }
  }, [accounts.isSuccess, selected, selectedAccount, tradingAccounts]);

  const filtered = useMemo(() => {
    const rows = [...(trades.data || [])].filter((trade) => {
      if (search && !trade.symbol.toLowerCase().includes(search.toLowerCase())) return false;
      if (action !== "All" && trade.action !== action) return false;
      if (result === "profit" && trade.pnl <= 0) return false;
      if (result === "loss" && trade.pnl >= 0) return false;
      if (result === "flat" && trade.pnl !== 0) return false;
      return true;
    });
    return rows.sort((a, b) => {
      if (sort === "oldest") return a.trade_time.localeCompare(b.trade_time);
      if (sort === "pnl-high") return b.pnl - a.pnl;
      if (sort === "pnl-low") return a.pnl - b.pnl;
      return b.trade_time.localeCompare(a.trade_time);
    });
  }, [trades.data, search, action, result, sort]);

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["trades", selected] });
    await queryClient.invalidateQueries({ queryKey: ["journal-summary", selected] });
    await queryClient.invalidateQueries({ queryKey: ["dashboard", selected] });
  };
  const remove = useMutation({
    mutationFn: portfolioApi.deleteTrade,
    onSuccess: invalidate,
    onError: (requestError) => setError(getApiError(requestError))
  });
  const update = useMutation({
    mutationFn: portfolioApi.updateTrade,
    onSuccess: async () => { setEditing(null); await invalidate(); },
    onError: (requestError) => setError(getApiError(requestError))
  });

  if (!user) return <EmptyState title="Authentication required" body="Sign in to review and manage your trade history." />;
  if (accounts.isSuccess && !tradingAccounts.length) {
    return (
      <EmptyState
        title="Trading account required"
        body="The journal is available only for Trading Accounts. Create one from the dashboard to start recording trades."
      />
    );
  }

  return (
    <div className="page">
      <section className="page-toolbar">
        <div><p className="eyebrow">Execution record</p><h1>Trade journal</h1></div>
        <AccountSelector accounts={tradingAccounts} value={selected} onChange={setSelected} />
      </section>
      <MetricStrip metrics={[
        { label: "Total entries", value: String(summary.data?.total_entries || 0) },
        { label: "Closed trades", value: String(summary.data?.trade_count || 0) },
        { label: "Net P&L", value: money(summary.data?.realised_pnl, selectedAccount?.currency), tone: (summary.data?.realised_pnl || 0) >= 0 ? "positive" : "negative" },
        { label: "Win rate", value: `${(summary.data?.win_rate || 0).toFixed(1)}%` },
        { label: "Average trade", value: money(summary.data?.average_trade, selectedAccount?.currency) }
      ]} />
      <section className="panel">
        <div className="section-heading"><div><p className="eyebrow">History</p><h2>{filtered.length} ledger entries</h2></div></div>
        <div className="filter-row">
          <input placeholder="Search symbol" value={search} onChange={(event) => setSearch(event.target.value)} />
          <select value={action} onChange={(event) => setAction(event.target.value)}>
            <option>All</option><option>Trade</option><option>Deposit</option><option>Withdraw</option>
          </select>
          <select value={result} onChange={(event) => setResult(event.target.value)}>
            <option value="All">All results</option><option value="profit">Profitable</option><option value="loss">Losing</option><option value="flat">Break-even</option>
          </select>
          <select value={sort} onChange={(event) => setSort(event.target.value)}>
            <option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="pnl-high">P&L highest</option><option value="pnl-low">P&L lowest</option>
          </select>
        </div>
        {error && <p className="form-error">{error}</p>}
        <div className="table-wrap">
          <table>
            <thead><tr><th>Date</th><th>Action</th><th>Direction</th><th>Symbol</th><th>P&L</th><th /></tr></thead>
            <tbody>
              {filtered.map((trade) => (
                <tr key={trade.id}>
                  <td>{trade.trade_time.slice(0, 10)}</td><td>{trade.action}</td><td>{trade.type || "—"}</td>
                  <td className="symbol">{trade.symbol}</td>
                  <td className={trade.pnl >= 0 ? "positive" : "negative"}>{trade.pnl > 0 ? "+" : ""}{money(trade.pnl, selectedAccount?.currency)}</td>
                  <td className="row-actions">
                    <button className="icon-button" onClick={() => setEditing(trade)}><Pencil size={15} /></button>
                    <button className="icon-button danger-icon" onClick={() => remove.mutate(trade.id)}><Trash2 size={15} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {editing && (
        <div className="modal-backdrop">
          <form
            className="modal stack"
            onSubmit={(event) => {
              event.preventDefault();
              update.mutate({
                ...editing,
                trade_time: editing.trade_time.slice(0, 10),
                symbol: editing.action === "Trade" ? editing.symbol : "CASH",
                type: editing.action === "Trade" ? editing.type || "Long" : undefined,
                pnl: editing.action === "Withdraw" ? -Math.abs(editing.pnl) : editing.pnl
              });
            }}
          >
            <button type="button" className="icon-button modal-close" onClick={() => setEditing(null)}><X size={18} /></button>
            <p className="eyebrow">Edit entry</p><h2>{editing.symbol}</h2>
            <label>Date<input type="date" value={editing.trade_time.slice(0, 10)} onChange={(e) => setEditing({ ...editing, trade_time: e.target.value })} /></label>
            <label>Action<select value={editing.action} onChange={(e) => setEditing({ ...editing, action: e.target.value as Trade["action"] })}><option>Trade</option><option>Deposit</option><option>Withdraw</option></select></label>
            {editing.action === "Trade" && (
              <>
                <label>Direction<select value={editing.type || "Long"} onChange={(e) => setEditing({ ...editing, type: e.target.value })}><option>Long</option><option>Short</option></select></label>
                <label>Symbol<input value={editing.symbol} onChange={(e) => setEditing({ ...editing, symbol: e.target.value.toUpperCase() })} /></label>
              </>
            )}
            <label>P&L<input type="number" step="0.01" value={editing.pnl} onChange={(e) => setEditing({ ...editing, pnl: Number(e.target.value) })} /></label>
            <button className="button primary">Save changes</button>
          </form>
        </div>
      )}
    </div>
  );
}
