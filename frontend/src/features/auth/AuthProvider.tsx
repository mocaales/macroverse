import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { onAuthStateChanged, signOut } from "firebase/auth";

import { firebaseAuth } from "../../firebase";
import type { User } from "../../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(
    () =>
      onAuthStateChanged(firebaseAuth, (firebaseUser) => {
        setUser(
          firebaseUser?.email
            ? {
                uid: firebaseUser.uid,
                email: firebaseUser.email
              }
            : null
        );
        setLoading(false);
      }),
    []
  );

  useEffect(() => {
    const clear = () => {
      void signOut(firebaseAuth);
    };
    window.addEventListener("macroverse:unauthorized", clear);
    return () => window.removeEventListener("macroverse:unauthorized", clear);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      logout: () => signOut(firebaseAuth)
    }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// The provider and its hook intentionally share this module.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider.");
  return value;
}
