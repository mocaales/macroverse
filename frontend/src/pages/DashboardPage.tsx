import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, X } from "lucide-react";

import { getApiError } from "../api/client";
import { portfolioApi } from "../api/queries";
import { AccountSelector } from "../components/AccountSelector";
import { BalanceLineChart } from "../components/BalanceLineChart";
import { EmptyState } from "../components/EmptyState";
import { MetricStrip } from "../components/MetricStrip";
import { useAuth } from "../features/auth/AuthProvider";
import { CashTransactionForm } from "../features/dashboard/CashTransactionForm";
import { CreateAccountForm } from "../features/dashboard/CreateAccountForm";
import { RecurringTransactionsPanel } from "../features/dashboard/RecurringTransactionsPanel";
import { RiskCalculator } from "../features/dashboard/RiskCalculator";
import { TradeForm } from "../features/dashboard/TradeForm";
import { TransactionCategoryIcon } from "../features/dashboard/transactionCategories";
import type {
  Account,
  CurrencyCode,
  DashboardSummary,
  RecurringTransaction,
  Trade
} from "../types";

type TradePayload = Parameters<typeof portfolioApi.createTrade>[0];

function money(value = 0, currency: CurrencyCode = "EUR", sign = false) {
  const formatted = new Intl.NumberFormat("en-US", { style: "currency", currency }).format(value);
  return sign && value > 0 ? `+${formatted}` : formatted;
}

function toDay(value: string) {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
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

function BalanceChart({
  summary,
  title,
  emptyBody
}: {
  readonly summary?: DashboardSummary;
  readonly title: string;
  readonly emptyBody: string;
}) {
  const points = chartSeries(summary?.equity_curve || []);
  const latest = points.at(-1);
  const latestBalance = latest ? money(latest.balance, summary?.currency || "EUR") : "";
  return (
    <section className="panel chart-panel">
      <div className="section-heading">
        <div><p className="eyebrow">Performance</p><h2>{title}</h2></div>
        <div className="chart-meta">
          {latest && <strong>{latestBalance}</strong>}
          <span className="live-label"><i /> Live ledger</span>
        </div>
      </div>
      {points.length ? (
        <>
          <BalanceLineChart currency={summary?.currency || "EUR"} points={points} />
          <div className="balance-chart-note">
            <span>X-axis: width · Y-axis: height · plot: both · double-click: reset</span>
            <span>Charts by TradingView</span>
          </div>
        </>
      ) : (
        <EmptyState title="No ledger entries" body={emptyBody} />
      )}
    </section>
  );
}

function SummaryMetrics({ summary }: { readonly summary?: DashboardSummary }) {
  const currency = summary?.currency || "EUR";
  if (summary?.account_type !== "Trading Account") {
    return (
      <MetricStrip
        metrics={[
          { label: "Current balance", value: money(summary?.balance, currency) },
          { label: "Net cash flow", value: money(summary?.realised_pnl, currency, true) },
          { label: "Transactions", value: String(summary?.total_entries || 0) },
          {
            label: summary?.account_type === "All Accounts" ? "Accounts" : "Account type",
            value: summary?.account_type === "All Accounts"
              ? String(summary?.account_count || 0)
              : summary?.account_type || "—"
          }
        ]}
      />
    );
  }
  return (
    <MetricStrip
      metrics={[
        { label: "Account balance", value: money(summary?.balance, currency) },
        {
          label: "Realised P&L",
          value: money(summary?.realised_pnl, currency, true),
          detail: `${summary?.trade_count || 0} closed trades`,
          tone: (summary?.realised_pnl || 0) >= 0 ? "positive" : "negative"
        },
        {
          label: "Win rate",
          value: `${(summary?.win_rate || 0).toFixed(1)}%`,
          detail: `${summary?.winning_trades || 0} wins`
        },
        {
          label: "Average trade",
          value: money(summary?.average_trade, currency, true),
          detail: `Best ${money(summary?.best_trade, currency)}`
        }
      ]}
    />
  );
}

function RecentTransactions({
  transactions,
  currency
}: {
  readonly transactions: Trade[];
  readonly currency: CurrencyCode;
}) {
  return (
    <section className="panel transaction-panel">
      <div className="section-heading">
        <div><p className="eyebrow">Activity</p><h2>Recent transactions</h2></div>
        <span>{transactions.length} entries</span>
      </div>
      <div className="transaction-list">
        {transactions.slice(0, 8).map((transaction) => (
          <article key={transaction.id}>
            <span className="category-icon"><TransactionCategoryIcon category={transaction.category} /></span>
            <div>
              <strong>{transaction.description || transaction.action}</strong>
              <small>{transaction.category || "Uncategorised"} · {transaction.trade_time.slice(0, 10)}</small>
            </div>
            <b className={transaction.pnl >= 0 ? "positive" : "negative"}>
              {money(transaction.pnl, currency, true)}
            </b>
          </article>
        ))}
        {!transactions.length && <p className="muted-copy">No transactions recorded yet.</p>}
      </div>
    </section>
  );
}

interface AccountViewProps {
  account: Account;
  summary?: DashboardSummary;
  transactions: Trade[];
  schedules: RecurringTransaction[];
  scheduleFeedback?: { tone: "success" | "error"; message: string } | null;
  createEntry: (payload: TradePayload) => void;
  createSchedule: (payload: Omit<RecurringTransaction, "id" | "active" | "created_at">) => Promise<void>;
  updateSchedule: (payload: Omit<RecurringTransaction, "active" | "created_at">) => Promise<void>;
  deleteSchedule: (id: string) => Promise<void>;
  entryPending: boolean;
  schedulePending: boolean;
}

function AccountView({
  account,
  summary,
  transactions,
  schedules,
  scheduleFeedback,
  createEntry,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  entryPending,
  schedulePending
}: AccountViewProps) {
  const isTrading = account.type === "Trading Account";
  const balance = summary?.balance || account.starting_balance;
  return (
    <>
      <SummaryMetrics summary={summary} />
      <section className="split-layout main-split">
        <BalanceChart
          summary={summary}
          title="Balance through time"
          emptyBody="Add a transaction to start building this account history."
        />
        <section className="panel">
          <p className="eyebrow">Ledger</p>
          <h2>{isTrading ? "Log action" : "Add transaction"}</h2>
          {isTrading ? (
            <TradeForm account={account.name} busy={entryPending} onSubmit={createEntry} />
          ) : (
            <CashTransactionForm
              account={account.name}
              accountType={account.type}
              busy={entryPending}
              currency={account.currency}
              onSubmit={createEntry}
            />
          )}
        </section>
      </section>
      {isTrading ? (
        <RiskCalculator currency={account.currency} initialBalance={balance} />
      ) : (
        <RecentTransactions currency={account.currency} transactions={transactions} />
      )}
      {account.type === "Bank Account" && (
        <RecurringTransactionsPanel
          account={account.name}
          busy={schedulePending}
          currency={account.currency}
          feedback={scheduleFeedback}
          onCreate={createSchedule}
          onUpdate={updateSchedule}
          onDelete={deleteSchedule}
          schedules={schedules}
        />
      )}
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
        body="Add a savings, bank, or trading account to start tracking your finances."
      />
    );
  }
  return (
    <>
      <SummaryMetrics summary={summary} />
      <BalanceChart
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
        body="Add a savings, bank, or trading account to start tracking your finances."
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
  const [scheduleFeedback, setScheduleFeedback] = useState<{
    tone: "success" | "error";
    message: string;
  } | null>(null);
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
    enabled: Boolean(user && selected && account?.type !== "Trading Account")
  });
  const schedules = useQuery({
    queryKey: ["recurring-transactions", selected],
    queryFn: () => portfolioApi.recurringTransactions(selected),
    enabled: Boolean(user && selected && account?.type === "Bank Account")
  });

  useEffect(() => {
    if (selected && accounts.isSuccess && !account) {
      setSelected("");
    }
  }, [account, accounts.isSuccess, selected]);

  useEffect(() => {
    setScheduleFeedback(null);
  }, [selected]);

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      queryClient.invalidateQueries({ queryKey: ["trades", selected] }),
      queryClient.invalidateQueries({ queryKey: ["recurring-transactions", selected] })
    ]);
  };
  const mutationError = (requestError: unknown) => setError(getApiError(requestError));
  const scheduleError = (requestError: unknown) => {
    const message = getApiError(requestError);
    setError(message);
    setScheduleFeedback({ tone: "error", message });
  };
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
        queryClient.invalidateQueries({ queryKey: ["trades"] }),
        queryClient.invalidateQueries({ queryKey: ["recurring-transactions"] })
      ]);
    },
    onError: mutationError
  });
  const createEntry = useMutation({ mutationFn: portfolioApi.createTrade, onSuccess: refresh, onError: mutationError });
  const createSchedule = useMutation({
    mutationFn: portfolioApi.createRecurringTransaction,
    onSuccess: async (created) => {
      setError("");
      setScheduleFeedback({ tone: "success", message: "Automation created and saved to Firebase." });
      queryClient.setQueryData<RecurringTransaction[]>(
        ["recurring-transactions", created.account],
        (current = []) => current.some((schedule) => schedule.id === created.id) ? current : [created, ...current]
      );
      await refresh();
    },
    onError: scheduleError
  });
  const updateSchedule = useMutation({
    mutationFn: portfolioApi.updateRecurringTransaction,
    onSuccess: async (updated) => {
      setError("");
      setScheduleFeedback({ tone: "success", message: "Automation changes saved to Firebase." });
      queryClient.setQueryData<RecurringTransaction[]>(
        ["recurring-transactions", updated.account],
        (current = []) => current.map((schedule) => schedule.id === updated.id ? updated : schedule)
      );
      await refresh();
    },
    onError: scheduleError
  });
  const deleteSchedule = useMutation({
    mutationFn: portfolioApi.deleteRecurringTransaction,
    onSuccess: async () => {
      setError("");
      setScheduleFeedback({ tone: "success", message: "Automation deleted." });
      await refresh();
    },
    onError: scheduleError
  });

  if (!user) {
    return <EmptyState title="Authentication required" body="Sign in from the account menu to access your portfolio." />;
  }

  const summary = selected ? accountSummary.data : undefined;
  const aggregateSummaries = totalSummaries
    .map((query) => query.data)
    .filter((item): item is DashboardSummary => Boolean(item));
  return (
    <div className="page">
      <section className="page-toolbar">
        <div>
          <p className="eyebrow">Portfolio workspace</p>
          <h1>{account?.name || "All accounts"}</h1>
          <p className="page-subtitle">
            {account ? `${account.type} · ${account.currency}` : "Combined balances grouped by currency"}
          </p>
        </div>
        <div className="toolbar-actions">
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
          createSchedule={async (payload) => { await createSchedule.mutateAsync(payload); }}
          updateSchedule={async (payload) => { await updateSchedule.mutateAsync(payload); }}
          deleteSchedule={async (id) => { await deleteSchedule.mutateAsync(id); }}
          entryPending={createEntry.isPending}
          scheduleFeedback={scheduleFeedback}
          schedulePending={createSchedule.isPending || updateSchedule.isPending || deleteSchedule.isPending}
          schedules={schedules.data || []}
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
