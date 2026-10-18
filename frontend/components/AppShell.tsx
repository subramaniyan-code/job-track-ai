"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Search, ListChecks, Mail, Settings, LogOut, ShieldCheck,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/jobs", label: "Find Jobs", icon: Search },
  { href: "/applications", label: "Applications", icon: ListChecks },
  { href: "/followups", label: "Follow-ups", icon: Mail },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen md:flex">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 border-r border-[var(--border)] bg-white">
        <div className="px-5 py-6">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-brand-600 flex items-center justify-center text-white font-bold text-sm">JT</div>
            <span className="font-bold text-lg tracking-tight">JobTrack AI</span>
          </div>
        </div>
        <nav className="flex-1 px-3 space-y-1">
          {NAV_ITEMS.map((item) => {
            const active = pathname?.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                  active ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <Icon size={18} />
                {item.label}
              </Link>
            );
          })}
          {user?.role === "super_admin" && (
            <Link
              href="/settings/admin"
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                pathname === "/settings/admin" ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <ShieldCheck size={18} />
              Admin
            </Link>
          )}
        </nav>
        <div className="p-3 border-t border-[var(--border)]">
          <div className="flex items-center gap-2 px-2 py-2">
            <div className="h-8 w-8 rounded-full bg-slate-200 flex items-center justify-center text-xs font-semibold text-slate-600">
              {user?.full_name?.[0]?.toUpperCase() || "?"}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium truncate">{user?.full_name}</p>
              <p className="text-xs text-slate-500 truncate">{user?.email}</p>
            </div>
            <button onClick={logout} className="btn-ghost p-2" title="Log out">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 md:ml-64 pb-20 md:pb-0">
        <header className="md:hidden sticky top-0 z-20 bg-white border-b border-[var(--border)] px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-lg bg-brand-600 flex items-center justify-center text-white font-bold text-xs">JT</div>
            <span className="font-bold">JobTrack AI</span>
          </div>
          <button onClick={logout} className="btn-ghost p-2">
            <LogOut size={16} />
          </button>
        </header>
        <main className="px-4 py-5 md:px-8 md:py-8 max-w-6xl mx-auto">{children}</main>
      </div>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-20 bg-white border-t border-[var(--border)] flex items-stretch"
        style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}>
        {NAV_ITEMS.map((item) => {
          const active = pathname?.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex-1 flex flex-col items-center justify-center gap-1 py-2.5 text-[11px] font-medium ${
                active ? "text-brand-700" : "text-slate-500"
              }`}
            >
              <Icon size={19} />
              {item.label.split(" ")[0]}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
