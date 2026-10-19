"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, AlertCircle, ExternalLink, Briefcase } from "lucide-react";
import { api, Application } from "@/lib/api";
import ProtectedRoute from "@/components/ProtectedRoute";

function QuickAddContent() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"saving" | "success" | "error">("saving");
  const [errorMsg, setErrorMsg] = useState("");
  const [appData, setAppData] = useState<Application | null>(null);

  const title = searchParams.get("title") || "Untitled Job";
  const company = searchParams.get("company") || "";
  const location = searchParams.get("location") || "";
  const url = searchParams.get("url") || "";
  const salary = searchParams.get("salary") || "";
  const initialStatus = (searchParams.get("status") || "applied") as any;

  useEffect(() => {
    let active = true;

    async function track() {
      try {
        const job = await api.post<{ id: string }>("/jobs/manual", {
          title,
          company: company || null,
          location: location || null,
          url: url || null,
        });

        const app = await api.post<Application>("/applications", {
          job_id: job.id,
          status: initialStatus,
          salary_expectation: salary || null,
        });

        if (active) {
          setAppData(app);
          setStatus("success");
        }
      } catch (err: any) {
        if (active) {
          setErrorMsg(err.message || "Failed to save application.");
          setStatus("error");
        }
      }
    }

    track();

    return () => {
      active = false;
    };
  }, [title, company, location, url, salary, initialStatus]);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
      <div className="card p-6 max-w-md w-full shadow-lg border border-[var(--border)] text-center space-y-4">
        {status === "saving" && (
          <div className="space-y-3 py-6">
            <div className="h-10 w-10 border-4 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <h2 className="font-semibold text-lg text-slate-800">Tracking Application…</h2>
            <p className="text-sm text-slate-500 truncate">{title}</p>
          </div>
        )}

        {status === "success" && (
          <div className="space-y-4 py-2">
            <CheckCircle2 size={48} className="text-emerald-500 mx-auto" />
            <div>
              <h2 className="font-bold text-xl text-slate-900">Application Tracked!</h2>
              <p className="text-xs text-slate-500 mt-1">Added to your JobTrack AI board</p>
            </div>

            <div className="bg-slate-100 rounded-xl p-3 text-left space-y-1">
              <p className="text-sm font-semibold text-slate-800">{title}</p>
              {company && <p className="text-xs text-slate-600 font-medium">{company}</p>}
              {location && <p className="text-xs text-slate-400">{location}</p>}
              {salary && <p className="text-xs text-emerald-600 font-medium">💰 {salary}</p>}
              <div className="pt-2 flex items-center gap-2">
                <span className="badge bg-blue-100 text-blue-700 font-medium text-xs">Status: Applied</span>
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={() => window.close()}
                className="btn btn-secondary flex-1 text-sm py-2"
              >
                Close Window
              </button>
              <a
                href="/applications"
                className="btn btn-primary flex-1 text-sm py-2 flex items-center justify-center gap-1.5"
                target="_blank"
                rel="noreferrer"
              >
                View Board <ExternalLink size={14} />
              </a>
            </div>
          </div>
        )}

        {status === "error" && (
          <div className="space-y-4 py-2">
            <AlertCircle size={48} className="text-rose-500 mx-auto" />
            <h2 className="font-bold text-xl text-slate-900">Failed to Track</h2>
            <p className="text-sm text-rose-600">{errorMsg}</p>
            <button
              onClick={() => window.location.reload()}
              className="btn btn-primary w-full text-sm"
            >
              Retry
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function QuickAddPage() {
  return (
    <ProtectedRoute>
      <QuickAddContent />
    </ProtectedRoute>
  );
}
