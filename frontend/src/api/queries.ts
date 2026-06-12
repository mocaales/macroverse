import { api } from "./client";
import type {
  Account,
  AdminUser,
  Asset,
  ChartDefinition,
  ChartSeries,
  DashboardSummary,
  JournalSummary,
  Trade,
  User
} from "../types";

export const authApi = {
  me: async () => (await api.get<User>("/auth/me")).data
};

export const adminApi = {
  users: async () => (await api.get<AdminUser[]>("/admin/users")).data,
  deleteUser: async (uid: string) => (await api.delete(`/admin/users/${uid}`)).data
};

export const portfolioApi = {
  accounts: async () => (await api.get<Account[]>("/portfolio/accounts")).data,
  createAccount: async (payload: Omit<Account, "created_at">) =>
    (await api.post<Account>("/portfolio/accounts", payload)).data,
  trades: async (account?: string) =>
    (await api.get<Trade[]>("/portfolio/trades", { params: { account } })).data,
  createTrade: async (payload: {
    account: string;
    trade_time: string;
    action: string;
    type?: string;
    symbol: string;
    pnl: number;
    notes?: string;
  }) => (await api.post<Trade>("/portfolio/trades", payload)).data,
  updateTrade: async ({ id, ...payload }: Partial<Trade> & { id: string }) =>
    (await api.put<Trade>(`/portfolio/trades/${id}`, payload)).data,
  deleteTrade: async (id: string) => (await api.delete(`/portfolio/trades/${id}`)).data,
  assets: async (account?: string) =>
    (await api.get<Asset[]>("/portfolio/assets", { params: { account } })).data,
  createAsset: async (payload: Omit<Asset, "id" | "created_at">) =>
    (await api.post<Asset>("/portfolio/assets", payload)).data,
  deleteAsset: async (id: string) => (await api.delete(`/portfolio/assets/${id}`)).data,
  dashboard: async (account: string) =>
    (await api.get<DashboardSummary>(`/portfolio/dashboard/${encodeURIComponent(account)}`)).data,
  journalSummary: async (account: string) =>
    (await api.get<JournalSummary>(`/portfolio/journal/${encodeURIComponent(account)}/summary`)).data
};

export const chartsApi = {
  charts: async () => (await api.get<ChartDefinition[]>("/charts")).data,
  favourites: async () => (await api.get<string[]>("/charts/favourites")).data,
  toggleFavourite: async (name: string) =>
    (await api.post<string[]>(`/charts/favourites/${encodeURIComponent(name)}`)).data,
  series: async (slug: string) =>
    (await api.get<ChartSeries[]>(`/charts/${slug}/series`)).data
};
