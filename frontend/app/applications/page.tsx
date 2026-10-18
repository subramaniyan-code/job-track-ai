"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Edit3, Mail } from "lucide-react";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Modal from "@/components/Modal";
import { api, Application, ApplicationStatus } from "@/lib/api";

const COLUMNS: { key: ApplicationStatus; label: string }[] = [
  { key: "saved", label: "Saved" },
  { key: "applied", label: "Applied" },
  { key: "interviewing", label: "Interviewing" },
  { key: "offer", label: "Offer" },
  { key: "rejected", label: "Rejected" },
  { key: "ghosted", label: "Ghosted" },
];

function EditModal({ app, onClose, onSaved }: { app: Application; onClose: () => void; onSaved: (a: Application) => void }) {
  const [recruiterEmail, setRecruiterEmail] = useState(app.recruiter_email || "");
  const [notes, setNotes] = useState(app.notes || "");
  const [resumeVersion, setResumeVersion] = useState(app.resume_version || "");
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const updated = await api.patch<Application>(`/applications/${app.id}`, {
        recruiter_email: recruiterEmail || null,
        notes: notes || null,
        resume_version: resumeVersion || null,
      });
      onSaved(updated);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title={app.job.title} onClose={onClose}>
      <div className="space-y-4">
        <div>
          <label className="label">Recruiter / contact email</label>
          <input className="input" value={recruiterEmail} onChange={(e) => setRecruiterEmail(e.target.value)} placeholder="recruiter@company.com" />
          <p className="text-xs text-slate-400 mt-1">Needed so follow-up emails know where to send.</p>
        </div>
        <div>
          <label className="label">Resume version used</label>
          <input className="input" value={resumeVersion} onChange={(e) => setResumeVersion(e.target.value)} placeholder="e.g. Azure-focused v3" />
        </div>
        <div>
          <label className="label">Notes</label>
          <textarea className="input" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Interview notes, referral info, etc." />
        </div>
        <button onClick={save} disabled={saving} className="btn btn-primary w-full">
          {saving ? "Saving\u2026" : "Save"}
        </button>
      </div>
    </Modal>
  );
}

function ApplicationsContent() {
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Application | null>(null);

  useEffect(() => {
    api.get<Application[]>("/applications").then(setApps).finally(() => setLoading(false));
  }, []);

  async function changeStatus(app: Application, status: ApplicationStatus) {
    const updated = await api.patch<Application>(`/applications/${app.id}`, { status });
    setApps((prev) => prev.map((a) => (a.id === app.id ? updated : a)));
  }

  async function openApplyLink(app: Application) {
    const res = await api.get<{ apply_url: string }>(`/applications/${app.id}/apply-link`);
    window.open(res.apply_url, "_blank");
    if (app.status === "saved") changeStatus(app, "applied");
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Applications</h1>
        <p className="text-sm text-slate-500">Track every stage, from saved to offer.</p>
      </div>

      {loading ? (
        <div className="text-sm text-slate-400">Loading\u2026</div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-4 -mx-4 px-4 md:mx-0 md:px-0 snap-x">
          {COLUMNS.map((col) => {
            const items = apps.filter((a) => a.status === col.key);
            return (
              <div key={col.key} className="shrink-0 w-72 snap-start">
                <div className="flex items-center justify-between mb-2 px-1">
                  <h3 className="text-sm font-semibold text-slate-600">{col.label}</h3>
                  <span className="text-xs text-slate-400">{items.length}</span>
                </div>
                <div className="space-y-2">
                  {items.map((app) => (
                    <div key={app.id} className="card p-3">
                      <p className="text-sm font-semibold truncate">{app.job.title}</p>
                      <p className="text-xs text-slate-500 truncate">{app.job.company || "\u2014"}</p>
                      {app.fit_score != null && (
                        <p className="text-xs text-brand-600 mt-1">Fit score: {app.fit_score}%</p>
                      )}
                      <div className="flex items-center gap-1.5 mt-2">
                        <select
                          value={app.status}
                          onChange={(e) => changeStatus(app, e.target.value as ApplicationStatus)}
                          className="input text-xs py-1.5 flex-1"
                        >
                          {COLUMNS.map((c) => (
                            <option key={c.key} value={c.key}>{c.label}</option>
                          ))}
                        </select>
                        <button onClick={() => setEditing(app)} className="btn-ghost p-1.5" title="Edit">
                          <Edit3 size={14} />
                        </button>
                        <button onClick={() => openApplyLink(app)} className="btn-ghost p-1.5" title="Open apply link">
                          <ExternalLink size={14} />
                        </button>
                      </div>
                      {app.recruiter_email && (
                        <p className="flex items-center gap-1 text-[11px] text-slate-400 mt-1.5">
                          <Mail size={11} /> {app.recruiter_email}
                        </p>
                      )}
                    </div>
                  ))}
                  {items.length === 0 && (
                    <div className="text-xs text-slate-300 text-center py-6 border border-dashed border-slate-200 rounded-xl">Empty</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {editing && (
        <EditModal
          app={editing}
          onClose={() => setEditing(null)}
          onSaved={(updated) => setApps((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))}
        />
      )}
    </div>
  );
}

export default function ApplicationsPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <ApplicationsContent />
      </AppShell>
    </ProtectedRoute>
  );
}
