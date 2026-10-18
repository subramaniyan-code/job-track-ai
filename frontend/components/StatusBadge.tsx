const STYLES: Record<string, string> = {
  saved: "bg-slate-100 text-slate-600",
  applied: "bg-blue-50 text-blue-700",
  interviewing: "bg-amber-50 text-amber-700",
  offer: "bg-emerald-50 text-emerald-700",
  rejected: "bg-rose-50 text-rose-700",
  ghosted: "bg-slate-100 text-slate-500",
  draft: "bg-slate-100 text-slate-600",
  approved: "bg-blue-50 text-blue-700",
  sent: "bg-emerald-50 text-emerald-700",
  skipped: "bg-slate-100 text-slate-400",
};

export default function StatusBadge({ status }: { status: string }) {
  return <span className={`badge ${STYLES[status] || STYLES.saved}`}>{status}</span>;
}
