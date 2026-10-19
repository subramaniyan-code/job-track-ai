"use client";

import { useState } from "react";
import { Search, MapPin, ExternalLink, Plus, Loader2, PenLine, Bookmark } from "lucide-react";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Modal from "@/components/Modal";
import { api, Job } from "@/lib/api";

function BookmarkletModal({ onClose }: { onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const origin = typeof window !== "undefined" ? window.location.origin : "http://100.64.0.2:3100";
  const bookmarkletCode = `javascript:(function(){var t=(document.querySelector('h1.styles_jd-header-title__28b4m')||document.querySelector('h1')||{}).innerText||document.title;var c=(document.querySelector('a.styles_jd-header-comp-name__title__haCK3')||document.querySelector('.comp-name')||document.querySelector('.company-name')||document.querySelector('.job-details-jobs-unified-top-card__company-name')||{}).innerText||'';var l=(document.querySelector('span.styles_jsh-loc__eAal_')||document.querySelector('.loc')||{}).innerText||'';var s=(document.querySelector('div.styles_jsh-sal__wE_c_ span')||document.querySelector('.salary')||{}).innerText||'';var u=window.location.href;window.open('${origin}/quick-add?title='+encodeURIComponent((t||'').trim())+'&company='+encodeURIComponent((c||'').trim())+'&location='+encodeURIComponent((l||'').trim())+'&salary='+encodeURIComponent((s||'').trim())+'&url='+encodeURIComponent(u)+'&status=applied','jt_quick_add','width=520,height=600,scrollbars=yes');})();`;

  function copyCode() {
    navigator.clipboard.writeText(bookmarkletCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <Modal title="1-Click Naukri & LinkedIn Bookmarklet" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          Save any job from <strong>Naukri, LinkedIn, or Indeed</strong> in exactly 1 click without leaving the page!
        </p>

        <div className="border border-brand-200 bg-brand-50 rounded-xl p-4 text-center space-y-3">
          <p className="text-xs font-semibold text-brand-800 uppercase tracking-wide">
            👉 Drag this button to your Bookmarks bar:
          </p>
          <div>
            <a
              href={bookmarkletCode}
              onClick={(e) => e.preventDefault()}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-bold rounded-xl shadow cursor-grab active:cursor-grabbing text-sm"
            >
              📌 Track with JobTrack
            </a>
          </div>
          <p className="text-xs text-slate-500">
            (Or click &ldquo;Copy bookmarklet code&rdquo; below and save it as a browser bookmark)
          </p>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-semibold text-slate-700">How to use it:</p>
          <ol className="text-xs text-slate-600 list-decimal pl-4 space-y-1">
            <li>Open any job on <strong>Naukri.com</strong> or <strong>LinkedIn</strong>.</li>
            <li>Click <strong>&ldquo;Track with JobTrack&rdquo;</strong> in your bookmarks bar.</li>
            <li>It extracts Title, Company, Location, Salary, and Apply Link, and adds it to your <strong>Applications</strong> board!</li>
          </ol>
        </div>

        <div className="pt-2 border-t border-[var(--border)]">
          <button onClick={copyCode} className="btn btn-secondary w-full text-xs py-2">
            {copied ? "Copied to clipboard!" : "Copy bookmarklet code"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

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
          For anything found on Naukri, LinkedIn, Indeed, a company site, or a referral — add it here to track it the same way as a searched result.
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
          {saving ? "Adding…" : "Add & track"}
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
  const [showBookmarklet, setShowBookmarklet] = useState(false);
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
      setError(err.message || "Search failed — check your connected API sources in Settings.");
    } finally {
      setLoading(false);
    }
  }

  async function trackJob(jobId: string) {
    try {
      await api.post("/applications", { job_id: jobId, status: "saved" });
      setTrackedIds((prev) => new Set(prev).add(jobId));
    } catch {
      // no-op
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Find Jobs</h1>
          <p className="text-sm text-slate-500">Searches every job source you've connected in Settings.</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={() => setShowBookmarklet(true)} className="btn btn-secondary flex items-center gap-1.5">
            <Bookmark size={15} /> 1-Click Bookmarklet
          </button>
          <button onClick={() => setShowManual(true)} className="btn btn-primary flex items-center gap-1.5">
            <PenLine size={15} /> Add manually
          </button>
        </div>
      </div>

      {justAdded && (
        <div className="bg-emerald-50 text-emerald-800 text-sm px-4 py-3 rounded-xl border border-emerald-200">
          Job added and saved to your Applications board.
        </div>
      )}

      <form onSubmit={handleSearch} className="card p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="label">Keywords / title</label>
            <div className="relative">
              <Search size={16} className="absolute left-3 top-3 text-slate-400" />
              <input
                className="input pl-9"
                placeholder="e.g. Python, Azure, DevOps"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="label">Location</label>
            <div className="relative">
              <MapPin size={16} className="absolute left-3 top-3 text-slate-400" />
              <input
                className="input pl-9"
                placeholder="e.g. Bangalore, Mumbai, Remote"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between pt-1">
          <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
            <input
              type="checkbox"
              checked={remoteOnly}
              onChange={(e) => setRemoteOnly(e.target.checked)}
              className="rounded text-brand-600 focus:ring-brand-500"
            />
            Remote roles only
          </label>
          <button type="submit" disabled={loading} className="btn btn-primary text-sm">
            {loading ? <Loader2 size={16} className="animate-spin" /> : "Search jobs"}
          </button>
        </div>
      </form>

      {error && (
        <div className="bg-rose-50 text-rose-800 text-sm p-4 rounded-xl border border-rose-200">
          {error}
        </div>
      )}

      {searched && !loading && jobs.length === 0 && !error && (
        <div className="card p-8 text-center text-slate-500 text-sm">
          No jobs found. Try different keywords or check that Adzuna / JSearch are connected in Settings.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {jobs.map((job) => (
          <div key={job.id} className="card p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-start justify-between gap-2 mb-1">
                <h3 className="font-semibold text-sm line-clamp-1">{job.title}</h3>
                <span className="badge text-[10px] uppercase font-bold tracking-wider">{job.source}</span>
              </div>
              <p className="text-xs text-slate-500 mb-2">{job.company || "Company not listed"} · {job.location || "Location not listed"}</p>
              {job.description && (
                <p className="text-xs text-slate-600 line-clamp-2 mb-3">{job.description}</p>
              )}
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-[var(--border)]">
              <a
                href={job.url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-brand-600 font-medium flex items-center gap-1 hover:underline"
              >
                View posting <ExternalLink size={12} />
              </a>
              <button
                onClick={() => trackJob(job.id)}
                disabled={trackedIds.has(job.id)}
                className="btn btn-primary text-xs py-1 px-2.5"
              >
                <Plus size={13} /> {trackedIds.has(job.id) ? "Tracked" : "Track"}
              </button>
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

      {showBookmarklet && (
        <BookmarkletModal onClose={() => setShowBookmarklet(false)} />
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
