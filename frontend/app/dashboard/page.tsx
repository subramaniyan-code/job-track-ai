"use client";

import { useEffect, useState } from "react";
import { BarChart2, Send, MessageSquare, Award, XCircle, Clock, TrendingUp, Mail, Sparkles, Plus, Layers, AlertTriangle } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid } from "recharts";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import StatCard from "@/components/StatCard";
import { api, DashboardStats, Application, EmailInsight, PlatformTrendsOut } from "@/lib/api";
import Link from "next/link";
import StatusBadge from "@/components/StatusBadge";

const INSIGHT_LABELS: Record<string, string> = {
  application_confirmation: "Application received",
  interview_invite: "Interview invite",
  rejection: "Rejection",
  offer: "Offer",
  job_alert: "New job alert",
  other: "Update",
};

const INSIGHT_TONES: Record<string, string> = {
  application_confirmation: "bg-blue-50 text-blue-700",
  interview_invite: "bg-amber-50 text-amber-700",
  rejection: "bg-rose-50 text-rose-700",
  offer: "bg-emerald-50 text-emerald-700",
  job_alert: "bg-brand-50 text-brand-700",
  other: "bg-slate-100 text-slate-600",
};

function InboxCard({ insight, onRead }: { insight: EmailInsight; onRead: (id: string) => void }) {
  const [trackedUrls, setTrackedUrls] = useState<Set<string>>(new Set());

  async function trackExtracted(job: { title: string; company?: string; url?: string }) {
    const created = await api.post<{ id: string }>("/jobs/manual", {
      title: job.title,
      company: job.company || null,
      url: job.url || null,
    });
    await api.post("/applications", { job_id: created.id, status: "saved" });
    setTrackedUrls((prev) => new Set(prev).add(job.url || job.title));
  }

  return (
    <div className={`card p-4 ${!insight.is_read ? "border-brand-200" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`badge ${INSIGHT_TONES[insight.insight_type]}`}>{INSIGHT_LABELS[insight.insight_type]}</span>
            {!insight.is_read && <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />}
          </div>
          <p className="text-sm font-medium truncate">{insight.job_title || insight.subject || "Email update"}</p>
          {insight.company && <p className="text-xs text-slate-500">{insight.company}</p>}
          {insight.summary && <p className="text-xs text-slate-500 mt-1">{insight.summary}</p>}

          {insight.insight_type === "job_alert" && insight.extracted_jobs && insight.extracted_jobs.length > 0 && (
            <div className="mt-3 space-y-2">
              {insight.extracted_jobs.slice(0, 5).map((job, i) => {
                const key = job.url || job.title;
                const tracked = trackedUrls.has(key);
                return (
                  <div key={i} className="flex items-center justify-between gap-2 bg-slate-50 rounded-lg px-3 py-2">
                    <div className="min-w-0">
                      <p className="text-xs font-medium truncate">{job.title}</p>
                      {job.company && <p className="text-[11px] text-slate-400 truncate">{job.company}</p>}
                    </div>
                    <button
                      onClick={() => trackExtracted(job)}
                      disabled={tracked}
                      className="btn btn-secondary text-[11px] py-1 px-2 shrink-0"
                    >
                      <Plus size={12} /> {tracked ? "Added" : "Track"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
        {!insight.is_read && (
          <button onClick={() => onRead(insight.id)} className="btn-ghost text-xs shrink-0">Mark read</button>
        )}
      </div>
    </div>
  );
}

function PlatformTrendsCard({ trends }: { trends: PlatformTrendsOut }) {
  const maxApplied = Math.max(1, ...trends.platforms.map((p) => p.applied));

  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 mb-1">
        <Layers size={16} className="text-brand-600" />
        <h2 className="font-semibold">Platform trends</h2>
      </div>
      <p className="text-sm text-slate-500 mb-4">{trends.summary}</p>

      {trends.platforms.length > 0 && (
        <div className="space-y-3">
          {trends.platforms.map((p) => (
            <div key={p.platform}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-medium text-slate-700">{p.platform}</span>
                <span className="text-slate-400">
                  {p.applied} applied \u00b7 {p.replies} {p.replies === 1 ? "reply" : "replies"} \u00b7 {p.reply_rate}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-full bg-brand-500 rounded-full"
                  style={{ width: `${(p.applied / maxApplied) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DashboardContent() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recent, setRecent] = useState<Application[]>([]);
  const [inbox, setInbox] = useState<EmailInsight[]>([]);
  const [trends, setTrends] = useState<PlatformTrendsOut | null>(null);
  const [stale, setStale] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<DashboardStats>("/dashboard/stats"),
      api.get<Application[]>("/applications"),
      api.get<EmailInsight[]>("/inbox?limit=10"),
      api.get<PlatformTrendsOut>("/dashboard/platform-trends"),
      api.get<Application[]>("/applications/stale"),
    ])
      .then(([s, apps, ins, tr, st]) => {
        setStats(s);
        setRecent(apps.slice(0, 6));
        setInbox(ins);
        setTrends(tr);
        setStale(st);
      })
      .finally(() => setLoading(false));
  }, []);

  async function markRead(id: string) {
    await api.post(`/inbox/${id}/mark-read`);
    setInbox((prev) => prev.map((i) => (i.id === id ? { ...i, is_read: true } : i)));
    setStats((prev) => (prev ? { ...prev, unread_inbox_insights: Math.max(0, prev.unread_inbox_insights - 1) } : prev));
  }

  const chartData = stats
    ? [
        { name: "Applied", value: stats.applied },
        { name: "Interviewing", value: stats.interviewing },
        { name: "Offers", value: stats.offers },
        { name: "Rejected", value: stats.rejected },
        { name: "Ghosted", value: stats.ghosted },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-sm text-slate-500">Your job search, at a glance.</p>
      </div>

      {loading ? (
        <div className="text-sm text-slate-400">Loading\u2026</div>
      ) : stats ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Total applications" value={stats.total_applications} icon={BarChart2} tone="brand" />
            <StatCard label="Applied" value={stats.applied} icon={Send} tone="default" />
            <StatCard label="Interviewing" value={stats.interviewing} icon={MessageSquare} tone="amber" />
            <StatCard label="Offers" value={stats.offers} icon={Award} tone="green" />
            <StatCard label="Rejected" value={stats.rejected} icon={XCircle} tone="red" />
            <StatCard label="Response rate" value={`${stats.response_rate}%`} icon={TrendingUp} tone="brand" />
            <StatCard label="Pending follow-ups" value={stats.pending_followups} icon={Clock} tone="amber" />
            <StatCard label="Inbox updates" value={stats.unread_inbox_insights} icon={Mail} tone={stats.unread_inbox_insights > 0 ? "brand" : "default"} />
          </div>

          {stale.length > 0 && (
            <div className="card p-4 border-amber-200 bg-amber-50">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={16} className="text-amber-600" />
                <h2 className="font-semibold text-amber-800">⏰ Follow-up needed ({stale.length})</h2>
              </div>
              <p className="text-xs text-amber-700 mb-3">These applications have had no activity for 7+ days.</p>
              <div className="space-y-2">
                {stale.map((a) => {
                  const days = Math.floor((Date.now() - new Date(a.last_activity_at).getTime()) / 86400000);
                  return (
                    <div key={a.id} className="flex items-center justify-between bg-white rounded-lg px-3 py-2 border border-amber-100">
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{a.job.title}</p>
                        <p className="text-xs text-slate-500">{a.job.company || "—"} · {days}d ago</p>
                      </div>
                      <Link href="/followups" className="text-xs text-brand-600 font-medium shrink-0 ml-2">Follow up →</Link>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="card p-5">
            <h2 className="font-semibold mb-4">Applications by outcome</h2>
            <div style={{ width: "100%", height: 240 }}>
              <ResponsiveContainer>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eef1f8" />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#64748b" }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#64748b" }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: "#f6f8fc" }} contentStyle={{ borderRadius: 10, border: "1px solid #e6e9f0", fontSize: 13 }} />
                  <Bar dataKey="value" fill="#3b6fe0" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {trends && <PlatformTrendsCard trends={trends} />}

          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Sparkles size={16} className="text-brand-600" />
              <h2 className="font-semibold">Inbox activity</h2>
            </div>
            {inbox.length === 0 ? (
              <div className="card p-5 text-sm text-slate-400">
                No inbox activity yet. Turn on inbox analysis in Settings to see replies and job alerts here automatically.
              </div>
            ) : (
              <div className="space-y-2">
                {inbox.map((insight) => (
                  <InboxCard key={insight.id} insight={insight} onRead={markRead} />
                ))}
              </div>
            )}
          </div>

          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold">Recent activity</h2>
              <Link href="/applications" className="text-sm text-brand-600 font-medium">View all</Link>
            </div>
            {recent.length === 0 ? (
              <p className="text-sm text-slate-400">No applications tracked yet \u2014 head to Find Jobs to get started.</p>
            ) : (
              <div className="divide-y divide-[var(--border)]">
                {recent.map((a) => (
                  <div key={a.id} className="py-3 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{a.job.title}</p>
                      <p className="text-xs text-slate-500 truncate">{a.job.company || "\u2014"}</p>
                    </div>
                    <StatusBadge status={a.status} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <DashboardContent />
      </AppShell>
    </ProtectedRoute>
  );
}
