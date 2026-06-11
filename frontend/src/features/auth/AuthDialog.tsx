import { useState, type FormEvent } from "react";
import { createUserWithEmailAndPassword, signInWithEmailAndPassword } from "firebase/auth";
import { X } from "lucide-react";

import { getApiError } from "../../api/client";
import { firebaseAuth } from "../../firebase";
import { useAuth } from "./AuthProvider";

export function AuthDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user, logout } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (mode === "register") {
        if (password !== confirmPassword) {
          setError("Passwords do not match.");
          return;
        }
        await createUserWithEmailAndPassword(firebaseAuth, email, password);
      } else {
        await signInWithEmailAndPassword(firebaseAuth, email, password);
      }
      onClose();
    } catch (requestError) {
      setError(getApiError(requestError));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="modal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
        <button className="icon-button modal-close" onClick={onClose} aria-label="Close account dialog">
          <X size={18} />
        </button>
        <p className="eyebrow">Account</p>
        {user ? (
          <>
            <h2>Session active</h2>
            <p className="muted">{user.email}</p>
            <button
              className="button danger"
              onClick={async () => {
                await logout();
                onClose();
              }}
            >
              Log out
            </button>
          </>
        ) : (
          <>
            <h2>{mode === "login" ? "Sign in to Macroverse" : "Create your account"}</h2>
            <form onSubmit={submit} className="stack">
              <label>
                Email
                <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
              </label>
              <label>
                Password
                <input
                  type="password"
                  minLength={8}
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              {mode === "register" && (
                <label>
                  Confirm password
                  <input
                    type="password"
                    minLength={8}
                    required
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                  />
                </label>
              )}
              {error && <p className="form-error">{error}</p>}
              <button className="button primary" disabled={submitting}>
                {submitting ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
              </button>
            </form>
            <button className="text-button" onClick={() => setMode(mode === "login" ? "register" : "login")}>
              {mode === "login" ? "Need an account? Register" : "Already registered? Sign in"}
            </button>
          </>
        )}
      </section>
    </div>
  );
}
