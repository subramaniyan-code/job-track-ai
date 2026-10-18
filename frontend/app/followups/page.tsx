"use client";

import { useEffect, useState } from "react";
import { Clock, Send, Check, X, Plus, Edit3 } from "lucide-react";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Modal from "@/components/Modal";
import StatusBadge from "@/components/StatusBadge";
import { api, FollowUp, Application } from "@/lib/api";

function formatDate(iso: string | null) {
  if (!iso) return "\u2014";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function NewDraftModal({ apps, onClose, onCreated }: { apps: Application[]; onClose: () => void; onCreated: (f: FollowUp) => void }) {
  const [applicationId, setApplicationId] = useState(apps[0]?.id || "");
  const [template, setTemplate] = useState<string>("post_application_checkin");
  const [templates, setTemplates] = useState<Record<string, string>>({});
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api.get<Record<string, string>>("/followups/templates").then(setTemplates);
  }, []);

  async function create() {
    if (!applicationId) return;
    setCreating(true);
    try {
      const fu = await api.post<FollowUp>("/followups/draft", { application_id: applicationId, template });
      onCreated(fu);
      onClose();
    } finally {
      setCreating(false);
    }
  }

  return (
    <Modal title="Draft a follow-up" onClose={onClose}>
      <div className="space-y-4">
        <div>
          <label className="label">Application</label>
          <select className="input" value={applicationId} onChange={(e) => setApplicationId(e.target.value)}>
            {apps.map((a) => (
              <option key={a.id} value={a.id}>{a.job.title} \u2014 {a.job.company}</option>
            ))}
          </select>
          {apps.length === 0 && <p className="text-xs text-rose-500 mt-1">Track an application first from Find Jobs.</p>}
        </div>
        <div>
          <label className="label">Template</label>
          <select className="input" value={template} onChange={(e) => setTemplate(e.target.value)}>
            {Object.entries(templates).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </div>
        <button onClick={create} disabled={creating || !applicationId} className="btn btn-primary w-full">
          {creating ? "Drafting\u2026" : "Generate draft"}
        </button>
      </div>
    </Modal>
  );
}

function ReviewModal({ fu, app, onClose, onUpdated }: { fu: FollowUp; app: Application | undefined; onClose: () => void; onUpdated: (f: FollowUp) => void }) {
  const [subject, setSubject] = useState(fu.subject);
  const [body, setBody] = useState(fu.body);
  const [saving, setSaving] = useState(false);
  const [acting, setActing] = useState(false);

  async function saveEdits() {
    setSaving(true);
    try {
      const updated = await api.patch<FollowUp>(`/followups/${fu.id}`, { subject, body });
      onUpdated(updated);
    } finally {
      setSaving(false);
    }
  }

  async function approve() {
    setActing(true);
    try {
      if (subject !== fu.subject || body !== fu.body) await saveEdits();
      const updated = await api.post<FollowUp>(`/followups/${fu.id}/approve`);
      onUpdated(updated);
      onClose();
    } finally {
      setActing(false);
    }
  }

  async function sendNow() {
    setActing(true);
    try {
      const updated = await api.post<FollowUp>(`/followups/${fu.id}/send-now`);
      onUpdated(updated);
      onClose();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setActing(false);
    }
  }

  async function skip() {
    setActing(true);
    try {
      const updated = await api.post<FollowUp>(`/followups/${fu.id}/skip`);
      onUpdated(updated);
      onClose();
    } finally {
      setActing(false);
    }
  }

  return (
    <Modal title="Review follow-up" onClose={onClose} wide>
      <div className="space-y-4">
        {!app?.recruiter_email && (
          <div className="text-sm text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            No recruiter/contact email is set on this application yet \u2014 add one from the Applications tab before sending.
          </div>
        )}
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Clock size={14} />
          Suggested send time: <span className="font-medium text-slate-700">{formatDate(fu.suggested_send_at)}</span>
        </div>
        <div>
          <label className="label">Subject</label>
          <input className="input" value={subject} onChange={(e) => setSubject(e.target.value)} />
        </div>
        <div>
          <label className="label">Body</label>
          <textarea className="input" rows={10} value={body} onChange={(e) => setBody(e.target.value)} />
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={approve} disabled={acting || fu.status !== "draft"} className="btn btn-primary flex-1">
            <Check size={15} /> Approve for {formatDate(fu.suggested_send_at)}
          </button>
          <button onClick={sendNow} disabled={acting} className="btn btn-secondary flex-1">
            <Send size={15} /> Send now instead
          </button>
          <button onClick={skip} disabled={acting} className="btn btn-danger">
            <X size={15} /> Skip
          </button>
        </div>
      </div>
    </Modal>
  );
}

function FollowUpsContent() {
  const [followups, setFollowups] = useState<FollowUp[]>([]);
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [reviewing, setReviewing] = useState<FollowUp | null>(null);

  useEffect(() => {
    Promise.all([api.get<FollowUp[]>("/followups"), api.get<Application[]>("/applications")])
      .then(([f, a]) => {
        setFollowups(f);
        setApps(a);
      })
      .finally(() => setLoading(false));
  }, []);

  function appFor(fu: FollowUp) {
    return apps.find((a) => a.id === fu.application_id);
  }

  function upsert(fu: FollowUp) {
    setFollowups((prev) => (prev.some((f) => f.id === fu.id) ? prev.map((f) => (f.id === fu.id ? fu : f)) : [fu, ...prev]));
  }

  const pending = followups.filter((f) => f.status === "draft" || f.status === "approved");
  const history = followups.filter((f) => f.status === "sent" || f.status === "skipped");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Follow-ups</h1>
          <p className="text-sm text-slate-500">Nothing sends without your approval.</p>
        </div>
        <button onClick={() => setShowNew(true)} className="btn btn-primary">
          <Plus size={16} /> New
        </button>
      </div>

      {loading ? (
        <div className="text-sm text-slate-400">Loading\u2026</div>
      ) : (
        <>
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-600">Needs your review</h2>
            {pending.length === 0 && <p className="text-sm text-slate-400">No drafts waiting. Create one from an application.</p>}
            {pending.map((fu) => {
              const app = appFor(fu);
              return (
                <button key={fu.id} onClick={() => setReviewing(fu)} className="card p-4 w-full text-left block hover:border-brand-200 transition-colors">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold truncate">{app?.job.title || "Application"}</p>
                      <p className="text-xs text-slate-500 truncate">{fu.subject}</p>
                      <p className="flex items-center gap-1 text-xs text-slate-400 mt-1">
                        <Clock size={12} /> {formatDate(fu.suggested_send_at)}
                      </p>
                    </div>
                    <StatusBadge status={fu.status} />
                  </div>
                </button>
              );
            })}
          </div>

          {history.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-sm font-semibold text-slate-600">History</h2>
              {history.map((fu) => {
                const app = appFor(fu);
                return (
                  <div key={fu.id} className="card p-4 flex items-center justify-between gap-3 opacity-70">
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{app?.job.title || "Application"}</p>
                      <p className="text-xs text-slate-500 truncate">{fu.subject}</p>
                    </div>
                    <StatusBadge status={fu.status} />
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {showNew && <NewDraftModal apps={apps} onClose={() => setShowNew(false)} onCreated={upsert} />}
      {reviewing && (
        <ReviewModal fu={reviewing} app={appFor(reviewing)} onClose={() => setReviewing(null)} onUpdated={upsert} />
      )}
    </div>
  );
}

export default function FollowUpsPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <FollowUpsContent />
      </AppShell>
    </ProtectedRoute>
  );
}
