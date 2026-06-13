import { useState, type FormEvent } from "react";

import type { AccountType, ActionType, CurrencyCode, TransactionCategory } from "../../types";
import { CategoryPicker } from "./transactionCategories";

interface CashTransactionFormProps {
  readonly account: string;
  readonly accountType: AccountType;
  readonly currency: CurrencyCode;
  readonly busy: boolean;
  readonly onSubmit: (payload: {
    account: string;
    trade_time: string;
    action: ActionType;
    symbol: string;
    pnl: number;
    description: string;
    category: TransactionCategory;
  }) => void;
}

export function CashTransactionForm({
  account,
  accountType,
  currency,
  busy,
  onSubmit
}: CashTransactionFormProps) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [action, setAction] = useState<ActionType>("Deposit");
  const [amount, setAmount] = useState(0);
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<TransactionCategory>(
    accountType === "Savings" ? "Savings" : "Other"
  );

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!description.trim() || amount <= 0) return;
    onSubmit({
      account,
      trade_time: date,
      action,
      symbol: "CASH",
      pnl: action === "Withdraw" ? -amount : amount,
      description: description.trim(),
      category: accountType === "Savings" ? "Savings" : category
    });
    setAmount(0);
    setDescription("");
  };

  return (
    <form className="stack" onSubmit={submit}>
      <div className="form-grid two">
        <label>
          <span>Date</span>
          <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </label>
        <label>
          <span>Transaction</span>
          <select value={action} onChange={(event) => setAction(event.target.value as ActionType)}>
            <option>Deposit</option>
            <option>Withdraw</option>
          </select>
        </label>
      </div>
      <label>
        <span>Amount ({currency})</span>
        <input
          min="0.01"
          required
          step="0.01"
          type="number"
          value={amount}
          onChange={(event) => setAmount(Number(event.target.value))}
        />
      </label>
      <label>
        <span>Description</span>
        <input
          maxLength={200}
          placeholder="What was this transaction for?"
          required
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </label>
      {accountType === "Bank Account" && (
        <fieldset className="category-fieldset">
          <legend>Category</legend>
          <CategoryPicker value={category} onChange={setCategory} />
        </fieldset>
      )}
      <button className="button primary" disabled={busy}>
        Add transaction
      </button>
    </form>
  );
}
