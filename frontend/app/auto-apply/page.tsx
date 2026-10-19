"use client";

import { useEffect, useState, useRef } from "react";
import {
  Zap,
  Play,
  RefreshCw,
  UploadCloud,
  FileText,
  Shield,
  Sliders,
  Key,
  ExternalLink,
  Clock,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Sparkles,
  ChevronDown,
  ChevronUp,
  User,
  Briefcase,
  MapPin,
  Check,
  Plus,
  Trash2,
  Save,
  Lock,
} from "lucide-react";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import {
  api,
  CandidateProfile,
  NaukriBotConfig,
  NaukriBotLog,
} from "@/lib/api";

export default function AutoApplyPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <AutoApplyContent />
      </AppShell>
    </ProtectedRoute>
  );
}

function AutoApplyContent() {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [config, setConfig] = useState<NaukriBotConfig | null>(null);
  const [logs, setLogs] = useState<NaukriBotLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningAction, setRunningAction] = useState(false);
  const [savingConfig, setSavingConfig] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingSession, setSavingSession] = useState(false);
  const [savingGeminiKey, setSavingGeminiKey] = useState(false);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [activeTab, setActiveTab] = useState<"activity" | "resume" | "settings">("resume");

  // Profile Form States
  const [fullName, setFullName] = useState("");
  const [candidateEmail, setCandidateEmail] = useState("");
  const [candidatePhone, setCandidatePhone] = useState("");
  const [profileExp, setProfileExp] = useState<number>(4.0);
  const [primaryRoles, setPrimaryRoles] = useState<string[]>([]);
  const [searchQueries, setSearchQueries] = useState<string[]>([]);
  const [preferredLocations, setPreferredLocations] = useState<string[]>([]);
  const [skills, setSkills] = useState<string[]>([]);
  const [summary, setSummary] = useState("");

  // Input states for adding tags
  const [newRoleInput, setNewRoleInput] = useState("");
  const [newQueryInput, setNewQueryInput] = useState("");
  const [newLocationInput, setNewLocationInput] = useState("");
  const [newSkillInput, setNewSkillInput] = useState("");

  // Gemini API Key state
  const [geminiApiKey, setGeminiApiKey] = useState("");
  const [showGeminiBox, setShowGeminiBox] = useState(false);

  // Bot Config Form states
  const [targetKeywords, setTargetKeywords] = useState("");
  const [targetLocations, setTargetLocations] = useState("");
  const [dailyMax, setDailyMax] = useState(5);
  const [runsPerDay, setRunsPerDay] = useState(3);
  const [experienceYears, setExperienceYears] = useState(4);
  const [cookiesJson, setCookiesJson] = useState("");
  const [showCookieGuide, setShowCookieGuide] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);
  const [logFilter, setLogFilter] = useState<string>("all");

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  function syncProfileToState(p: CandidateProfile) {
    setProfile(p);
    setFullName(p.full_name || "");
    setCandidateEmail(p.email || "");
    setCandidatePhone(p.phone || "");
    setProfileExp(p.experience_years || 0);
    setPrimaryRoles(p.primary_roles || []);
    setSearchQueries(p.naukri_search_queries || []);
    setPreferredLocations(p.preferred_locations || []);
    setSkills(p.skills || []);
    setSummary(p.summary || "");
  }

  async function loadData() {
    try {
      const [p, c, l] = await Promise.all([
        api.get<CandidateProfile | null>("/profile").catch(() => null),
        api.get<NaukriBotConfig>("/naukri-bot/config").catch(() => null),
        api.get<NaukriBotLog[]>("/naukri-bot/logs").catch(() => []),
      ]);
      if (p) syncProfileToState(p);
      if (c) {
        setConfig(c);
        setTargetKeywords(c.target_keywords || "");
        setTargetLocations(c.target_locations || "");
        setDailyMax(c.daily_max_applications || 5);
        setRunsPerDay(c.runs_per_day || 3);
        setExperienceYears(c.experience_years || 0);
      }
      if (l) setLogs(l);
    } catch (e: any) {
      console.error("Failed to load auto-apply data:", e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  // Poll status while bot is running
  useEffect(() => {
    if (config?.status === "running") {
      const interval = setInterval(() => {
        api.get<NaukriBotConfig>("/naukri-bot/config").then((updated) => {
          setConfig(updated);
          if (updated.status !== "running") {
            api.get<NaukriBotLog[]>("/naukri-bot/logs").then(setLogs);
          }
        });
      }, 8000);
      return () => clearInterval(interval);
    }
  }, [config?.status]);

  async function handleToggleBot(enable: boolean) {
    if (!config) return;
    try {
      const updated = await api.put<NaukriBotConfig>("/naukri-bot/config", { enabled: enable });
      setConfig(updated);
      setActionMessage({
        type: "success",
        text: enable ? "Auto-Apply bot enabled! Scheduled sessions will run during daytime hours." : "Auto-Apply bot paused.",
      });
    } catch (e: any) {
      setActionMessage({ type: "error", text: e.message || "Failed to update bot state" });
    }
  }

  async function handleSaveSettings() {
    setSavingConfig(true);
    setActionMessage(null);
    try {
      const updated = await api.put<NaukriBotConfig>("/naukri-bot/config", {
        target_keywords: targetKeywords.trim(),
        target_locations: targetLocations.trim(),
        daily_max_applications: Number(dailyMax),
        runs_per_day: Number(runsPerDay),
        experience_years: Number(experienceYears),
      });
      setConfig(updated);
      setActionMessage({ type: "success", text: "Bot settings updated successfully." });
    } catch (e: any) {
      setActionMessage({ type: "error", text: e.message || "Failed to save settings" });
    } finally {
      setSavingConfig(false);
    }
  }

  async function handleSaveProfile() {
    setSavingProfile(true);
    setActionMessage(null);
    try {
      const updated = await api.put<CandidateProfile>("/profile", {
        full_name: fullName.trim() || null,
        email: candidateEmail.trim() || null,
        phone: candidatePhone.trim() || null,
        experience_years: Number(profileExp),
        primary_roles: primaryRoles,
        naukri_search_queries: searchQueries,
        preferred_locations: preferredLocations,
        skills: skills,
        summary: summary.trim() || null,
      });
      syncProfileToState(updated);

      // Refresh bot config too since keywords automatically sync
      const updatedConfig = await api.get<NaukriBotConfig>("/naukri-bot/config");
      setConfig(updatedConfig);
      setTargetKeywords(updatedConfig.target_keywords || "");
      setTargetLocations(updatedConfig.target_locations || "");
      setExperienceYears(updatedConfig.experience_years || 0);

      setActionMessage({
        type: "success",
        text: "Candidate profile and search keywords saved successfully! Naukri bot targeting updated.",
      });
    } catch (e: any) {
      setActionMessage({ type: "error", text: e.message || "Failed to save profile" });
    } finally {
      setSavingProfile(false);
    }
  }

  async function handleSaveGeminiKey() {
    if (!geminiApiKey.trim()) return;
    setSavingGeminiKey(true);
    setActionMessage(null);
    try {
      const updated = await api.put<CandidateProfile>("/profile", {
        google_ai_api_key: geminiApiKey.trim(),
      });
      syncProfileToState(updated);
      setGeminiApiKey("");
      setActionMessage({
        type: "success",
        text: "Google Gemini API key securely saved! Future resume uploads will use your Gemini AI key.",
      });
    } catch (e: any) {
      setActionMessage({ type: "error", text: e.message || "Failed to save Gemini key" });
    } finally {
      setSavingGeminiKey(false);
    }
  }

  async function handleSaveSession() {
    if (!cookiesJson.trim()) {
      setActionMessage({ type: "error", text: "Please paste your exported cookies JSON." });
      return;
    }
    setSavingSession(true);
    setActionMessage(null);
    try {
      const updated = await api.post<NaukriBotConfig>("/naukri-bot/session", {
        cookies_json: cookiesJson.trim(),
      });
      setConfig(updated);
      setCookiesJson("");
      setActionMessage({
        type: "success",
        text: "Naukri session cookies securely encrypted and saved! Your homelab bot is ready to connect without OTP.",
      });
    } catch (e: any) {
      setActionMessage({ type: "error", text: e.message || "Failed to save session cookies" });
    } finally {
      setSavingSession(false);
    }
  }

  async function handleRunNow() {
    if (!config?.has_session) {
      setActionMessage({
        type: "error",
        text: "Please add your Naukri session cookies in the Settings tab first.",
      });
      setActiveTab("settings");
      return;
    }
    setRunningAction(true);
    setActionMessage(null);
    try {
      const res = await api.post<{ status: string; message: string }>("/naukri-bot/run-now");
      setActionMessage({
        type: "info",
        text: res.message || "Stealth Naukri browsing session started in the background. Checking jobs...",
      });
      setConfig((prev) => (prev ? { ...prev, status: "running" } : prev));
      setActiveTab("activity");
    } catch (e: any) {
      setActionMessage({ type: "error", text: e.message || "Failed to start session" });
    } finally {
      setRunningAction(false);
    }
  }

  async function handleResumeUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const lowerName = file.name.toLowerCase();
    if (!lowerName.endsWith(".pdf") && !lowerName.endsWith(".docx") && !lowerName.endsWith(".doc") && !lowerName.endsWith(".txt")) {
      setActionMessage({ type: "error", text: "Please upload a PDF (.pdf), Microsoft Word (.docx, .doc), or Text file." });
      return;
    }

    setUploadingResume(true);
    setActionMessage({
      type: "info",
      text: "Analyzing resume structure, roles, and technical skills...",
    });

    const formData = new FormData();
    formData.append("file", file);

    try {
      const updatedProfile = await api.upload<CandidateProfile>("/profile/resume", formData);
      syncProfileToState(updatedProfile);

      // Refresh bot config too since keywords auto-sync
      const updatedConfig = await api.get<NaukriBotConfig>("/naukri-bot/config");
      setConfig(updatedConfig);
      setTargetKeywords(updatedConfig.target_keywords || "");
      setTargetLocations(updatedConfig.target_locations || "");
      setExperienceYears(updatedConfig.experience_years || 0);

      const sourceLabel = updatedProfile.parser_source === "gemini" ? "Google Gemini AI" : "High-Precision Heuristic";
      setActionMessage({
        type: "success",
        text: `Resume parsed with ${sourceLabel}! Extracted ${updatedProfile.primary_roles?.length || 0} roles and ${updatedProfile.skills?.length || 0} skills for ${updatedProfile.full_name}.`,
      });
      setActiveTab("resume");
    } catch (err: any) {
      setActionMessage({ type: "error", text: err.message || "Failed to parse resume" });
    } finally {
      setUploadingResume(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  // Tag manipulation helpers
  function addTag(list: string[], setList: (l: string[]) => void, item: string, setInput: (s: string) => void) {
    const clean = item.trim();
    if (clean && !list.includes(clean)) {
      setList([...list, clean]);
    }
    setInput("");
  }

  function removeTag(list: string[], setList: (l: string[]) => void, index: number) {
    setList(list.filter((_, i) => i !== index));
  }

  const filteredLogs = logs.filter((log) => {
    if (logFilter === "all") return true;
    return log.action === logFilter;
  });

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[500px]">
        <div className="flex flex-col items-center gap-3 text-slate-500">
          <RefreshCw className="animate-spin text-brand-600" size={32} />
          <p className="text-sm font-medium">Loading Auto-Apply Bot engine...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto space-y-6">
      {/* Top Banner / Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="h-10 w-10 rounded-xl bg-amber-500/10 text-amber-600 flex items-center justify-center font-bold">
              <Zap size={22} className="text-amber-500 fill-amber-500" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">Naukri Auto-Apply Copilot</h1>
              <p className="text-sm text-slate-500">
                Stealth Playwright bot on your homelab server. Applies exclusively to 1-click direct apply jobs.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setLoading(true);
              loadData();
            }}
            className="btn btn-secondary text-xs px-3 py-2"
            title="Refresh logs & status"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>

          <button
            onClick={handleRunNow}
            disabled={runningAction || config?.status === "running"}
            className="btn btn-primary text-xs px-4 py-2 flex items-center gap-2 shadow-sm"
          >
            {config?.status === "running" ? (
              <>
                <RefreshCw size={14} className="animate-spin" />
                Session Running...
              </>
            ) : (
              <>
                <Play size={14} className="fill-white" />
                Run Session Now
              </>
            )}
          </button>
        </div>
      </div>

      {/* Action Notification Alert */}
      {actionMessage && (
        <div
          className={`p-4 rounded-xl flex items-start justify-between gap-3 text-sm border ${
            actionMessage.type === "success"
              ? "bg-emerald-50 text-emerald-900 border-emerald-200"
              : actionMessage.type === "error"
              ? "bg-rose-50 text-rose-900 border-rose-200"
              : "bg-blue-50 text-blue-900 border-blue-200"
          }`}
        >
          <div className="flex items-start gap-2.5">
            {actionMessage.type === "success" && <CheckCircle2 size={18} className="text-emerald-600 mt-0.5" />}
            {actionMessage.type === "error" && <XCircle size={18} className="text-rose-600 mt-0.5" />}
            {actionMessage.type === "info" && <Sparkles size={18} className="text-blue-600 mt-0.5" />}
            <span className="font-medium">{actionMessage.text}</span>
          </div>
          <button
            onClick={() => setActionMessage(null)}
            className="text-slate-400 hover:text-slate-600 text-xs font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {/* Metric & Status Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Status card */}
        <div className="card p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Bot Status</span>
            <span
              className={`badge ${
                config?.status === "running"
                  ? "bg-blue-100 text-blue-800 animate-pulse"
                  : config?.enabled
                  ? "bg-emerald-100 text-emerald-800"
                  : "bg-slate-100 text-slate-700"
              }`}
            >
              {config?.status === "running"
                ? "Running Now"
                : config?.enabled
                ? "Active (Automated)"
                : "Paused"}
            </span>
          </div>
          <div className="pt-1 flex items-center justify-between">
            <span className="text-sm font-medium text-slate-700">Autonomous Schedule</span>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={config?.enabled || false}
                onChange={(e) => handleToggleBot(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
            </label>
          </div>
          <p className="text-xs text-slate-400">
            {config?.enabled
              ? `${config.runs_per_day}x daily runs between 9am - 8pm IST`
              : "Turn on to run 2-4 stealth sessions automatically"}
          </p>
        </div>

        {/* Applications Today */}
        <div className="card p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Applied Today</span>
            <span className="text-xs font-medium text-slate-400">
              Max {config?.daily_max_applications || 5}/day
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">
              {config?.applications_today || 0}
            </span>
            <span className="text-sm text-slate-500">/ {config?.daily_max_applications || 5}</span>
          </div>
          {/* Progress Bar */}
          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
            <div
              className="bg-brand-600 h-2 rounded-full transition-all duration-500"
              style={{
                width: `${Math.min(
                  100,
                  (((config?.applications_today || 0) / (config?.daily_max_applications || 5)) * 100)
                )}%`,
              }}
            />
          </div>
        </div>

        {/* Session Authenticity */}
        <div className="card p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Naukri Login</span>
            {config?.has_session ? (
              <span className="badge bg-emerald-100 text-emerald-800">Connected</span>
            ) : (
              <span className="badge bg-amber-100 text-amber-800">Cookies Needed</span>
            )}
          </div>
          <div className="flex items-center gap-2 pt-1">
            <Key size={18} className={config?.has_session ? "text-emerald-600" : "text-amber-500"} />
            <span className="text-sm font-semibold text-slate-800">
              {config?.has_session ? "Encrypted Session Active" : "No Session Cookies"}
            </span>
          </div>
          <p className="text-xs text-slate-400">
            {config?.has_session ? "Reusing session with zero OTPs needed" : "Paste cookies in Settings tab to start"}
          </p>
        </div>

        {/* AI Resume Status */}
        <div className="card p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Resume Profile</span>
            {profile?.resume_filename ? (
              <span className={`badge ${profile.parser_source === "gemini" ? "bg-purple-100 text-purple-800" : "bg-blue-100 text-blue-800"}`}>
                {profile.parser_source === "gemini" ? "Gemini AI" : "Heuristic"}
              </span>
            ) : (
              <span className="badge bg-slate-100 text-slate-600">No Resume</span>
            )}
          </div>
          <div className="flex items-center gap-2 pt-1 truncate">
            <FileText size={18} className={profile?.resume_filename ? "text-brand-600" : "text-slate-400"} />
            <span className="text-sm font-semibold text-slate-800 truncate">
              {profile?.full_name || profile?.resume_filename || "Upload Resume"}
            </span>
          </div>
          <p className="text-xs text-slate-400 truncate">
            {profile?.primary_roles?.length
              ? `${profile.primary_roles[0]} (${profile.experience_years}y exp)`
              : "Set up keywords below"}
          </p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-[var(--border)] gap-6">
        <button
          onClick={() => setActiveTab("resume")}
          className={`pb-3 font-semibold text-sm transition-colors border-b-2 flex items-center gap-2 ${
            activeTab === "resume"
              ? "border-brand-600 text-brand-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Sparkles size={16} className="text-purple-600" />
          Resume &amp; Search Keywords
        </button>

        <button
          onClick={() => setActiveTab("settings")}
          className={`pb-3 font-semibold text-sm transition-colors border-b-2 flex items-center gap-2 ${
            activeTab === "settings"
              ? "border-brand-600 text-brand-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Sliders size={16} />
          Bot Settings &amp; Cookies
        </button>

        <button
          onClick={() => setActiveTab("activity")}
          className={`pb-3 font-semibold text-sm transition-colors border-b-2 flex items-center gap-2 ${
            activeTab === "activity"
              ? "border-brand-600 text-brand-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Clock size={16} />
          Activity &amp; Audit Log ({logs.length})
        </button>
      </div>

      {/* TAB: RESUME & KEYWORD INTELLIGENCE */}
      {activeTab === "resume" && (
        <div className="space-y-6">
          {/* Card: Upload & Parser Options */}
          <div className="card p-6 space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h3 className="font-bold text-slate-900 flex items-center gap-2">
                  <UploadCloud size={18} className="text-brand-600" />
                  Resume Upload &amp; Intelligent Keyword Extraction
                </h3>
                <p className="text-sm text-slate-500">
                  Upload your resume in <strong>PDF</strong>, <strong>Word (.docx, .doc)</strong>, or <strong>Text</strong> format.
                  You can also manually edit all roles, skills, and search queries below.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowGeminiBox(!showGeminiBox)}
                  className="btn btn-secondary text-xs px-3 py-2 flex items-center gap-1.5"
                >
                  <Key size={14} className="text-purple-600" />
                  {profile?.has_gemini_key ? "Gemini Key Saved" : "Set Gemini Key"}
                  {showGeminiBox ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>

                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleResumeUpload}
                  accept=".pdf,.docx,.doc,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword,text/plain"
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadingResume}
                  className="btn btn-primary text-xs px-4 py-2 flex items-center gap-2 shadow-sm"
                >
                  <UploadCloud size={16} />
                  {uploadingResume ? "Reading Document..." : profile?.resume_filename ? "Upload New Resume" : "Upload Resume (PDF / Word)"}
                </button>
              </div>
            </div>

            {/* Optional Gemini API Key Box */}
            {showGeminiBox && (
              <div className="bg-purple-50/70 border border-purple-200 rounded-xl p-4 text-xs space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-purple-900 flex items-center gap-1.5">
                    <Sparkles size={14} className="text-purple-600" />
                    Google Gemini AI API Key (Free)
                  </span>
                  <a
                    href="https://aistudio.google.com/apikey"
                    target="_blank"
                    rel="noreferrer"
                    className="text-brand-600 hover:underline flex items-center gap-1 font-medium"
                  >
                    Get a free key from Google AI Studio
                    <ExternalLink size={12} />
                  </a>
                </div>
                <p className="text-purple-800 leading-relaxed">
                  Provide your own Google Gemini API key to ensure 100% accurate AI extraction on every upload. It is stored encrypted in your private database.
                </p>
                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="password"
                    value={geminiApiKey}
                    onChange={(e) => setGeminiApiKey(e.target.value)}
                    placeholder={profile?.has_gemini_key ? "••••••••••••••••••••••••• (Key Active)" : "Paste AIzaSy... key here"}
                    className="input text-xs flex-1 bg-white"
                  />
                  <button
                    type="button"
                    onClick={handleSaveGeminiKey}
                    disabled={savingGeminiKey || !geminiApiKey.trim()}
                    className="btn btn-primary text-xs px-3 py-2 bg-purple-700 hover:bg-purple-800"
                  >
                    {savingGeminiKey ? "Saving..." : "Save Key"}
                  </button>
                </div>
              </div>
            )}

            {uploadingResume && (
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl flex items-center gap-3">
                <RefreshCw size={18} className="animate-spin text-blue-600" />
                <span className="text-sm text-blue-900 font-medium">
                  Extracting text and analyzing candidate qualifications...
                </span>
              </div>
            )}

            {/* Parser Source Info Banner */}
            {profile?.parser_message && (
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between text-xs text-slate-700">
                <div className="flex items-center gap-2">
                  <span className={`badge ${profile.parser_source === "gemini" ? "bg-purple-100 text-purple-800" : "bg-blue-100 text-blue-800"}`}>
                    {profile.parser_source === "gemini" ? "Gemini 2.0 Flash AI" : "Heuristic Parser"}
                  </span>
                  <span>{profile.parser_message}</span>
                </div>
              </div>
            )}
          </div>

          {/* Card: Interactive Profile & Manual Keyword Editor */}
          <div className="card p-6 space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-100 pb-4">
              <div>
                <h3 className="font-bold text-slate-900 flex items-center gap-2">
                  <User size={18} className="text-brand-600" />
                  Candidate Profile &amp; Search Targeting
                </h3>
                <p className="text-xs text-slate-500">
                  Review and customize your target roles, skills, experience, and search queries below. Changes will sync to the Naukri Bot.
                </p>
              </div>

              <button
                type="button"
                onClick={handleSaveProfile}
                disabled={savingProfile}
                className="btn btn-primary text-xs px-4 py-2.5 flex items-center gap-2 shadow-sm"
              >
                <Save size={15} />
                {savingProfile ? "Saving Profile..." : "Save Profile & Update Bot Keywords"}
              </button>
            </div>

            {/* Basic Candidate Contact & Experience */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="label">Full Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Subramaniyan Arumugam"
                  className="input text-sm font-medium"
                />
              </div>

              <div>
                <label className="label">Email Address</label>
                <input
                  type="email"
                  value={candidateEmail}
                  onChange={(e) => setCandidateEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="input text-sm"
                />
              </div>

              <div>
                <label className="label">Phone / Mobile</label>
                <input
                  type="text"
                  value={candidatePhone}
                  onChange={(e) => setCandidatePhone(e.target.value)}
                  placeholder="+91 88258 39860"
                  className="input text-sm"
                />
              </div>

              <div>
                <label className="label">Experience (Years)</label>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  max="40"
                  value={profileExp}
                  onChange={(e) => setProfileExp(Number(e.target.value))}
                  className="input text-sm font-semibold"
                />
              </div>
            </div>

            {/* Interactive Target Roles */}
            <div className="space-y-2 border-t border-slate-100 pt-4">
              <label className="label">Primary Target Roles (What positions should you match?)</label>
              <div className="flex flex-wrap gap-2 items-center">
                {primaryRoles.map((role, idx) => (
                  <span
                    key={idx}
                    className="badge bg-blue-50 text-blue-900 border border-blue-200 text-xs py-1 px-2.5 flex items-center gap-1.5"
                  >
                    {role}
                    <button
                      type="button"
                      onClick={() => removeTag(primaryRoles, setPrimaryRoles, idx)}
                      className="text-blue-500 hover:text-rose-600 font-bold ml-1 text-sm"
                      title="Remove role"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-2 max-w-md pt-1">
                <input
                  type="text"
                  value={newRoleInput}
                  onChange={(e) => setNewRoleInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addTag(primaryRoles, setPrimaryRoles, newRoleInput, setNewRoleInput);
                    }
                  }}
                  placeholder="e.g. Cloud & Infrastructure Engineer, Azure Administrator"
                  className="input text-xs"
                />
                <button
                  type="button"
                  onClick={() => addTag(primaryRoles, setPrimaryRoles, newRoleInput, setNewRoleInput)}
                  className="btn btn-secondary text-xs px-3 py-2 flex items-center gap-1 whitespace-nowrap"
                >
                  <Plus size={14} /> Add Role
                </button>
              </div>
            </div>

            {/* Interactive Naukri Search Queries */}
            <div className="space-y-2 border-t border-slate-100 pt-4">
              <label className="label">Generated Naukri Search Queries (Used directly by the Playwright bot)</label>
              <div className="flex flex-wrap gap-2 items-center">
                {searchQueries.map((query, idx) => (
                  <span
                    key={idx}
                    className="badge bg-purple-50 text-purple-900 border border-purple-200 text-xs py-1 px-2.5 flex items-center gap-1.5"
                  >
                    {query}
                    <button
                      type="button"
                      onClick={() => removeTag(searchQueries, setSearchQueries, idx)}
                      className="text-purple-500 hover:text-rose-600 font-bold ml-1 text-sm"
                      title="Remove query"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-2 max-w-md pt-1">
                <input
                  type="text"
                  value={newQueryInput}
                  onChange={(e) => setNewQueryInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addTag(searchQueries, setSearchQueries, newQueryInput, setNewQueryInput);
                    }
                  }}
                  placeholder="e.g. Azure Cloud Engineer Chennai, DevOps Engineer"
                  className="input text-xs"
                />
                <button
                  type="button"
                  onClick={() => addTag(searchQueries, setSearchQueries, newQueryInput, setNewQueryInput)}
                  className="btn btn-secondary text-xs px-3 py-2 flex items-center gap-1 whitespace-nowrap"
                >
                  <Plus size={14} /> Add Query
                </button>
              </div>
            </div>

            {/* Preferred Locations */}
            <div className="space-y-2 border-t border-slate-100 pt-4">
              <label className="label">Preferred Job Locations</label>
              <div className="flex flex-wrap gap-2 items-center">
                {preferredLocations.map((loc, idx) => (
                  <span
                    key={idx}
                    className="badge bg-emerald-50 text-emerald-900 border border-emerald-200 text-xs py-1 px-2.5 flex items-center gap-1.5"
                  >
                    <MapPin size={12} className="text-emerald-600" />
                    {loc}
                    <button
                      type="button"
                      onClick={() => removeTag(preferredLocations, setPreferredLocations, idx)}
                      className="text-emerald-500 hover:text-rose-600 font-bold ml-1 text-sm"
                      title="Remove location"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-2 max-w-md pt-1">
                <input
                  type="text"
                  value={newLocationInput}
                  onChange={(e) => setNewLocationInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addTag(preferredLocations, setPreferredLocations, newLocationInput, setNewLocationInput);
                    }
                  }}
                  placeholder="e.g. Chennai, Bengaluru, Remote"
                  className="input text-xs"
                />
                <button
                  type="button"
                  onClick={() => addTag(preferredLocations, setPreferredLocations, newLocationInput, setNewLocationInput)}
                  className="btn btn-secondary text-xs px-3 py-2 flex items-center gap-1 whitespace-nowrap"
                >
                  <Plus size={14} /> Add City
                </button>
              </div>
            </div>

            {/* Extracted Skills */}
            <div className="space-y-2 border-t border-slate-100 pt-4">
              <label className="label">Extracted Technical Skills ({skills.length})</label>
              <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto p-1 bg-slate-50 rounded-xl border border-slate-100">
                {skills.map((skill, idx) => (
                  <span
                    key={idx}
                    className="badge bg-white text-slate-800 border border-slate-200 text-xs py-1 px-2 flex items-center gap-1"
                  >
                    {skill}
                    <button
                      type="button"
                      onClick={() => removeTag(skills, setSkills, idx)}
                      className="text-slate-400 hover:text-rose-600 font-bold ml-0.5 text-xs"
                      title="Remove skill"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-2 max-w-md pt-1">
                <input
                  type="text"
                  value={newSkillInput}
                  onChange={(e) => setNewSkillInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addTag(skills, setSkills, newSkillInput, setNewSkillInput);
                    }
                  }}
                  placeholder="e.g. Azure, Docker, Tailscale, Terraform"
                  className="input text-xs"
                />
                <button
                  type="button"
                  onClick={() => addTag(skills, setSkills, newSkillInput, setNewSkillInput)}
                  className="btn btn-secondary text-xs px-3 py-2 flex items-center gap-1 whitespace-nowrap"
                >
                  <Plus size={14} /> Add Skill
                </button>
              </div>
            </div>

            {/* Executive Summary */}
            <div className="space-y-2 border-t border-slate-100 pt-4">
              <label className="label">Candidate Executive Summary</label>
              <textarea
                rows={3}
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                placeholder="Brief summary of candidate experience and certifications..."
                className="input text-xs leading-relaxed"
              />
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={handleSaveProfile}
                disabled={savingProfile}
                className="btn btn-primary text-xs px-5 py-2.5 flex items-center gap-2 shadow-sm"
              >
                <Save size={15} />
                {savingProfile ? "Saving Changes..." : "Save Candidate Profile & Update Bot Keywords"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB: BOT SETTINGS & COOKIES */}
      {activeTab === "settings" && (
        <div className="space-y-6">
          {/* Card: Session Authentication (Zero OTPs) */}
          <div className="card p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-bold text-slate-900 flex items-center gap-2">
                  <Key size={18} className="text-amber-500" />
                  Naukri Session Authentication (Zero Daily OTPs)
                </h3>
                <p className="text-sm text-slate-500 mt-0.5">
                  The bot uses your active Naukri session cookies stored with Fernet encryption on your private server. It never logs in with passwords or triggers OTP alerts.
                </p>
              </div>

              <button
                type="button"
                onClick={() => setShowCookieGuide(!showCookieGuide)}
                className="btn btn-secondary text-xs px-3 py-1.5 flex items-center gap-1"
              >
                <HelpCircle size={14} />
                {showCookieGuide ? "Hide Guide" : "How to get cookies (30s)"}
                {showCookieGuide ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
            </div>

            {/* Step-by-step Cookie Extraction Guide */}
            {showCookieGuide && (
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs text-slate-700 space-y-2.5">
                <p className="font-semibold text-slate-900">How to export cookies from your normal browser:</p>
                <ol className="list-decimal list-inside space-y-1.5 ml-1">
                  <li>
                    Log in to <a href="https://www.naukri.com" target="_blank" rel="noreferrer" className="text-brand-600 underline font-medium">naukri.com</a> in your regular Chrome, Edge, or Brave browser.
                  </li>
                  <li>
                    Install the free Chrome extension <strong>Cookie-Editor</strong> (or use DevTools &gt; Application &gt; Cookies &gt; naukri.com).
                  </li>
                  <li>
                    Open the Cookie-Editor extension icon on Naukri.com and click the <strong>Export</strong> button at the bottom right &rarr; choose <strong>Export as JSON</strong>.
                  </li>
                  <li>
                    Paste the copied JSON text into the box below and click <strong>Encrypt &amp; Save Session</strong>.
                  </li>
                </ol>
                <p className="text-slate-500 italic pt-1">
                  * Note: Naukri cookies usually stay valid for 30–60 days. You only need to update this if Naukri logs you out.
                </p>
              </div>
            )}

            {/* Cookies Input Box */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-600 block">
                Paste Naukri Cookies JSON:
              </label>
              <textarea
                rows={4}
                value={cookiesJson}
                onChange={(e) => setCookiesJson(e.target.value)}
                placeholder='[{"name": "naukri_id", "value": "..."}, {"name": "sessionId", "value": "..."}]'
                className="input font-mono text-xs"
              />
              <div className="flex items-center justify-between pt-1">
                <span className="text-xs text-slate-400">
                  {config?.has_session
                    ? "✓ Session currently active on server."
                    : "No session configured yet."}
                </span>
                <button
                  type="button"
                  onClick={handleSaveSession}
                  disabled={savingSession || !cookiesJson.trim()}
                  className="btn btn-primary text-xs px-4 py-2"
                >
                  {savingSession ? "Saving..." : "Encrypt & Save Session"}
                </button>
              </div>
            </div>
          </div>

          {/* Card: Bot Search & Guardrail Configuration */}
          <div className="card p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="font-bold text-slate-900 flex items-center gap-2">
                  <Shield size={18} className="text-brand-600" />
                  Bot Search Parameters &amp; Anti-Flagging Safeguards
                </h3>
                <p className="text-xs text-slate-500">
                  Carefully tuned to mimic natural human behavior with random delays, smooth scrolling, and strict daily caps.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="label">Target Search Keywords / Queries</label>
                <input
                  type="text"
                  value={targetKeywords}
                  onChange={(e) => setTargetKeywords(e.target.value)}
                  placeholder="e.g. Cloud Infrastructure Engineer, Azure Administrator"
                  className="input text-sm"
                />
                <span className="text-xs text-slate-400 mt-1 block">
                  Comma-separated keywords to search on Naukri. Pre-filled from your profile queries.
                </span>
              </div>

              <div>
                <label className="label">Target Locations</label>
                <input
                  type="text"
                  value={targetLocations}
                  onChange={(e) => setTargetLocations(e.target.value)}
                  placeholder="e.g. Chennai, Bengaluru, Remote"
                  className="input text-sm"
                />
                <span className="text-xs text-slate-400 mt-1 block">
                  Leave blank or specify cities to filter search results.
                </span>
              </div>

              <div>
                <label className="label">Daily Max Applications Cap</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={dailyMax}
                  onChange={(e) => setDailyMax(Number(e.target.value))}
                  className="input text-sm"
                />
                <span className="text-xs text-slate-400 mt-1 block">
                  Hard safety cap (1–10/day). Keeps your Naukri account completely safe from algorithmic flags.
                </span>
              </div>

              <div>
                <label className="label">Stealth Sessions Per Day</label>
                <input
                  type="number"
                  min={1}
                  max={4}
                  value={runsPerDay}
                  onChange={(e) => setRunsPerDay(Number(e.target.value))}
                  className="input text-sm"
                />
                <span className="text-xs text-slate-400 mt-1 block">
                  Distributed randomly across daytime working hours (9:00 AM – 8:00 PM IST).
                </span>
              </div>

              <div>
                <label className="label">Candidate Experience (Years)</label>
                <input
                  type="number"
                  min={0}
                  max={30}
                  value={experienceYears}
                  onChange={(e) => setExperienceYears(Number(e.target.value))}
                  className="input text-sm"
                />
                <span className="text-xs text-slate-400 mt-1 block">
                  Matches Naukri experience slider filter.
                </span>
              </div>
            </div>

            {/* Direct Apply Only Guarantee */}
            <div className="bg-amber-50/70 border border-amber-200/60 rounded-xl p-4 text-xs text-amber-900 space-y-1.5">
              <div className="font-semibold flex items-center gap-1.5 text-amber-900">
                <CheckCircle2 size={15} className="text-amber-600" />
                Guaranteed 1-Click Direct Apply Only
              </div>
              <p className="text-amber-800 leading-relaxed">
                The Playwright bot will only click &ldquo;Apply&rdquo; when Naukri directly submits your profile resume. If a job attempts to redirect to external ATS portals (Workday, Taleo, Greenhouse) or prompts an interactive screening questionnaire, the bot immediately cancels and logs it as skipped.
              </p>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={handleSaveSettings}
                disabled={savingConfig}
                className="btn btn-primary text-xs px-5 py-2.5"
              >
                {savingConfig ? "Saving..." : "Save Bot Parameters"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB: ACTIVITY AUDIT LOG */}
      {activeTab === "activity" && (
        <div className="space-y-4">
          <div className="card p-5 space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div>
                <h3 className="font-bold text-slate-900">Application Audit Trail</h3>
                <p className="text-xs text-slate-500">
                  Every job card inspected by Playwright is recorded with its outcome and reason.
                </p>
              </div>

              {/* Filter pills */}
              <div className="flex flex-wrap items-center gap-1.5">
                {[
                  { id: "all", label: "All" },
                  { id: "applied", label: "Applied" },
                  { id: "skipped_redirect", label: "Skipped (Redirects)" },
                  { id: "skipped_questions", label: "Skipped (Questions)" },
                  { id: "already_applied", label: "Already Applied" },
                  { id: "failed", label: "Failed" },
                ].map((pill) => (
                  <button
                    key={pill.id}
                    onClick={() => setLogFilter(pill.id)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                      logFilter === pill.id
                        ? "bg-brand-600 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {pill.label}
                  </button>
                ))}
              </div>
            </div>

            {filteredLogs.length === 0 ? (
              <div className="py-12 text-center text-slate-400 space-y-2">
                <Clock size={32} className="mx-auto opacity-40" />
                <p className="text-sm font-medium text-slate-600">No activity logs recorded yet</p>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  Click &ldquo;Run Session Now&rdquo; above or enable the autonomous schedule to let the stealth Playwright bot browse Naukri.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      <th className="py-2.5 px-3">Time (IST)</th>
                      <th className="py-2.5 px-3">Job Title &amp; Company</th>
                      <th className="py-2.5 px-3">Location</th>
                      <th className="py-2.5 px-3">Action</th>
                      <th className="py-2.5 px-3">Details / Reason</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredLogs.map((log) => {
                      const dateStr = new Date(log.created_at).toLocaleString("en-IN", {
                        timeZone: "Asia/Kolkata",
                        dateStyle: "short",
                        timeStyle: "short",
                      });

                      return (
                        <tr key={log.id} className="hover:bg-slate-50/50 transition-colors">
                          <td className="py-3 px-3 text-xs text-slate-500 whitespace-nowrap">
                            {dateStr}
                          </td>
                          <td className="py-3 px-3 font-medium text-slate-900">
                            <div className="flex items-center gap-1.5">
                              {log.url ? (
                                <a
                                  href={log.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="hover:text-brand-600 hover:underline flex items-center gap-1"
                                >
                                  {log.job_title}
                                  <ExternalLink size={12} className="text-slate-400" />
                                </a>
                              ) : (
                                log.job_title
                              )}
                            </div>
                            <div className="text-xs text-slate-500">{log.company || "Unknown Company"}</div>
                          </td>
                          <td className="py-3 px-3 text-xs text-slate-600">
                            {log.location || "Not specified"}
                          </td>
                          <td className="py-3 px-3 whitespace-nowrap">
                            {log.action === "applied" && (
                              <span className="badge bg-emerald-100 text-emerald-800 flex items-center gap-1 w-fit">
                                <CheckCircle2 size={12} />
                                Applied (Direct)
                              </span>
                            )}
                            {log.action === "skipped_redirect" && (
                              <span className="badge bg-slate-100 text-slate-700 flex items-center gap-1 w-fit">
                                <ExternalLink size={12} />
                                Skipped (External Portal)
                              </span>
                            )}
                            {log.action === "skipped_questions" && (
                              <span className="badge bg-amber-100 text-amber-800 flex items-center gap-1 w-fit">
                                <AlertTriangle size={12} />
                                Skipped (Questions)
                              </span>
                            )}
                            {log.action === "already_applied" && (
                              <span className="badge bg-blue-100 text-blue-800 flex items-center gap-1 w-fit">
                                <Check size={12} />
                                Already Applied
                              </span>
                            )}
                            {log.action === "failed" && (
                              <span className="badge bg-rose-100 text-rose-800 flex items-center gap-1 w-fit">
                                <XCircle size={12} />
                                Failed
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-3 text-xs text-slate-500 max-w-xs truncate" title={log.notes || ""}>
                            {log.notes || "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
