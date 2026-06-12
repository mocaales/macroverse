import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { onAuthStateChanged, signOut } from "firebase/auth";
import { createUserWithEmailAndPassword, signInWithEmailAndPassword } from "firebase/auth";
import { beforeEach, describe, expect, it, vi } from "vitest";

const authApi = vi.hoisted(() => ({ me: vi.fn() }));
vi.mock("../../firebase", () => ({ firebaseAuth: { currentUser: null } }));
vi.mock("../../api/queries", () => ({ authApi }));
vi.mock("firebase/auth", () => ({
  onAuthStateChanged: vi.fn(),
  signOut: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signInWithEmailAndPassword: vi.fn()
}));

import { AuthDialog } from "./AuthDialog";
import { AuthProvider, useAuth } from "./AuthProvider";

function AuthStatus() {
  const { user, loading } = useAuth();
  return <p>{loading ? "loading" : user?.email || "anonymous"}</p>;
}

describe("authentication", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(onAuthStateChanged).mockImplementation((_auth, callback) => {
      (callback as (user: null) => void)(null);
      return vi.fn();
    });
    vi.mocked(signOut).mockResolvedValue();
    authApi.me.mockResolvedValue({
      uid: "u-1",
      email: "user@example.com",
      role: "user",
      email_verified: true
    });
  });

  it("tracks Firebase users and clears invalid sessions", async () => {
    vi.mocked(onAuthStateChanged).mockImplementation((_auth, callback) => {
      (callback as (user: never) => void)({ uid: "u-1", email: "user@example.com" } as never);
      return vi.fn();
    });
    render(<AuthProvider><AuthStatus /></AuthProvider>);

    expect(await screen.findByText("user@example.com")).toBeInTheDocument();
    expect(authApi.me).toHaveBeenCalled();
    globalThis.dispatchEvent(new Event("macroverse:unauthorized"));
    await waitFor(() => expect(signOut).toHaveBeenCalled());
  });

  it("requires the provider around the auth hook", () => {
    expect(() => render(<AuthStatus />)).toThrow("useAuth must be used within AuthProvider.");
  });

  it("signs in and closes the dialog", async () => {
    const onClose = vi.fn();
    vi.mocked(signInWithEmailAndPassword).mockResolvedValue({} as never);
    render(<AuthProvider><AuthDialog open onClose={onClose} /></AuthProvider>);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password1" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(signInWithEmailAndPassword).toHaveBeenCalled());
    expect(onClose).toHaveBeenCalled();
  });

  it("validates registration passwords and creates matching accounts", async () => {
    vi.mocked(createUserWithEmailAndPassword).mockResolvedValue({} as never);
    render(<AuthProvider><AuthDialog open onClose={vi.fn()} /></AuthProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Need an account? Register" }));
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password1" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "different" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Passwords do not match.")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "password1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(createUserWithEmailAndPassword).toHaveBeenCalled());
  });

  it("logs out an authenticated user", async () => {
    vi.mocked(onAuthStateChanged).mockImplementation((_auth, callback) => {
      (callback as (user: never) => void)({ uid: "u-1", email: "user@example.com" } as never);
      return vi.fn();
    });
    const onClose = vi.fn();
    render(<AuthProvider><AuthDialog open onClose={onClose} /></AuthProvider>);
    fireEvent.click(await screen.findByRole("button", { name: "Log out" }));
    await waitFor(() => expect(signOut).toHaveBeenCalled());
    expect(onClose).toHaveBeenCalled();
  });

  it("does not render a closed dialog", () => {
    const { container } = render(<AuthProvider><AuthDialog open={false} onClose={vi.fn()} /></AuthProvider>);
    expect(container.querySelector("dialog")).toBeNull();
  });
});
