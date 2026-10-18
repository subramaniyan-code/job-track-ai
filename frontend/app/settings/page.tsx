"use client";

import { useEffect, useState } from "react";
import { Trash2, Plug, Mail, Info } from "lucide-react";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import { api, ApiConnection, ConnectorProvider, EmailAccount } from "@/lib/api";

const PROVIDER_FIELDS: Record<ConnectorProvider, { key: string; label: string; placeholder: string }[]> = {
  adzuna: [
    { key: "app_id", label: "App ID", placeholder: "from developer.adzuna.com" },
    { key: "app_key", label: "App Key", placeholder: "from developer.adzuna.com" },
    { key: "country", label: "Country code", placeholder: "in" },
  ],
  greenhouse: [
    { key: "board_tokens", label: "Board tokens (comma-separated)", placeholder: "stripe,airbnb,figma" },
  ],
  lever: [
    { key: "site_names", label: "Site names (comma-separated)", placeholder: "netflix,mistral" },
  ],
  jsearch: [
    { key: "rapidapi_key", label: "RapidAPI key", placeholder: "from rapidapi.com/.../jsearch" },
  ],
};

const PROVIDER_LABELS: Record<ConnectorProvider, string> = {
  adzuna: "Adzuna",
  greenhouse: "Greenhouse (public boards)",
  lever: "Lever (public postings)",
  jsearch: "JSearch (RapidAPI)",
};

function ConnectorsSection() {
  const [connections, setConnections] = useState<ApiConnection[]>([]);
  const [provider, setProvider] = useState<ConnectorProvider>("adzuna");
  const [label, setLabel] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  function refresh() {
    api.get<ApiConnection[]>("/connectors").then(setConnections);
  }
  useEffect(refresh, []);

  async function addConnector() {
    setSaving(true);
    try {
      await api.post("/connectors", { provider, label: label || null, credentials: fields });
      setFields({});
      setLabel("");
      refresh();
    } finally {
      setSaving(false);
    }
  }

  async function removeConnector(id: string) {
    await api.del(`/connectors/${id}`);
    refresh();
  }

  return (
    <div className="card p-5 space-y-5">
      <div className="flex items-center gap-2">
        <Plug size={18} className="text-brand-600" />
        <h2 className="font-semibold">Job source connections</h2>
      </div>
      <p className="text-sm text-slate-500 -mt-3">
        Connect free job-board APIs. Adzuna and JSearch need a free key from their site; Greenhouse and Lever need no key \u2014 just the company board names you want to track.
      </p>

      <div className="space-y-3">
        {connections.map((c) => (
          <div key={c.id} className="flex items-center justify-between border border-[var(--border)] rounded-xl px-3 py-2.5">
            <div>
              <p className="text-sm font-medium">{PROVIDER_LABELS[c.provider]}</p>
              {c.label && <p className="text-xs text-slate-400">{c.label}</p>}
            </div>
            <button onClick={() => removeConnector(c.id)} className="btn-ghost p-1.5 text-rose-500">
              <Trash2 size={15} />
            </button>
          </div>
        ))}
        {connections.length === 0 && <p className="text-xs text-slate-400">No sources connected yet.</p>}
      </div>

      <div className="border-t border-[var(--border)] pt-4 space-y-3">
        <div>
          <label className="label">Provider</label>
          <select
            className="input"
            value={provider}
            onChange={(e) => {
              setProvider(e.target.value as ConnectorProvider);
              setFields({});
            }}
          >
            {Object.entries(PROVIDER_LABELS).map(([key, l]) => (
              <option key={key} value={key}>{l}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Label (optional)</label>
          <input className="input" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. my personal key" />
        </div>
        {PROVIDER_FIELDS[provider].map((f) => (
          <div key={f.key}>
            <label className="label">{f.label}</label>
            <input
              className="input"
              value={fields[f.key] || ""}
              onChange={(e) => setFields((prev) => ({ ...prev, [f.key]: e.target.value }))}
              placeholder={f.placeholder}
            />
          </div>
        ))}
        <button onClick={addConnector} disabled={saving} className="btn btn-primary w-full">
          {saving ? "Connecting\u2026" : "Connect"}
        </button>
      </div>
    </div>
  );
}

function EmailAccountSection() {
  const [account, setAccount] = useState<EmailAccount | null>(null);
  const [smtpHost, setSmtpHost] = useState("smtp.gmail.com");
  const [smtpPort, setSmtpPort] = useState(587);
  const [smtpUsername, setSmtpUsername] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [fromName, setFromName] = useState("");
  const [imapEnabled, setImapEnabled] = useState(false);
  const [imapHost, setImapHost] = useState("");
  const [imapPort, setImapPort] = useState(993);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get<EmailAccount | null>("/email-account").then((acc) => {
      if (acc) {
        setAccount(acc);
        setSmtpHost(acc.smtp_host);
        setSmtpPort(acc.smtp_port);
        setSmtpUsername(acc.smtp_username);
        setFromName(acc.from_name || "");
        setImapEnabled(acc.imap_enabled);
        setImapHost(acc.imap_host || "");
        setImapPort(acc.imap_port || 993);
      }
    });
  }, []);

  async function save() {
    setSaving(true);
    setSaved(false);
    try {
      const acc = await api.put<EmailAccount>("/email-account", {
        smtp_host: smtpHost,
        smtp_port: smtpPort,
        smtp_username: smtpUsername,
        smtp_password: smtpPassword,
        from_name: fromName || null,
        imap_enabled: imapEnabled,
        imap_host: imapHost || null,
        imap_port: imapPort,
      });
      setAccount(acc);
      setSmtpPassword("");
      setImapHost(acc.imap_host || "");
      setSaved(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Mail size={18} className="text-brand-600" />
        <h2 className="font-semibold">Email for follow-ups &amp; inbox analysis</h2>
      </div>
      <div className="flex items-start gap-2 text-xs text-slate-500 bg-slate-50 rounded-lg px-3 py-2">
        <Info size={14} className="shrink-0 mt-0.5" />
        <span>For Gmail/Outlook, use an <strong>app password</strong> (not your normal login password) \u2014 generate one from your account&apos;s security settings. This same password is used for both sending follow-ups and reading your inbox.</span>
      </div>
      {account && <p className="text-xs text-emerald-600">Connected as {account.smtp_username}</p>}
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <label className="label">SMTP host (for sending)</label>
          <input className="input" value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} />
        </div>
        <div>
          <label className="label">Port</label>
          <input className="input" type="number" value={smtpPort} onChange={(e) => setSmtpPort(Number(e.target.value))} />
        </div>
        <div>
          <label className="label">From name</label>
          <input className="input" value={fromName} onChange={(e) => setFromName(e.target.value)} placeholder="Your Name" />
        </div>
        <div className="col-span-2">
          <label className="label">Email address</label>
          <input className="input" type="email" value={smtpUsername} onChange={(e) => setSmtpUsername(e.target.value)} />
        </div>
        <div className="col-span-2">
          <label className="label">App password</label>
          <input className="input" type="password" value={smtpPassword} onChange={(e) => setSmtpPassword(e.target.value)} placeholder={account ? "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022 (leave blank to keep current)" : ""} />
        </div>
      </div>

      <div className="border-t border-[var(--border)] pt-4 space-y-3">
        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" checked={imapEnabled} onChange={(e) => setImapEnabled(e.target.checked)} />
          Analyze my inbox for job replies &amp; alerts
        </label>
        <p className="text-xs text-slate-500 -mt-1">
          Reads job-related emails (Naukri, LinkedIn, Indeed, application confirmations, interview invites, etc.) every ~25 minutes and shows them on your dashboard. Nothing is ever sent from your inbox \u2014 this is read-only.
        </p>
        {imapEnabled && (
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="label">IMAP host</label>
              <input className="input" value={imapHost} onChange={(e) => setImapHost(e.target.value)} placeholder="auto-detected for Gmail/Outlook/Yahoo, or enter your provider's IMAP host" />
            </div>
            <div>
              <label className="label">IMAP port</label>
              <input className="input" type="number" value={imapPort} onChange={(e) => setImapPort(Number(e.target.value))} />
            </div>
          </div>
        )}
      </div>

      <button onClick={save} disabled={saving} className="btn btn-primary w-full">
        {saving ? "Saving\u2026" : "Save email settings"}
      </button>
      {saved && <p className="text-xs text-emerald-600 text-center">Saved.</p>}
    </div>
  );
}

function SettingsContent() {
  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-sm text-slate-500">Connect your job sources and your email account.</p>
      </div>
      <ConnectorsSection />
      <EmailAccountSection />
    </div>
  );
}

export default function SettingsPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <SettingsContent />
      </AppShell>
    </ProtectedRoute>
  );
}
