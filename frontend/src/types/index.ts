export type AccountType = "Trading Account";
export type CurrencyCode = "EUR" | "USD" | "GBP" | "CHF" | "JPY" | "CAD" | "AUD";
export type ActionType = "Trade" | "Deposit" | "Withdraw";
export type TransactionCategory =
  | "Salary"
  | "Groceries"
  | "Food & Dining"
  | "Rent & Housing"
  | "Utilities"
  | "Transport"
  | "Health"
  | "Gifts"
  | "Entertainment"
  | "Shopping"
  | "Education"
  | "Travel"
  | "Transfer"
  | "Savings"
  | "Fees"
  | "Other";

export interface User {
  uid: string;
  email: string;
  role: "admin" | "user";
  email_verified: boolean;
}

export interface AdminUser {
  uid: string;
  email: string | null;
  role: "admin" | "user";
  email_verified: boolean;
  disabled: boolean;
  created_at?: string | null;
  last_sign_in_at?: string | null;
}

export interface Account {
  name: string;
  starting_balance: number;
  type: AccountType;
  currency: CurrencyCode;
  created_at?: string;
}

export interface Trade {
  id: string;
  account: string;
  trade_time: string;
  action: ActionType;
  type?: string | null;
  symbol: string;
  pnl: number;
  notes: string;
  description?: string;
  category?: TransactionCategory | null;
  recurring_schedule_id?: string | null;
}

export interface Asset {
  id: string;
  account: string;
  symbol: string;
  quantity: number;
  unit: string;
  display_quantity: number;
  created_at?: string;
}

export interface DashboardSummary {
  currency: CurrencyCode;
  account_type: AccountType | "All Accounts";
  account_count: number;
  balance: number;
  realised_pnl: number;
  total_entries: number;
  trade_count: number;
  winning_trades: number;
  win_rate: number;
  average_trade: number;
  best_trade: number;
  equity_curve: Array<{ date: string; balance: number }>;
  daily_pnl: Array<{ date: string; pnl: number; trade_count: number }>;
  accounts: Array<{
    name: string;
    type: AccountType;
    currency: CurrencyCode;
    balance: number;
  }>;
}

export interface JournalSummary {
  total_entries: number;
  trade_count: number;
  realised_pnl: number;
  win_rate: number;
  average_trade: number;
}

export interface ChartDefinition {
  name: string;
  slug: string;
  category: string;
  quick: string[];
  assets: string[];
  summary: string;
  available: boolean;
}

export interface ChartSeries {
  name: string;
  points: Array<{ date: string; value: number }>;
}
