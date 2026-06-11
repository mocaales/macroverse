import axios from "axios";
import { FirebaseError } from "firebase/app";
import { describe, expect, it, vi } from "vitest";

vi.mock("../firebase", () => ({
  firebaseAuth: {
    currentUser: null
  }
}));

import { getApiError } from "./client";

describe("getApiError", () => {
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
});
