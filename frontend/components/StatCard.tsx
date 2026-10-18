import { LucideIcon } from "lucide-react";

export default function StatCard({
  label, value, icon: Icon, tone = "default",
}: { label: string; value: string | number; icon: LucideIcon; tone?: "default" | "brand" | "green" | "amber" | "red" }) {
  const tones: Record<string, string> = {
    default: "bg-slate-100 text-slate-600",
    brand: "bg-brand-50 text-brand-700",
    green: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
    red: "bg-rose-50 text-rose-700",
  };
  return (
    <div className="card p-4 flex items-center gap-3">
      <div className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 ${tones[tone]}`}>
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <p className="text-2xl font-bold leading-tight">{value}</p>
        <p className="text-xs text-slate-500 truncate">{label}</p>
      </div>
    </div>
  );
}
