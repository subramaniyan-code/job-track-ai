"use client";
import { X } from "lucide-react";
import { ReactNode } from "react";

export default function Modal({
  title, onClose, children, wide = false,
}: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/40 p-0 md:p-4">
      <div className={`w-full ${wide ? "md:max-w-2xl" : "md:max-w-md"} bg-white rounded-t-2xl md:rounded-2xl max-h-[90vh] overflow-y-auto`}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)] sticky top-0 bg-white">
          <h3 className="font-semibold">{title}</h3>
          <button onClick={onClose} className="btn-ghost p-1.5"><X size={18} /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}
