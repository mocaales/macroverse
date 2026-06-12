import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  user: {
    uid: "admin-uid",
    email: "admin@example.com",
    role: "admin" as "admin" | "user",
    email_verified: true
  }
}));
const adminApi = vi.hoisted(() => ({ users: vi.fn(), deleteUser: vi.fn() }));

vi.mock("../features/auth/AuthProvider", () => ({
  useAuth: () => ({ ...auth, loading: false, logout: vi.fn() })
}));
vi.mock("../api/queries", () => ({ adminApi }));

import { AdminPage } from "./AdminPage";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });
  return render(
    <QueryClientProvider client={client}>
      <AdminPage />
    </QueryClientProvider>
  );
}

describe("AdminPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    auth.user = {
      uid: "admin-uid",
      email: "admin@example.com",
      role: "admin",
      email_verified: true
    };
    adminApi.users.mockResolvedValue([
      {
        uid: "admin-uid",
        email: "admin@example.com",
        role: "admin",
        email_verified: true,
        disabled: false,
        created_at: "2026-01-01T00:00:00Z",
        last_sign_in_at: "2026-06-12T00:00:00Z"
      },
      {
        uid: "user-uid",
        email: "user@example.com",
        role: "user",
        email_verified: false,
        disabled: false,
        created_at: "2026-02-01T00:00:00Z",
        last_sign_in_at: null
      }
    ]);
    adminApi.deleteUser.mockResolvedValue({ message: "User deleted." });
    vi.spyOn(globalThis, "confirm").mockReturnValue(true);
  });

  it("blocks normal users", () => {
    auth.user = {
      uid: "user-uid",
      email: "user@example.com",
      role: "user",
      email_verified: true
    };
    renderPage();
    expect(screen.getByText("Administrator access required")).toBeInTheDocument();
  });

  it("lists users, protects the admin, and deletes a normal user", async () => {
    renderPage();

    expect(await screen.findByText("user@example.com")).toBeInTheDocument();
    expect(screen.getByText("admin@example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete admin@example.com" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Delete user@example.com" }));

    await waitFor(() => expect(adminApi.deleteUser).toHaveBeenCalledWith("user-uid", expect.anything()));
  });
});
