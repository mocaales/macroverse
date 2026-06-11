import type { Account } from "../types";

export function AccountSelector({
  accounts,
  value,
  onChange
}: {
  accounts: Account[];
  value: string;
  onChange: (value: string) => void;
}) {
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
