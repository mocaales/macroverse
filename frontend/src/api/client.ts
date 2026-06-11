import axios from "axios";
import { FirebaseError } from "firebase/app";

import { firebaseAuth } from "../firebase";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api/v1",
  timeout: 35_000
});

api.interceptors.request.use(async (config) => {
  const token = await firebaseAuth.currentUser?.getIdToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.dispatchEvent(new Event("macroverse:unauthorized"));
    }
    return Promise.reject(error);
  }
);

const FIREBASE_MESSAGES: Record<string, string> = {
  "auth/email-already-in-use": "An account with this email already exists.",
  "auth/invalid-credential": "Invalid email or password.",
  "auth/invalid-email": "Enter a valid email address.",
  "auth/too-many-requests": "Too many attempts. Try again later.",
  "auth/weak-password": "Choose a stronger password."
};

export function getApiError(error: unknown): string {
  if (error instanceof FirebaseError) {
    return FIREBASE_MESSAGES[error.code] || error.message;
  }
  if (axios.isAxiosError(error)) {
    return error.response?.data?.detail || error.message;
  }
  return "An unexpected error occurred.";
}
