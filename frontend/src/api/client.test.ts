import axios from "axios";
import { FirebaseError } from "firebase/app";
import { beforeEach, describe, expect, it, vi } from "vitest";

const firebaseAuth = vi.hoisted(() => ({ currentUser: null as null | { getIdToken: () => Promise<string> } }));
vi.mock("../firebase", () => ({
  firebaseAuth
}));

import { api, getApiError } from "./client";

describe("getApiError", () => {
  beforeEach(() => {
    firebaseAuth.currentUser = null;
  });

  it("maps known Firebase authentication errors", () => {
    expect(getApiError(new FirebaseError("auth/invalid-credential", "Firebase rejected the login."))).toBe(
      "Invalid email or password."
    );
  });

  it("returns API error details from Axios responses", () => {
    const error = new axios.AxiosError("Request failed");
    error.response = {
      data: { detail: "Account was not found." },
      status: 404,
      statusText: "Not Found",
      headers: {},
      config: { headers: new axios.AxiosHeaders() }
    };

    expect(getApiError(error)).toBe("Account was not found.");
  });

  it("uses a safe fallback for unknown errors", () => {
    expect(getApiError(new Error("internal detail"))).toBe("An unexpected error occurred.");
  });

  it("adds Firebase bearer tokens to requests", async () => {
    firebaseAuth.currentUser = { getIdToken: vi.fn().mockResolvedValue("token-123") };
    api.defaults.adapter = async (config) => ({
      data: config.headers.Authorization,
      status: 200,
      statusText: "OK",
      headers: {},
      config
    });

    const response = await api.get("/test");
    expect(response.data).toBe("Bearer token-123");
  });

  it("dispatches an unauthorized event for expired sessions", async () => {
    const listener = vi.fn();
    globalThis.addEventListener("macroverse:unauthorized", listener);
    api.defaults.adapter = async (config) => Promise.reject(
      new axios.AxiosError("Unauthorized", "401", config, undefined, {
        data: {}, status: 401, statusText: "Unauthorized", headers: {}, config
      })
    );

    await expect(api.get("/private")).rejects.toThrow("Unauthorized");
    expect(listener).toHaveBeenCalled();
    globalThis.removeEventListener("macroverse:unauthorized", listener);
  });
});
