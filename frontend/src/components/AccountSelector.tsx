import type { Account } from "../types";

interface AccountSelectorProps {
  readonly accounts: Account[];
  readonly value: string;
  readonly onChange: (value: string) => void;
}

export function AccountSelector({
  accounts,
  value,
  onChange
}: AccountSelectorProps) {
  return (
    <label className="compact-field">
      <span>Account</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Select account</option>
        {accounts.map((account) => (
          <option key={account.name} value={account.name}>
            {account.name} · {account.type}
          </option>
        ))}
      </select>
    </label>
  );
}
