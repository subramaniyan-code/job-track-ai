"use client";

import { useState } from "react";
import { Search, MapPin, ExternalLink, Plus, Loader2, PenLine } from "lucide-react";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Modal from "@/components/Modal";
import { api, Job } from "@/lib/api";

function ManualAddModal({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);

  async function save() {
    if (!title.trim()) return;
    setSaving(true);
    try {
      const job = await api.post<Job>("/jobs/manual", {
        title, company: company || null, location: location || null, url: url || null, description: description || null,
      });
      await api.post("/applications", { job_id: job.id, status: "saved" });
      onAdded();
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title="Add a job manually" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-xs text-slate-500 -mt-1">
          For anything found on Naukri, LinkedIn, Indeed, a company site, or a referral \u2014 add it here to track it the same way as a searched result.
        </p>
        <div>
          <label className="label">Job title *</label>
          <input className="input" required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Azure Cloud Engineer" />
        </div>
        <div>
          <label className="label">Company</label>
          <input className="input" value={company} onChange={(e) => setCompany(e.target.value)} />
        </div>
        <div>
          <label className="label">Location</label>
          <input className="input" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. Chennai, or Remote" />
        </div>
        <div>
          <label className="label">Posting URL</label>
          <input className="input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="Link to the Naukri/LinkedIn/company listing" />
        </div>
        <div>
          <label className="label">Notes / description</label>
          <textarea className="input" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <button onClick={save} disabled={saving || !title.trim()} className="btn btn-primary w-full">
          {saving ? "Adding\u2026" : "Add & track"}
        </button>
      </div>
    </Modal>
  );
}

function JobsContent() {
  const [keywords, setKeywords] = useState("");
  const [location, setLocation] = useState("");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trackedIds, setTrackedIds] = useState<Set<string>>(new Set());
  const [searched, setSearched] = useState(false);
  const [showManual, setShowManual] = useState(false);
  const [justAdded, setJustAdded] = useState(false);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!keywords.trim()) return;
    setLoading(true);
    setError(null);
    setSearched(true);
    try {
      const results = await api.post<Job[]>("/jobs/search", {
        keywords,
        location: location || undefined,
        remote_only: remoteOnly,
        max_results: 30,
      });
      setJobs(results);
    } catch (err: any) {
      setError(err.message || "Search failed \u2014 check your connected API sources in Settings.");
    } finally {
      setLoading(false);
    }
  }

  async function trackJob(jobId: string) {
    try {
      await api.post("/applications", { job_id: jobId, status: "saved" });
      setTrackedIds((prev) => new Set(prev).add(jobId));
    } catch {
      // no-op — button will just not flip to "Tracked"
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Find Jobs</h1>
          <p className="text-sm text-slate-500">Searches every job source you've connected in Settings.</p>
        </div>
        <button onClick={() => setShowManual(true)} className="btn btn-secondary shrink-0">
          <PenLine size={15} /> Add manually
        </button>
      </div>

      {justAdded && (
        <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2">
          Added and tracked \u2014 find it on your Applications board.
        </div>
      )}

      <form onSubmit={handleSearch} className="card p-4 space-y-3">
        <div className="grid md:grid-cols-[2fr_1fr_auto] gap-3">
          <div>
            <label className="label">Keywords</label>
            <input className="input" required value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="e.g. Azure administrator" />
          </div>
          <div>
            <label className="label">Location</label>
            <input className="input" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. Chennai" />
          </div>
          <div className="flex items-end">
            <button type="submit" disabled={loading} className="btn btn-primary w-full md:w-auto">
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
              Search
            </button>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} />
          Remote only
        </label>
      </form>

      {error && <div className="text-sm text-rose-700 bg-rose-50 border border-rose-100 rounded-lg px-3 py-2">{error}</div>}

      {searched && !loading && jobs.length === 0 && !error && (
        <div className="card p-6 text-center text-sm text-slate-500">
          No results. Try broader keywords, connect a job source in Settings, or use &quot;Add manually&quot; for jobs found on Naukri/LinkedIn/Indeed/a company site.
        </div>
      )}

      <div className="space-y-3">
        {jobs.map((job) => (
          <div key={job.id} className="card p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-semibold">{job.title}</p>
                <p className="text-sm text-slate-600">{job.company || "\u2014"}</p>
                <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                  {job.location && (
                    <span className="flex items-center gap-1"><MapPin size={12} />{job.location}</span>
                  )}
                  {job.remote && <span className="badge bg-emerald-50 text-emerald-700">Remote</span>}
                  <span className="badge bg-slate-100 text-slate-500">{job.source}</span>
                </div>
              </div>
              <div className="flex flex-col gap-2 shrink-0">
                <a href={job.url} target="_blank" rel="noreferrer" className="btn btn-secondary text-xs">
                  <ExternalLink size={14} /> View
                </a>
                <button
                  onClick={() => trackJob(job.id)}
                  disabled={trackedIds.has(job.id)}
                  className="btn btn-primary text-xs"
                >
                  <Plus size={14} /> {trackedIds.has(job.id) ? "Tracked" : "Track"}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {showManual && (
        <ManualAddModal
          onClose={() => setShowManual(false)}
          onAdded={() => {
            setJustAdded(true);
            setTimeout(() => setJustAdded(false), 4000);
          }}
        />
      )}
    </div>
  );
}

export default function JobsPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <JobsContent />
      </AppShell>
    </ProtectedRoute>
  );
}
