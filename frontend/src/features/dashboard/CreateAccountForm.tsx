import { useState, type FormEvent } from "react";
import type { AccountType } from "../../types";

export function CreateAccountForm({
  onCreate,
  busy
}: {
  onCreate: (payload: { name: string; starting_balance: number; type: AccountType }) => void;
  busy: boolean;
}) {
  const [name, setName] = useState("");
  const [startingBalance, setStartingBalance] = useState(0);
  const [type, setType] = useState<AccountType>("Trading");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    onCreate({ name: name.trim(), starting_balance: startingBalance, type });
    setName("");
  };

  return (
    <form className="inline-form" onSubmit={submit}>
      <label>
        Account name
        <input value={name} placeholder="e.g. Binance Spot" onChange={(event) => setName(event.target.value)} />
      </label>
      <label>
        Account type
        <select value={type} onChange={(event) => setType(event.target.value as AccountType)}>
          <option>Trading</option>
          <option>Investing</option>
          <option>Bank Account</option>
          <option>Overall</option>
        </select>
      </label>
      <label>
        Starting balance
        <input
          type="number"
          min="0"
          step="100"
          value={startingBalance}
          onChange={(event) => setStartingBalance(Number(event.target.value))}
        />
      </label>
      <button className="button primary" disabled={busy}>
        Create account
      </button>
    </form>
  );
}
