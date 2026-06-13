import { useState, type FormEvent } from "react";
import type { AccountType, CurrencyCode } from "../../types";

interface CreateAccountFormProps {
  readonly onCreate: (payload: {
    name: string;
    starting_balance: number;
    type: AccountType;
    currency: CurrencyCode;
  }) => void;
  readonly busy: boolean;
}

export function CreateAccountForm({
  onCreate,
  busy
}: CreateAccountFormProps) {
  const [name, setName] = useState("");
  const [startingBalance, setStartingBalance] = useState("");
  const [type, setType] = useState<AccountType>("Bank Account");
  const [currency, setCurrency] = useState<CurrencyCode>("EUR");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    onCreate({
      name: name.trim(),
      starting_balance: startingBalance === "" ? 0 : Number(startingBalance),
      type,
      currency
    });
    setName("");
    setStartingBalance("");
  };

  return (
    <form className="inline-form" onSubmit={submit}>
      <label>
        <span>Account name</span>
        <input value={name} placeholder="e.g. Binance Spot" onChange={(event) => setName(event.target.value)} />
      </label>
      <label>
        <span>Account type</span>
        <select value={type} onChange={(event) => setType(event.target.value as AccountType)}>
          <option>Savings</option>
          <option>Bank Account</option>
          <option>Trading Account</option>
        </select>
      </label>
      <label>
        <span>Currency</span>
        <select value={currency} onChange={(event) => setCurrency(event.target.value as CurrencyCode)}>
          {["EUR", "USD", "GBP", "CHF", "JPY", "CAD", "AUD"].map((code) => (
            <option key={code}>{code}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Starting balance</span>
        <input
          type="number"
          min="0"
          inputMode="decimal"
          placeholder="0.00"
          step="0.01"
          value={startingBalance}
          onChange={(event) => setStartingBalance(event.target.value)}
        />
      </label>
      <button className="button primary" disabled={busy}>
        Create account
      </button>
    </form>
  );
}
