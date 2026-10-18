"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, UserX, UserCheck } from "lucide-react";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import { api, User } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

function AdminContent() {
  const { user } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  function refresh() {
    api.get<User[]>("/admin/users").then(setUsers).finally(() => setLoading(false));
  }
  useEffect(refresh, []);

  async function toggle(u: User, activate: boolean) {
    await api.post(`/admin/users/${u.id}/${activate ? "reactivate" : "deactivate"}`);
    refresh();
  }

  if (user?.role !== "super_admin") {
    return <p className="text-sm text-slate-500">Admin access only.</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <ShieldCheck size={22} className="text-brand-600" />
        <h1 className="text-2xl font-bold">Admin</h1>
      </div>
      <p className="text-sm text-slate-500">Everyone who registers gets their own account and login. Deactivate anyone who shouldn&apos;t have access anymore.</p>

      {loading ? (
        <div className="text-sm text-slate-400">Loading\u2026</div>
      ) : (
        <div className="card divide-y divide-[var(--border)]">
          {users.map((u) => (
            <div key={u.id} className="flex items-center justify-between px-4 py-3">
              <div>
                <p className="text-sm font-medium">
                  {u.full_name} {u.role === "super_admin" && <span className="badge bg-brand-50 text-brand-700 ml-1">super admin</span>}
                </p>
                <p className="text-xs text-slate-500">{u.email}</p>
              </div>
              {u.role !== "super_admin" && (
                <button
                  onClick={() => toggle(u, !u.is_active)}
                  className={`btn text-xs ${u.is_active ? "btn-secondary" : "btn-primary"}`}
                >
                  {u.is_active ? <><UserX size={13} /> Deactivate</> : <><UserCheck size={13} /> Reactivate</>}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AdminPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <AdminContent />
      </AppShell>
    </ProtectedRoute>
  );
}
