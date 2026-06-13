import { CalendarClock, Pencil, Trash2, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import type { CurrencyCode, RecurringTransaction, TransactionCategory } from "../../types";
import { CategoryPicker, TransactionCategoryIcon } from "./transactionCategories";

interface RecurringTransactionsPanelProps {
  readonly account: string;
  readonly currency: CurrencyCode;
  readonly schedules: RecurringTransaction[];
  readonly busy: boolean;
  readonly feedback?: { tone: "success" | "error"; message: string } | null;
  readonly onCreate: (payload: Omit<RecurringTransaction, "id" | "active" | "created_at">) => Promise<void>;
  readonly onUpdate: (payload: Omit<RecurringTransaction, "active" | "created_at">) => Promise<void>;
  readonly onDelete: (id: string) => Promise<void>;
}

export function RecurringTransactionsPanel({
  account,
  currency,
  schedules,
  busy,
  feedback,
  onCreate,
  onUpdate,
  onDelete
}: RecurringTransactionsPanelProps) {
  const today = new Date().toISOString().slice(0, 10);
  const [action, setAction] = useState<"Deposit" | "Withdraw">("Deposit");
  const [amount, setAmount] = useState(100);
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<TransactionCategory>("Salary");
  const [dayOfMonth, setDayOfMonth] = useState(1);
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);

  const resetForm = () => {
    setAction("Deposit");
    setAmount(100);
    setDescription("");
    setCategory("Salary");
    setDayOfMonth(1);
    setStartDate(today);
    setEndDate("");
    setEditingId(null);
  };

  useEffect(() => {
    setAction("Deposit");
    setAmount(100);
    setDescription("");
    setCategory("Salary");
    setDayOfMonth(1);
    setStartDate(today);
    setEndDate("");
    setEditingId(null);
  }, [account, today]);

  const edit = (schedule: RecurringTransaction) => {
    setAction(schedule.action);
    setAmount(schedule.amount);
    setDescription(schedule.description);
    setCategory(schedule.category);
    setDayOfMonth(schedule.day_of_month);
    setStartDate(schedule.start_date.slice(0, 10));
    setEndDate(schedule.end_date?.slice(0, 10) || "");
    setEditingId(schedule.id);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!description.trim() || amount <= 0) return;
    const payload = {
      account,
      action,
      amount,
      description: description.trim(),
      category,
      day_of_month: dayOfMonth,
      start_date: startDate,
      end_date: endDate || null
    };
    try {
      if (editingId) {
        await onUpdate({ id: editingId, ...payload });
      } else {
        await onCreate(payload);
      }
      resetForm();
    } catch {
      // The parent renders the API error and keeps these values available for correction.
    }
  };

  const remove = async (schedule: RecurringTransaction) => {
    try {
      await onDelete(schedule.id);
      if (editingId === schedule.id) resetForm();
    } catch {
      // The parent renders the API error and keeps the row in place.
    }
  };

  return (
    <section className="panel recurring-panel">
      <div className="section-heading">
        <div><p className="eyebrow">Automation</p><h2>Recurring transactions</h2></div>
        <CalendarClock size={18} />
      </div>
      {feedback && (
        <p className={`form-notice ${feedback.tone}`} role={feedback.tone === "error" ? "alert" : "status"}>
          {feedback.message}
        </p>
      )}
      <form className="stack" onSubmit={submit}>
        <div className="form-grid two">
          <label>
            <span>Transaction</span>
            <select value={action} onChange={(event) => setAction(event.target.value as "Deposit" | "Withdraw")}>
              <option>Deposit</option>
              <option>Withdraw</option>
            </select>
          </label>
          <label>
            <span>Amount ({currency})</span>
            <input min="0.01" step="0.01" type="number" value={amount} onChange={(event) => setAmount(Number(event.target.value))} />
          </label>
        </div>
        <label>
          <span>Description</span>
          <input required value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <div className="form-grid two">
          <label>
            <span>Day of month</span>
            <input min="1" max="31" type="number" value={dayOfMonth} onChange={(event) => setDayOfMonth(Number(event.target.value))} />
          </label>
          <label>
            <span>Start date</span>
            <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          </label>
        </div>
        <label>
          <span>End date (optional)</span>
          <input min={startDate} type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
        </label>
        <fieldset className="category-fieldset">
          <legend>Category</legend>
          <CategoryPicker value={category} onChange={setCategory} />
        </fieldset>
        <div className="form-actions">
          <button className="button secondary" disabled={busy}>
            {editingId ? "Save changes" : "Create automation"}
          </button>
          {editingId && (
            <button className="button ghost" disabled={busy} type="button" onClick={resetForm}>
              <X size={15} /> Cancel editing
            </button>
          )}
        </div>
      </form>
      <div className="schedule-list">
        {schedules.map((schedule) => (
          <article key={schedule.id}>
            <span className="category-icon"><TransactionCategoryIcon category={schedule.category} /></span>
            <div>
              <strong>{schedule.description}</strong>
              <small>{schedule.action} {schedule.amount.toLocaleString()} {currency} · day {schedule.day_of_month}</small>
            </div>
            <div className="schedule-actions">
              <button aria-label={`Edit ${schedule.description}`} className="icon-button" disabled={busy} onClick={() => edit(schedule)}>
                <Pencil size={15} />
              </button>
              <button aria-label={`Delete ${schedule.description}`} className="icon-button danger-icon" disabled={busy} onClick={() => remove(schedule)}>
                <Trash2 size={15} />
              </button>
            </div>
          </article>
        ))}
        {!schedules.length && <p className="muted-copy">No recurring transactions configured.</p>}
      </div>
    </section>
  );
}
