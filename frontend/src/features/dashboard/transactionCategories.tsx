import type { TransactionCategory } from "../../types";
import { CircleEllipsis } from "lucide-react";
import { TRANSACTION_CATEGORIES } from "./transactionCategoryData";

export function TransactionCategoryIcon({
  category,
  size = 16
}: {
  readonly category?: TransactionCategory | null;
  readonly size?: number;
}) {
  const Icon = TRANSACTION_CATEGORIES.find((item) => item.label === category)?.icon || CircleEllipsis;
  return <Icon aria-hidden="true" size={size} />;
}

export function CategoryPicker({
  value,
  onChange
}: {
  readonly value: TransactionCategory;
  readonly onChange: (category: TransactionCategory) => void;
}) {
  return (
    <div className="category-picker" role="group" aria-label="Transaction category">
      {TRANSACTION_CATEGORIES.map(({ label, icon: Icon }) => (
        <button
          aria-pressed={value === label}
          className={value === label ? "selected" : ""}
          key={label}
          onClick={() => onChange(label)}
          title={label}
          type="button"
        >
          <Icon size={15} />
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}
