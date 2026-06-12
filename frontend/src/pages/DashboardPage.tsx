import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { getApiError } from "../api/client";
import { portfolioApi } from "../api/queries";
import { AccountSelector } from "../components/AccountSelector";
import { EmptyState } from "../components/EmptyState";
import { MetricStrip } from "../components/MetricStrip";
import { Plot } from "../components/Plot";
import { AssetsPanel } from "../features/dashboard/AssetsPanel";
import { CreateAccountForm } from "../features/dashboard/CreateAccountForm";
import { RiskCalculator } from "../features/dashboard/RiskCalculator";
import { TradeForm } from "../features/dashboard/TradeForm";
import { useAuth } from "../features/auth/AuthProvider";
import type { Account, Asset, DashboardSummary } from "../types";

const money = (value = 0, sign = false) =>
  `${sign && value > 0 ? "+" : ""}${new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD"
  }).format(value)}`;

type TradePayload = Parameters<typeof portfolioApi.createTrade>[0];

interface AccountContentProps {
  selected: string;
  account?: Account;
  accounts: Account[];
  assets: Asset[];
  summary?: DashboardSummary;
  createAsset: (payload: Omit<Asset, "id" | "created_at">) => void;
  deleteAsset: (id: string) => void;
  createTrade: (payload: TradePayload) => void;
  createAssetPending: boolean;
  createTradePending: boolean;
  setSelected: (value: string) => void;
}

function accountContent({
  selected,
  account,
  accounts,
  assets,
  summary,
  createAsset,
  deleteAsset,
  createTrade,
  createAssetPending,
  createTradePending,
  setSelected
}: AccountContentProps) {
  if (!selected) {
    return (
      <EmptyState
        title="Create your first account"
        body="Accounts separate trading, investing, banking, and overall portfolio views."
      />
    );
  }
  if (account?.type === "Investing") {
    return (
      <AssetsPanel
        account={selected}
        assets={assets}
        onCreate={createAsset}
        onDelete={deleteAsset}
        busy={createAssetPending}
      />
    );
  }
  if (account?.type === "Overall") {
    return (
      <section className="panel">
        <p className="eyebrow">Account overview</p>
        <h2>All portfolio accounts</h2>
        <div className="account-ledger">
          {accounts.filter((item) => item.type !== "Overall").map((item) => (
            <button key={item.name} onClick={() => setSelected(item.name)}>
              <span><strong>{item.name}</strong><small>{item.type}</small></span>
              <span>{money(item.starting_balance)}</span>
            </button>
          ))}
        </div>
      </section>
    );
  }
  const hasEquityCurve = Boolean(summary?.equity_curve.length);
  const balance = summary?.balance || account?.starting_balance || 0;
  return (
    <>
      <MetricStrip
        metrics={[
          { label: "Account balance", value: money(summary?.balance) },
          {
            label: "Realised P&L",
            value: money(summary?.realised_pnl, true),
            detail: `${summary?.trade_count || 0} closed trades`,
            tone: (summary?.realised_pnl || 0) >= 0 ? "positive" : "negative"
          },
          { label: "Win rate", value: `${(summary?.win_rate || 0).toFixed(1)}%`, detail: `${summary?.winning_trades || 0} wins` },
          { label: "Average trade", value: money(summary?.average_trade, true), detail: `Best ${money(summary?.best_trade)}` }
        ]}
      />
      <section className="split-layout main-split">
        <div className="panel chart-panel">
          <div className="section-heading">
            <div><p className="eyebrow">Performance</p><h2>Balance through time</h2></div>
            <span className="live-label"><i /> Live ledger</span>
          </div>
          {hasEquityCurve ? (
            <Plot
              data={[{
                x: summary!.equity_curve.map((point) => point.date),
                y: summary!.equity_curve.map((point) => point.balance),
                type: "scatter",
                mode: "lines",
                line: { color: "#19d492", width: 2, shape: "spline" },
                fill: "tozeroy",
                fillcolor: "rgba(25,212,146,.08)",
                hovertemplate: "%{x|%d %b %Y}<br><b>$%{y:,.2f}</b><extra></extra>"
              }]}
              layout={{
                autosize: true, height: 360, margin: { l: 58, r: 12, t: 20, b: 40 },
                paper_bgcolor: "transparent", plot_bgcolor: "transparent",
                font: { color: "#7e899f", family: "IBM Plex Mono" },
                xaxis: { gridcolor: "#1b2230" },
                yaxis: { gridcolor: "#1b2230", tickprefix: "$" },
                showlegend: false
              }}
              config={{ displayModeBar: false, responsive: true }}
              useResizeHandler
              style={{ width: "100%" }}
            />
          ) : (
            <EmptyState title="No ledger entries" body="Log a trade, deposit, or withdrawal to build the equity curve." />
          )}
        </div>
        <div className="panel">
          <p className="eyebrow">Ledger</p>
          <h2>Log action</h2>
          <TradeForm
            account={selected}
            onSubmit={createTrade}
            busy={createTradePending}
          />
        </div>
      </section>
      {account?.type === "Trading" && <RiskCalculator initialBalance={balance} />}
    </>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState("");
  const [showAccountForm, setShowAccountForm] = useState(false);
  const [error, setError] = useState("");
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: portfolioApi.accounts, enabled: Boolean(user) });
  const account = accounts.data?.find((item) => item.name === selected);
  const summary = useQuery({
    queryKey: ["dashboard", selected],
    queryFn: () => portfolioApi.dashboard(selected),
    enabled: Boolean(user && selected && account?.type !== "Investing" && account?.type !== "Overall")
  });
  const assets = useQuery({
    queryKey: ["assets", selected],
    queryFn: () => portfolioApi.assets(selected),
    enabled: Boolean(user && selected && account?.type === "Investing")
  });

  useEffect(() => {
    if (!selected && accounts.data?.length) setSelected(accounts.data[0].name);
  }, [accounts.data, selected]);

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["dashboard", selected] });
    await queryClient.invalidateQueries({ queryKey: ["trades", selected] });
  };

  const createAccount = useMutation({
    mutationFn: portfolioApi.createAccount,
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setSelected(created.name);
      setShowAccountForm(false);
    },
    onError: (requestError) => setError(getApiError(requestError))
  });
  const createTrade = useMutation({ mutationFn: portfolioApi.createTrade, onSuccess: refresh, onError: (e) => setError(getApiError(e)) });
  const createAsset = useMutation({
    mutationFn: portfolioApi.createAsset,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets", selected] }),
    onError: (e) => setError(getApiError(e))
  });
  const deleteAsset = useMutation({
    mutationFn: portfolioApi.deleteAsset,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets", selected] }),
    onError: (e) => setError(getApiError(e))
  });

  if (!user) return <EmptyState title="Authentication required" body="Sign in from the account menu to access your portfolio." />;

  return (
    <div className="page">
      <section className="page-toolbar">
        <div>
          <p className="eyebrow">Portfolio workspace</p>
          <h1>{account?.name || "Dashboard"}</h1>
        </div>
        <div className="toolbar-actions">
          <AccountSelector accounts={accounts.data || []} value={selected} onChange={setSelected} />
          <button className="button secondary" onClick={() => setShowAccountForm((value) => !value)}>
            <Plus size={16} /> New account
          </button>
        </div>
      </section>
      {showAccountForm && (
        <section className="panel reveal">
          <CreateAccountForm onCreate={(payload) => createAccount.mutate(payload)} busy={createAccount.isPending} />
        </section>
      )}
      {error && <p className="form-error">{error}</p>}
      {accountContent({
        selected,
        account,
        accounts: accounts.data || [],
        assets: assets.data || [],
        summary: summary.data,
        createAsset: (payload) => createAsset.mutate(payload),
        deleteAsset: (id) => deleteAsset.mutate(id),
        createTrade: (payload) => createTrade.mutate(payload),
        createAssetPending: createAsset.isPending,
        createTradePending: createTrade.isPending,
        setSelected
      })}
    </div>
  );
}
