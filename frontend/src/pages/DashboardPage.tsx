import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Download,
  MoreHorizontal,
  Plus,
  Sparkles,
  Target,
  Trash2,
  TrendingDown,
  TrendingUp,
  WalletCards,
  X
} from "lucide-react";

import { getApiError } from "../api/client";
import { portfolioApi } from "../api/queries";
import { AccountSelector } from "../components/AccountSelector";
import { BalanceLineChart } from "../components/BalanceLineChart";
import { DailyPnlCalendar } from "../components/DailyPnlCalendar";
import { EmptyState } from "../components/EmptyState";
import { MonthlyPerformanceChart } from "../components/MonthlyPerformanceChart";
import { useAuth } from "../features/auth/AuthProvider";
import { CreateAccountForm } from "../features/dashboard/CreateAccountForm";
import { RiskCalculator } from "../features/dashboard/RiskCalculator";
import { TradeForm } from "../features/dashboard/TradeForm";
import type {
  Account,
  CurrencyCode,
  DashboardSummary,
  Trade
} from "../types";

type TradePayload = Parameters<typeof portfolioApi.createTrade>[0];

function money(value = 0, currency: CurrencyCode = "EUR", sign = false) {
  const formatted = new Intl.NumberFormat("en-US", { style: "currency", currency }).format(value);
  return sign && value > 0 ? `+${formatted}` : formatted;
}

function toDay(value: string) {
  const date = new Date(value);
  date.setUTCHours(0, 0, 0, 0);
  return date;
}

function chartSeries(points: DashboardSummary["equity_curve"]) {
  if (points.length !== 1) return points;
  const start = toDay(points[0].date);
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return [
    { ...points[0], date: start.toISOString() },
    { ...points[0], date: end.toISOString() }
  ];
}

function isoDay(value: string) {
  return value.slice(0, 10);
}

function previousDate(value: string, days: number) {
  const date = toDay(value);
  date.setDate(date.getDate() - days + 1);
  return date.toISOString().slice(0, 10);
}

function filterChartPoints(points: DashboardSummary["equity_curve"], startDate: string, endDate: string) {
  if (!startDate || !endDate) return points;
  return points.filter((point) => {
    const day = isoDay(point.date);
    return day >= startDate && day <= endDate;
  });
}

type PerformancePeriod = 7 | 30 | 90 | 180 | 0;

const PERIODS: Array<{ days: PerformancePeriod; label: string }> = [
  { days: 7, label: "7 Days" },
  { days: 30, label: "1 Month" },
  { days: 90, label: "3 Months" },
  { days: 180, label: "6 Months" },
  { days: 0, label: "All" }
];

function tradesInRange(transactions: Trade[], startDate: string, endDate: string) {
  return transactions.filter((trade) => {
    const day = isoDay(trade.trade_time);
    return trade.action === "Trade" && (!startDate || day >= startDate) && (!endDate || day <= endDate);
  });
}

function downloadEquityReport(account: string, currency: CurrencyCode, points: DashboardSummary["equity_curve"]) {
  const rows = ["date,balance,currency", ...points.map((point) => `${isoDay(point.date)},${point.balance},${currency}`)];
  const url = URL.createObjectURL(new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${account.toLowerCase().replaceAll(" ", "-")}-equity.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function PerformanceWorkspace({
  summary,
  title,
  emptyBody,
  transactions
}: {
  readonly summary?: DashboardSummary;
  readonly title: string;
  readonly emptyBody: string;
  readonly transactions?: Trade[];
}) {
  const rawPoints = chartSeries(summary?.equity_curve || []);
  const firstDay = rawPoints[0] ? isoDay(rawPoints[0].date) : "";
  const lastDay = rawPoints.at(-1) ? isoDay(rawPoints.at(-1)!.date) : "";
  const [period, setPeriod] = useState<PerformancePeriod | "custom">(30);
  const selectedStart = typeof period === "number" && period && lastDay ? previousDate(lastDay, period) : firstDay;
  const [customRange, setCustomRange] = useState({ end: lastDay, start: selectedStart });
  useEffect(() => {
    setPeriod(30);
    setCustomRange({ end: lastDay, start: lastDay ? previousDate(lastDay, 30) : firstDay });
  }, [firstDay, lastDay]);
  const points = filterChartPoints(rawPoints, customRange.start, customRange.end);
  const periodTrades = tradesInRange(transactions || [], customRange.start, customRange.end);
  const hasTransactionData = transactions !== undefined;
  const endingBalance = points.at(-1)?.balance ?? summary?.balance ?? 0;
  const startingBalance = points[0]?.balance ?? endingBalance;
  const performance = startingBalance
    ? (endingBalance - startingBalance) / Math.abs(startingBalance) * 100
    : 0;
  const winningTrades = periodTrades.filter((trade) => trade.pnl > 0).length;
  const winRate = hasTransactionData
    ? periodTrades.length ? winningTrades / periodTrades.length * 100 : 0
    : summary?.win_rate || 0;
  const realisedTradePnl = hasTransactionData
    ? periodTrades.reduce((sum, trade) => sum + trade.pnl, 0)
    : summary?.realised_pnl || 0;
  const periodLabel = period === "custom"
    ? "Custom date range"
    : PERIODS.find((item) => item.days === period)?.label || "Selected period";
  const selectPeriod = (days: PerformancePeriod) => {
    setPeriod(days);
    setCustomRange({ end: lastDay, start: days ? previousDate(lastDay, days) : firstDay });
  };
  const metrics = [
    { detail: `${summary?.currency || "EUR"} live equity`, icon: <WalletCards size={15} />, label: "Portfolio value", value: money(endingBalance, summary?.currency) },
    { detail: `${hasTransactionData ? periodTrades.length : summary?.trade_count || 0} trades · ${periodLabel.toLowerCase()} · cash flow excluded`, icon: realisedTradePnl >= 0 ? <TrendingUp size={15} /> : <TrendingDown size={15} />, label: "Realized trade P&L", tone: realisedTradePnl >= 0 ? "positive" : "negative", value: money(realisedTradePnl, summary?.currency, true) },
    { detail: `${winningTrades} of ${periodTrades.length || summary?.trade_count || 0} closed trades`, icon: <Target size={15} />, label: "Win rate", value: `${winRate.toFixed(1)}%` },
    { detail: `${periodLabel} equity return`, icon: performance >= 0 ? <TrendingUp size={15} /> : <TrendingDown size={15} />, label: "Performance", tone: performance >= 0 ? "positive" : "negative", value: `${performance >= 0 ? "+" : ""}${performance.toFixed(2)}%` }
  ];
  return (
    <section className="performance-workspace">
      <header className="performance-toolbar">
        <div className="period-switcher" aria-label="Performance period">
          {PERIODS.map((item) => (
            <button className={period === item.days ? "active" : ""} key={item.label} onClick={() => selectPeriod(item.days)} type="button">
              {item.label}
            </button>
          ))}
        </div>
        <div className="performance-actions">
          <span className="workspace-status"><i /> Live ledger</span>
          <button className="button secondary report-button" disabled={!points.length} onClick={() => downloadEquityReport(title, summary?.currency || "EUR", points)} type="button">
            <Download size={15} /> Download report
          </button>
          <button aria-label="More performance options" className="icon-button" type="button"><MoreHorizontal size={17} /></button>
        </div>
      </header>
      <div className="performance-metrics">
        {metrics.map((metric) => (
          <article key={metric.label}>
            <span>{metric.icon}{metric.label}</span>
            <strong className={metric.tone || "neutral"}>{metric.value}</strong>
            <small>{metric.detail}</small>
          </article>
        ))}
      </div>
      {points.length ? (
        <div className="performance-chart-area">
          <div className="performance-chart-heading">
            <div>
              <p className="eyebrow">Equity curve</p>
              <h2>{title}</h2>
            </div>
            <div className="balance-date-fields">
              <label>
                <span>From</span>
                <input
                  max={customRange.end || lastDay}
                  min={firstDay}
                  onChange={(event) => { setPeriod("custom"); setCustomRange((current) => ({ ...current, start: event.target.value })); }}
                  type="date"
                  value={customRange.start}
                />
              </label>
              <label>
                <span>To</span>
                <input
                  max={lastDay}
                  min={customRange.start || firstDay}
                  onChange={(event) => { setPeriod("custom"); setCustomRange((current) => ({ ...current, end: event.target.value })); }}
                  type="date"
                  value={customRange.end}
                />
              </label>
            </div>
          </div>
          <BalanceLineChart currency={summary?.currency || "EUR"} points={points} />
          <div className="balance-chart-note">
            <span>Scroll axes to scale · drag to inspect · double-click to reset</span>
            <span>{points.length} daily observations</span>
          </div>
        </div>
      ) : (
        <EmptyState title="No ledger entries" body={emptyBody} />
      )}
    </section>
  );
}

function monthlyPnlStats(equityCurve: DashboardSummary["equity_curve"], transactions: Trade[]) {
  const months = new Set(equityCurve.map((point) => isoDay(point.date).slice(0, 7)));
  const rows = new Map<string, { trades: number; value: number }>();
  transactions.filter((transaction) => transaction.action === "Trade").forEach((transaction) => {
    const month = isoDay(transaction.trade_time).slice(0, 7);
    const row = rows.get(month) || { trades: 0, value: 0 };
    row.trades += 1;
    row.value += transaction.pnl;
    rows.set(month, row);
    months.add(month);
  });
  return [...months].sort().map((month) => ({ month, ...(rows.get(month) || { trades: 0, value: 0 }) }));
}

function MonthlyStatsPanel({
  currency,
  equityCurve,
  transactions
}: {
  readonly currency: CurrencyCode;
  readonly equityCurve: DashboardSummary["equity_curve"];
  readonly transactions: Trade[];
}) {
  const [range, setRange] = useState<3 | 6 | 12 | 0>(6);
  const monthlyRows = monthlyPnlStats(equityCurve, transactions);
  const visibleRows = range ? monthlyRows.slice(-range) : monthlyRows;
  return (
    <section className="panel monthly-stats-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Monthly P&L</p>
          <h2>Realized trading performance</h2>
          <p className="muted-copy">Closed-trade profit and loss by month. Deposits and withdrawals are excluded.</p>
        </div>
        <div aria-label="Monthly performance range" className="monthly-range-switcher">
          {([{ label: "3M", value: 3 }, { label: "6M", value: 6 }, { label: "1Y", value: 12 }, { label: "All", value: 0 }] as const).map((item) => (
            <button className={range === item.value ? "active" : ""} key={item.label} onClick={() => setRange(item.value)} type="button">{item.label}</button>
          ))}
        </div>
      </div>
      {visibleRows.length ? (
        <MonthlyPerformanceChart currency={currency} points={visibleRows} />
      ) : (
        <EmptyState title="Monthly performance unavailable" body="Closed trades will create monthly profit and loss columns here." />
      )}
    </section>
  );
}

function tradingIntelligence(transactions: Trade[]) {
  const trades = transactions.filter((transaction) => transaction.action === "Trade");
  const wins = trades.filter((trade) => trade.pnl > 0);
  const losses = trades.filter((trade) => trade.pnl < 0);
  const breakEven = trades.length - wins.length - losses.length;
  const grossProfit = wins.reduce((sum, trade) => sum + trade.pnl, 0);
  const grossLoss = Math.abs(losses.reduce((sum, trade) => sum + trade.pnl, 0));
  const symbols = new Map<string, { pnl: number; trades: number }>();
  trades.forEach((trade) => {
    const symbol = trade.symbol || "Other";
    const current = symbols.get(symbol) || { pnl: 0, trades: 0 };
    current.pnl += trade.pnl;
    current.trades += 1;
    symbols.set(symbol, current);
  });
  return {
    averageLoss: losses.length ? grossLoss / losses.length : 0,
    averageWin: wins.length ? grossProfit / wins.length : 0,
    breakEven,
    expectancy: trades.length ? (grossProfit - grossLoss) / trades.length : 0,
    losses: losses.length,
    profitFactor: grossLoss ? grossProfit / grossLoss : grossProfit > 0 ? Number.POSITIVE_INFINITY : 0,
    recent: [...trades].sort((a, b) => b.trade_time.localeCompare(a.trade_time)).slice(0, 5),
    symbols: [...symbols.entries()]
      .map(([symbol, value]) => ({ symbol, ...value }))
      .sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl))
      .slice(0, 4),
    total: trades.length,
    wins: wins.length
  };
}

function TradingIntelligence({ currency, transactions }: { readonly currency: CurrencyCode; readonly transactions: Trade[] }) {
  const insight = tradingIntelligence(transactions);
  const winShare = insight.total ? insight.wins / insight.total * 100 : 0;
  const lossShare = insight.total ? insight.losses / insight.total * 100 : 0;
  const maxSymbolPnl = Math.max(...insight.symbols.map((symbol) => Math.abs(symbol.pnl)), 1);
  const donutBackground = `conic-gradient(var(--green) 0 ${winShare}%, var(--red) ${winShare}% ${winShare + lossShare}%, #313b4b ${winShare + lossShare}% 100%)`;
  return (
    <section className="intelligence-suite">
      <header className="intelligence-heading">
        <div>
          <p className="eyebrow">Trading intelligence</p>
          <h2>What is driving performance</h2>
        </div>
        <span><Sparkles size={14} /> Calculated from {insight.total} closed trades</span>
      </header>
      <div className="intelligence-grid">
        <article className="outcome-panel">
          <div className="insight-title"><span>Outcome mix</span><Activity size={15} /></div>
          <div className="outcome-content">
            <div aria-label={`${insight.wins} wins, ${insight.losses} losses, ${insight.breakEven} break-even`} className="outcome-donut" style={{ background: donutBackground }}>
              <span><strong>{insight.total}</strong><small>trades</small></span>
            </div>
            <dl className="outcome-legend">
              <div><dt><i className="gain" /> Wins</dt><dd>{insight.wins}</dd></div>
              <div><dt><i className="loss" /> Losses</dt><dd>{insight.losses}</dd></div>
              <div><dt><i className="flat" /> Flat</dt><dd>{insight.breakEven}</dd></div>
            </dl>
          </div>
        </article>
        <article className="edge-panel">
          <div className="insight-title"><span>Edge quality</span><Target size={15} /></div>
          <dl className="edge-metrics">
            <div><dt>Profit factor</dt><dd>{Number.isFinite(insight.profitFactor) ? `${insight.profitFactor.toFixed(2)}x` : "∞"}</dd></div>
            <div><dt>Expectancy</dt><dd className={insight.expectancy >= 0 ? "positive" : "negative"}>{money(insight.expectancy, currency, true)}</dd></div>
            <div><dt>Average win</dt><dd className="positive">{money(insight.averageWin, currency, true)}</dd></div>
            <div><dt>Average loss</dt><dd className="negative">-{money(insight.averageLoss, currency)}</dd></div>
          </dl>
        </article>
        <article className="symbol-panel">
          <div className="insight-title"><span>Symbol contribution</span><TrendingUp size={15} /></div>
          <div className="symbol-breakdown">
            {insight.symbols.length ? insight.symbols.map((item) => (
              <div key={item.symbol}>
                <span><strong>{item.symbol}</strong><small>{item.trades} trades</small></span>
                <div><i className={item.pnl >= 0 ? "gain" : "loss"} style={{ width: `${Math.max(Math.abs(item.pnl) / maxSymbolPnl * 100, 4)}%` }} /></div>
                <b className={item.pnl >= 0 ? "positive" : "negative"}>{money(item.pnl, currency, true)}</b>
              </div>
            )) : <p className="muted-copy">Symbol contribution appears after the first closed trade.</p>}
          </div>
        </article>
        <article className="activity-panel">
          <div className="insight-title"><span>Recent executions</span><span className="live-label"><i /> Live</span></div>
          <div className="recent-executions">
            {insight.recent.length ? insight.recent.map((trade) => (
              <div key={trade.id}>
                <span className={`execution-direction ${trade.type?.toLowerCase() === "short" ? "short" : "long"}`}>{trade.type?.slice(0, 1) || "T"}</span>
                <span><strong>{trade.symbol}</strong><small>{isoDay(trade.trade_time)} · {trade.type || "Trade"}</small></span>
                <b className={trade.pnl >= 0 ? "positive" : "negative"}>{money(trade.pnl, currency, true)}</b>
              </div>
            )) : <p className="muted-copy">Recent executions will appear here.</p>}
          </div>
        </article>
      </div>
    </section>
  );
}

interface AccountViewProps {
  account: Account;
  summary?: DashboardSummary;
  transactions: Trade[];
  createEntry: (payload: TradePayload) => void;
  entryPending: boolean;
}

function AccountView({
  account,
  summary,
  transactions,
  createEntry,
  entryPending
}: AccountViewProps) {
  const balance = summary?.balance ?? account.starting_balance;
  return (
    <>
      <PerformanceWorkspace
        summary={summary}
        title="Balance through time"
        emptyBody="Add a transaction to start building this account history."
        transactions={transactions}
      />
      <TradingIntelligence currency={account.currency} transactions={transactions} />
      <section className="dashboard-journal-grid">
        <DailyPnlCalendar
          currency={account.currency}
          points={summary?.daily_pnl || []}
        />
        <section className="panel trade-ticket">
          <div className="section-heading trade-ticket-heading">
            <div><p className="eyebrow">Quick entry</p><h2>Log action</h2></div>
            <span className="trade-ticket-status"><i /> Ready</span>
          </div>
          <TradeForm account={account.name} busy={entryPending} onSubmit={createEntry} />
        </section>
      </section>
      <section className="dashboard-secondary-grid">
        <MonthlyStatsPanel currency={account.currency} equityCurve={summary?.equity_curve || []} transactions={transactions} />
        <RiskCalculator currency={account.currency} initialBalance={balance} />
      </section>
    </>
  );
}

function TotalView({
  accounts,
  summary,
  deletePending,
  onDelete
}: {
  readonly accounts: Account[];
  readonly summary?: DashboardSummary;
  readonly deletePending: boolean;
  readonly onDelete: (name: string) => void;
}) {
  const [accountToDelete, setAccountToDelete] = useState<Account | null>(null);
  const accountBalances = summary?.accounts?.length
    ? summary.accounts
    : accounts
        .filter((account) => account.currency === summary?.currency)
        .map((account) => ({ ...account, balance: account.starting_balance }));
  if (!accounts.length) {
    return (
      <EmptyState
        title="Create your first account"
        body="Add a trading account to start tracking your portfolio."
      />
    );
  }
  return (
    <>
      <PerformanceWorkspace
        summary={summary}
        title="Total balance through time"
        emptyBody="Transactions from every account in this currency will appear here."
      />
      <section className="panel account-overview">
        <div className="section-heading">
          <div><p className="eyebrow">Portfolio</p><h2>Accounts in {summary?.currency}</h2></div>
        </div>
        <div className="account-ledger">
          {accountBalances.map((accountBalance) => (
            <div key={accountBalance.name}>
              <span><strong>{accountBalance.name}</strong><small>{accountBalance.type}</small></span>
              <span className="account-ledger-actions">
                <span>{money(accountBalance.balance, accountBalance.currency)}</span>
                <button
                  aria-label={`Delete ${accountBalance.name}`}
                  className="icon-button danger-icon"
                  onClick={() => {
                    const account = accounts.find((item) => item.name === accountBalance.name);
                    if (account) setAccountToDelete(account);
                  }}
                  type="button"
                >
                  <Trash2 size={16} />
                </button>
              </span>
            </div>
          ))}
        </div>
      </section>
      {accountToDelete && (
        <div className="modal-backdrop">
          <section aria-labelledby="delete-account-title" aria-modal="true" className="modal" role="dialog">
            <button
              aria-label="Close delete account dialog"
              className="icon-button modal-close"
              onClick={() => setAccountToDelete(null)}
              type="button"
            >
              <X size={18} />
            </button>
            <p className="eyebrow">Delete account</p>
            <h2 id="delete-account-title">{accountToDelete.name}</h2>
            <p className="muted-copy">
              This permanently deletes the account, its transactions, recurring schedules, and related portfolio data.
            </p>
            <div className="confirmation-actions">
              <button className="button secondary" onClick={() => setAccountToDelete(null)} type="button">
                Cancel
              </button>
              <button
                className="button danger"
                disabled={deletePending}
                onClick={() => {
                  onDelete(accountToDelete.name);
                  setAccountToDelete(null);
                }}
                type="button"
              >
                Delete account
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}

function AllAccountsView({
  accounts,
  summaries,
  deletePending,
  onDelete
}: {
  readonly accounts: Account[];
  readonly summaries: DashboardSummary[];
  readonly deletePending: boolean;
  readonly onDelete: (name: string) => void;
}) {
  if (!accounts.length) {
    return (
      <EmptyState
        title="Create your first account"
        body="Add a trading account to start tracking your portfolio."
      />
    );
  }
  if (!summaries.length) {
    return <p className="muted-copy">Loading portfolio balances...</p>;
  }

  return (
    <>
      {summaries.map((summary) => (
        <section className="currency-portfolio" key={summary.currency}>
          <TotalView
            accounts={accounts}
            deletePending={deletePending}
            onDelete={onDelete}
            summary={summary}
          />
        </section>
      ))}
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
  const availableCurrencies = useMemo(
    () => [...new Set((accounts.data || []).map((item) => item.currency))].sort(),
    [accounts.data]
  );
  const accountSummary = useQuery({
    queryKey: ["dashboard", selected],
    queryFn: () => portfolioApi.dashboard(selected),
    enabled: Boolean(user && selected)
  });
  const totalSummaries = useQueries({
    queries: availableCurrencies.map((currency) => ({
      queryKey: ["dashboard", "total", currency],
      queryFn: () => portfolioApi.totalDashboard(currency),
      enabled: Boolean(user && !selected)
    }))
  });
  const transactions = useQuery({
    queryKey: ["trades", selected],
    queryFn: () => portfolioApi.trades(selected),
    enabled: Boolean(user && selected)
  });

  useEffect(() => {
    if (selected && accounts.isSuccess && !account) {
      setSelected("");
    }
  }, [account, accounts.isSuccess, selected]);

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      queryClient.invalidateQueries({ queryKey: ["trades", selected] }),
      queryClient.invalidateQueries({ queryKey: ["journal-summary", selected] })
    ]);
  };
  const mutationError = (requestError: unknown) => setError(getApiError(requestError));
  const createAccount = useMutation({
    mutationFn: portfolioApi.createAccount,
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setSelected(created.name);
      setShowAccountForm(false);
    },
    onError: mutationError
  });
  const deleteAccount = useMutation({
    mutationFn: portfolioApi.deleteAccount,
    onSuccess: async (_, deletedName) => {
      if (selected === deletedName) setSelected("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["accounts"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
        queryClient.invalidateQueries({ queryKey: ["trades"] })
      ]);
    },
    onError: mutationError
  });
  const createEntry = useMutation({ mutationFn: portfolioApi.createTrade, onSuccess: refresh, onError: mutationError });
  if (!user) {
    return <EmptyState title="Authentication required" body="Sign in from the account menu to access your portfolio." />;
  }

  const summary = selected ? accountSummary.data : undefined;
  const aggregateSummaries = totalSummaries
    .map((query) => query.data)
    .filter((item): item is DashboardSummary => Boolean(item));
  return (
    <div className="page">
      <section className="page-toolbar dashboard-commandbar">
        <div className="dashboard-title-block">
          <p className="eyebrow">Portfolio workspace</p>
          <h1>{account?.name || "All accounts"}</h1>
          <p className="page-subtitle">
            {account ? `${account.type} · ${account.currency}` : "Combined balances grouped by currency"}
          </p>
        </div>
        <div className="toolbar-actions">
          <span className="workspace-status"><i /> Live data</span>
          <AccountSelector accounts={accounts.data || []} includeAll value={selected} onChange={setSelected} />
          <button className="button secondary" onClick={() => setShowAccountForm((value) => !value)}>
            <Plus size={16} /> New account
          </button>
        </div>
      </section>
      {showAccountForm && (
        <section className="panel reveal">
          <CreateAccountForm busy={createAccount.isPending} onCreate={(payload) => createAccount.mutate(payload)} />
        </section>
      )}
      {error && <p className="form-error">{error}</p>}
      {account ? (
        <AccountView
          account={account}
          createEntry={(payload) => createEntry.mutate(payload)}
          entryPending={createEntry.isPending}
          summary={summary}
          transactions={transactions.data || []}
        />
      ) : (
        <AllAccountsView
          accounts={accounts.data || []}
          deletePending={deleteAccount.isPending}
          onDelete={(name) => deleteAccount.mutate(name)}
          summaries={aggregateSummaries}
        />
      )}
    </div>
  );
}
