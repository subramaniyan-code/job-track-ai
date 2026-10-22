"use client";

import { useEffect, useState } from "react";
import { BarChart2, Send, MessageSquare, Award, XCircle, Clock, TrendingUp, Mail, Sparkles, Plus, Layers, AlertTriangle, RefreshCw, ChevronDown, ChevronUp, Calendar, Copy, Check, User, FileText } from "lucide-react";
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


function formatIST(isoDate?: string | null) {
  if (!isoDate) return "—";
  const safeIso = isoDate.includes("Z") || /[+-]\d{2}:\d{2}$/.test(isoDate) ? isoDate : `${isoDate}Z`;
  try {
    return new Date(safeIso).toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
  } catch {
    return isoDate;
  }
}

const INSIGHT_TONES: Record<string, string> = {
  application_confirmation: "bg-blue-50 text-blue-700",
  interview_invite: "bg-amber-50 text-amber-700",
  rejection: "bg-rose-50 text-rose-700",
  offer: "bg-emerald-50 text-emerald-700",
  job_alert: "bg-brand-50 text-brand-700",
  other: "bg-slate-100 text-slate-600",
};

function InboxCard({ insight, onRead }: { insight: EmailInsight; onRead: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
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

  const receivedTimeStr = formatIST(insight.received_at || insight.created_at);

  return (
    <div className={`card transition-all ${expanded ? "ring-2 ring-brand-500/20 shadow-md p-5 bg-white" : "p-4 hover:border-slate-300"} ${!insight.is_read ? "border-brand-200 bg-brand-50/20" : ""}`}>
      {/* Header Row */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <span className={`badge ${INSIGHT_TONES[insight.insight_type] || "bg-slate-100 text-slate-700"}`}>
              {INSIGHT_LABELS[insight.insight_type] || "Email Update"}
            </span>

            {/* Received Date & Time Pill */}
            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200/60" title={`Received at: ${receivedTimeStr} (IST)`}>
              <Clock size={11} className="text-slate-400" />
              <span>{receivedTimeStr}</span>
            </span>

            {insight.platform && (
              <span className="text-[10px] uppercase font-semibold tracking-wider text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200/60">
                {insight.platform}
              </span>
            )}

            {!insight.is_read && (
              <span className="inline-flex items-center gap-1 text-[10px] font-bold text-brand-600 bg-brand-100/70 px-1.5 py-0.5 rounded-full">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-600 animate-pulse" /> New
              </span>
            )}
          </div>

          <h3 className="text-sm font-semibold text-slate-900 leading-snug">
            {insight.job_title || insight.subject || "Email Notification"}
          </h3>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-xs text-slate-500">
            {insight.company && (
              <span className="font-medium text-slate-700">{insight.company}</span>
            )}
            {insight.from_address && (
              <span className="text-slate-400 truncate max-w-xs font-mono text-[11px]">
                from: {insight.from_address}
              </span>
            )}
          </div>

          {!expanded && insight.summary && (
            <p className="text-xs text-slate-600 mt-1.5 line-clamp-2 leading-relaxed">
              {insight.summary}
            </p>
          )}

          {/* Quick preview of jobs for alerts when collapsed */}
          {!expanded && insight.insight_type === "job_alert" && insight.extracted_jobs && insight.extracted_jobs.length > 0 && (
            <div className="mt-2.5 flex items-center gap-2 text-xs text-slate-500">
              <span className="font-medium text-brand-600">
                {insight.extracted_jobs.length} jobs detected in alert
              </span>
              <span>·</span>
              <button
                onClick={() => setExpanded(true)}
                className="text-brand-600 hover:underline font-medium text-xs inline-flex items-center gap-0.5"
              >
                View all & track <ChevronDown size={12} />
              </button>
            </div>
          )}
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 shrink-0">
          {!insight.is_read && (
            <button
              onClick={() => onRead(insight.id)}
              className="btn-ghost text-xs text-slate-500 hover:text-brand-600 py-1 px-2 shrink-0 hidden sm:inline-block"
              title="Mark as read"
            >
              Mark read
            </button>
          )}

          {/* Dropdown Toggle Button */}
          <button
            onClick={() => setExpanded(!expanded)}
            className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border transition-all ${
              expanded
                ? "bg-brand-600 text-white border-brand-600 shadow-sm"
                : "bg-white text-slate-700 hover:text-brand-600 hover:bg-slate-50 border-slate-200"
            }`}
            title={expanded ? "Collapse email view" : "Open dropdown to read full email content"}
          >
            <Mail size={13} className={expanded ? "text-white" : "text-brand-600"} />
            <span className="hidden xs:inline">{expanded ? "Close Email" : "Read Email"}</span>
            {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        </div>
      </div>

      {/* Expanded Dropdown: Full Email Reader & Details */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-slate-200/80 space-y-3.5 animate-in fade-in duration-150">
          {/* Metadata Card */}
          <div className="bg-slate-50/80 border border-slate-200/80 rounded-xl p-3.5 text-xs space-y-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pb-2.5 border-b border-slate-200/60">
              <div className="flex items-center gap-1.5 text-slate-700">
                <Calendar size={13} className="text-brand-600 shrink-0" />
                <span className="font-semibold text-slate-500">Received Date & Time:</span>
                <span className="font-medium text-slate-900">{receivedTimeStr} (IST)</span>
              </div>

              {insight.from_address && (
                <div className="flex items-center gap-1.5 text-slate-700 min-w-0">
                  <User size={13} className="text-brand-600 shrink-0" />
                  <span className="font-semibold text-slate-500">From:</span>
                  <span className="font-mono text-slate-900 truncate bg-white px-2 py-0.5 rounded border border-slate-200 text-[11px]" title={insight.from_address}>
                    {insight.from_address}
                  </span>
                </div>
              )}
            </div>

            <div className="flex items-start gap-1.5 text-slate-700">
              <Mail size={13} className="text-brand-600 mt-0.5 shrink-0" />
              <div>
                <span className="font-semibold text-slate-500 mr-1.5">Subject:</span>
                <span className="font-medium text-slate-900">{insight.subject || "No Subject"}</span>
              </div>
            </div>

            {insight.summary && (
              <div className="flex items-start gap-1.5 bg-amber-50/70 border border-amber-200/60 rounded-lg p-2.5 text-slate-700">
                <Sparkles size={13} className="text-amber-600 mt-0.5 shrink-0" />
                <div>
                  <span className="font-semibold text-amber-800 mr-1">AI Classification Summary:</span>
                  <span className="text-amber-950">{insight.summary}</span>
                </div>
              </div>
            )}
          </div>

          {/* Full Email Message Box */}
          <div>
            <div className="flex items-center justify-between mb-1.5 px-0.5">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-800">
                <FileText size={13} className="text-brand-600" />
                <span>Full Email Content</span>
              </div>
              {insight.body && (
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(insight.body || "");
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                  }}
                  className="flex items-center gap-1 text-[11px] font-medium text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 px-2.5 py-1 rounded-md transition-colors"
                  title="Copy full email text to clipboard"
                >
                  {copied ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                  <span>{copied ? "Copied to clipboard!" : "Copy Full Text"}</span>
                </button>
              )}
            </div>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 font-sans text-xs text-slate-800 leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto select-text shadow-inner">
              {insight.body ? (
                insight.body
              ) : (
                <div className="text-slate-500 py-3 space-y-2">
                  <p className="font-medium text-slate-700">
                    {insight.summary || "Full message content was not cached for this earlier email."}
                  </p>
                  <p className="text-[11px] text-slate-400">
                    💡 Click <strong>"Sync inbox now"</strong> at the top of the Inbox Activity section to fetch and cache full email bodies for your recent emails.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Extracted Jobs (for job_alert) */}
          {insight.insight_type === "job_alert" && insight.extracted_jobs && insight.extracted_jobs.length > 0 && (
            <div className="mt-3 pt-3 border-t border-slate-200/80">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-slate-800">
                  Discovered Job Postings in this Alert ({insight.extracted_jobs.length}):
                </span>
              </div>
              <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                {insight.extracted_jobs.map((job, i) => {
                  const key = job.url || job.title;
                  const tracked = trackedUrls.has(key);
                  return (
                    <div key={i} className="flex items-center justify-between gap-2 bg-slate-50/80 hover:bg-slate-100/80 rounded-lg px-3 py-2 border border-slate-200 transition-colors">
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-semibold text-slate-900 truncate">{job.title}</p>
                        {job.company && <p className="text-[11px] text-slate-500 truncate">{job.company}</p>}
                      </div>
                      <button
                        onClick={() => trackExtracted(job)}
                        disabled={tracked}
                        className="btn btn-secondary text-[11px] py-1 px-2.5 shrink-0"
                      >
                        <Plus size={12} /> {tracked ? "Added to Applications" : "Track Job"}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Footer controls */}
          <div className="flex items-center justify-between pt-2">
            {!insight.is_read ? (
              <button
                onClick={() => onRead(insight.id)}
                className="text-xs text-brand-600 hover:text-brand-700 font-medium hover:underline flex items-center gap-1"
              >
                ✓ Mark as read
              </button>
            ) : (
              <span className="text-[11px] text-slate-400">✓ Read</span>
            )}

            <button
              onClick={() => setExpanded(false)}
              className="flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-800 py-1 px-2.5 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <ChevronUp size={13} /> Collapse Email
            </button>
          </div>
        </div>
      )}
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
  const [syncing, setSyncing] = useState(false);

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

  async function syncInbox() {
    setSyncing(true);
    try {
      const res = await api.post<{ status: string; new_insights: number; scanned_job_emails: number; total_insights: number }>(
        "/inbox/sync?force_backfill=true"
      );
      const [newInbox, newStats] = await Promise.all([
        api.get<EmailInsight[]>("/inbox?limit=10"),
        api.get<DashboardStats>("/dashboard/stats"),
      ]);
      setInbox(newInbox);
      setStats(newStats);
      if (res.new_insights > 0) {
        alert(`Inbox synced successfully! Discovered ${res.new_insights} new job update(s) in your email.`);
      } else if (res.total_insights > 0) {
        alert(`Inbox is up to date! Showing ${res.total_insights} job update(s) on your dashboard.`);
      } else {
        alert("Inbox connected and checked for the past 30 days! No job application or interview emails found yet.");
      }
    } catch (err: any) {
      alert(err.message || "Failed to check inbox. Make sure your email account with IMAP is connected in Settings.");
    } finally {
      setSyncing(false);
    }
  }

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
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-brand-600" />
                <h2 className="font-semibold">Inbox activity</h2>
              </div>
              <button
                onClick={syncInbox}
                disabled={syncing}
                className="btn btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5"
                title="Scan last 30 days of job emails from inbox"
              >
                <RefreshCw size={13} className={syncing ? "animate-spin" : ""} />
                {syncing ? "Scanning inbox…" : "Sync inbox now"}
              </button>
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
