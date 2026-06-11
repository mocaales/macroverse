export type AccountType = "Trading" | "Investing" | "Bank Account" | "Overall";
export type ActionType = "Trade" | "Deposit" | "Withdraw";

export interface User {
  uid: string;
  email: string;
}

export interface Account {
  name: string;
  starting_balance: number;
  type: AccountType;
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
  balance: number;
  realised_pnl: number;
  trade_count: number;
  winning_trades: number;
  win_rate: number;
  average_trade: number;
  best_trade: number;
  equity_curve: Array<{ date: string; balance: number }>;
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
