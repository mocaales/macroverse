import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, Trash2, Users } from "lucide-react";

import { adminApi } from "../api/queries";
import { EmptyState } from "../components/EmptyState";
import { MetricStrip } from "../components/MetricStrip";
import { useAuth } from "../features/auth/AuthProvider";

const formatDate = (value?: string | null) =>
  value ? new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "Never";

export function AdminPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const users = useQuery({
    queryKey: ["admin-users"],
    queryFn: adminApi.users,
    enabled: user?.role === "admin"
  });
  const remove = useMutation({
    mutationFn: adminApi.deleteUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] })
  });

  if (user?.role !== "admin") {
    return (
      <EmptyState
        title="Administrator access required"
        body="This workspace is only available to the configured Macroverse administrator."
      />
    );
  }

  const registeredUsers = users.data || [];
  const activeUsers = registeredUsers.filter((item) => !item.disabled).length;

  return (
    <div className="page">
      <section className="page-toolbar">
        <div>
          <p className="eyebrow">Administration</p>
          <h1>User management</h1>
          <p className="page-subtitle">Review registered Firebase accounts and remove normal users.</p>
        </div>
      </section>

      <MetricStrip
        metrics={[
          { label: "Registered users", value: String(registeredUsers.length) },
          { label: "Active users", value: String(activeUsers), tone: "positive" },
          { label: "Administrators", value: "1", detail: "Protected account" }
        ]}
      />

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Firebase Authentication</p>
            <h2>Registered accounts</h2>
          </div>
          <span className="live-label"><Users size={15} /> {registeredUsers.length} users</span>
        </div>

        {users.isLoading && <p className="muted">Loading registered users...</p>}
        {users.isError && <p className="form-error">Registered users could not be loaded.</p>}
        {!users.isLoading && !users.isError && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>User</th><th>Role</th><th>Created</th><th>Last sign-in</th><th>Status</th><th /></tr>
              </thead>
              <tbody>
                {registeredUsers.map((item) => {
                  const isAdmin = item.role === "admin";
                  return (
                    <tr key={item.uid}>
                      <td>
                        <strong className="symbol">{item.email || "No email"}</strong>
                        <small className="table-detail">{item.uid}</small>
                      </td>
                      <td>
                        <span className={`role-badge ${isAdmin ? "admin" : ""}`}>
                          {isAdmin && <ShieldCheck size={13} />}
                          {isAdmin ? "Admin" : "User"}
                        </span>
                      </td>
                      <td>{formatDate(item.created_at)}</td>
                      <td>{formatDate(item.last_sign_in_at)}</td>
                      <td className={item.disabled ? "negative" : "positive"}>
                        {item.disabled ? "Disabled" : "Active"}
                      </td>
                      <td>
                        <button
                          className="icon-button danger-icon"
                          aria-label={`Delete ${item.email || item.uid}`}
                          disabled={isAdmin || remove.isPending}
                          title={isAdmin ? "The administrator account cannot be deleted" : "Delete user"}
                          onClick={() => {
                            if (globalThis.confirm(`Delete ${item.email || item.uid}? This also deletes portfolio data.`)) {
                              remove.mutate(item.uid);
                            }
                          }}
                        >
                          <Trash2 size={15} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
