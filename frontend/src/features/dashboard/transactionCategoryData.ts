import {
  ArrowLeftRight,
  Car,
  CircleEllipsis,
  Clapperboard,
  Gift,
  GraduationCap,
  HeartPulse,
  House,
  PiggyBank,
  Plane,
  Receipt,
  ShoppingBag,
  ShoppingCart,
  Utensils,
  WalletCards,
  Zap,
  type LucideIcon
} from "lucide-react";

import type { TransactionCategory } from "../../types";

export interface CategoryDefinition {
  label: TransactionCategory;
  icon: LucideIcon;
}

export const TRANSACTION_CATEGORIES: CategoryDefinition[] = [
  { label: "Salary", icon: WalletCards },
  { label: "Groceries", icon: ShoppingCart },
  { label: "Food & Dining", icon: Utensils },
  { label: "Rent & Housing", icon: House },
  { label: "Utilities", icon: Zap },
  { label: "Transport", icon: Car },
  { label: "Health", icon: HeartPulse },
  { label: "Gifts", icon: Gift },
  { label: "Entertainment", icon: Clapperboard },
  { label: "Shopping", icon: ShoppingBag },
  { label: "Education", icon: GraduationCap },
  { label: "Travel", icon: Plane },
  { label: "Transfer", icon: ArrowLeftRight },
  { label: "Savings", icon: PiggyBank },
  { label: "Fees", icon: Receipt },
  { label: "Other", icon: CircleEllipsis }
];
