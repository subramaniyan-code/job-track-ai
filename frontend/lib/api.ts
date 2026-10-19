export function getApiBase(): string {
  if (typeof window !== "undefined") {
    const envUrl = process.env.NEXT_PUBLIC_API_URL;
    if (envUrl && !envUrl.includes("localhost") && !envUrl.includes("127.0.0.1")) {
      return envUrl;
    }
    const host = window.location.hostname;
    const protocol = window.location.protocol;
    return `${protocol}//${host}:8000`;
  }
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("jobtrack_token");
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem("jobtrack_token", token);
  else localStorage.removeItem("jobtrack_token");
}

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const isUrlEncoded = typeof URLSearchParams !== "undefined" && options.body instanceof URLSearchParams;
  const headers: Record<string, string> = {
    ...(options.body && !isUrlEncoded && !isFormData ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string> | undefined),
  };

  const apiBase = getApiBase();
  const res = await fetch(`${apiBase}${path}`, { ...options, headers });

  if (res.status === 204) return undefined as T;

  let data: any = null;
  try {
    data = await res.json();
  } catch {
    // no body
  }

  if (!res.ok) {
    const message = data?.detail || res.statusText || "Request failed";
    throw new ApiError(typeof message === "string" ? message : JSON.stringify(message), res.status);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body:
        typeof FormData !== "undefined" && body instanceof FormData
          ? body
          : typeof URLSearchParams !== "undefined" && body instanceof URLSearchParams
          ? body
          : body !== undefined
          ? JSON.stringify(body)
          : undefined,
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PATCH",
      body:
        typeof FormData !== "undefined" && body instanceof FormData
          ? body
          : typeof URLSearchParams !== "undefined" && body instanceof URLSearchParams
          ? body
          : body !== undefined
          ? JSON.stringify(body)
          : undefined,
    }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PUT",
      body:
        typeof FormData !== "undefined" && body instanceof FormData
          ? body
          : typeof URLSearchParams !== "undefined" && body instanceof URLSearchParams
          ? body
          : body !== undefined
          ? JSON.stringify(body)
          : undefined,
    }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, formData: FormData) => request<T>(path, { method: "POST", body: formData }),
};

export async function login(email: string, password: string) {
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);
  return request<{ access_token: string; user: User }>("/auth/login", { method: "POST", body: form });
}

export async function register(email: string, full_name: string, password: string) {
  return request<{ access_token: string; user: User }>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, full_name, password }),
  });
}

// ---------- Types (mirroring backend schemas.py) ----------
export type Role = "super_admin" | "user";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  timezone: string;
  created_at: string;
}

export type ConnectorProvider = "adzuna" | "greenhouse" | "lever" | "jsearch";

export interface ApiConnection {
  id: string;
  provider: ConnectorProvider;
  label: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Job {
  id: string;
  source: string;
  title: string;
  company: string | null;
  location: string | null;
  remote: boolean;
  url: string;
  platform: string | null;
  description: string | null;
  posted_at: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
}

export type ApplicationStatus = "saved" | "applied" | "interviewing" | "offer" | "rejected" | "ghosted";

export interface Application {
  id: string;
  job: Job;
  status: ApplicationStatus;
  fit_score: number | null;
  recruiter_email: string | null;
  recruiter_phone: string | null;
  resume_version: string | null;
  salary_expectation: string | null;
  notes: string | null;
  applied_at: string | null;
  last_activity_at: string;
  created_at: string;
}

export interface ApplicationEvent {
  id: string;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  note: string | null;
  created_at: string;
}

export type FollowUpStatus = "draft" | "approved" | "sent" | "skipped";

export interface FollowUp {
  id: string;
  application_id: string;
  subject: string;
  body: string;
  template_used: string | null;
  status: FollowUpStatus;
  suggested_send_at: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface DashboardStats {
  total_applications: number;
  applied: number;
  interviewing: number;
  offers: number;
  rejected: number;
  ghosted: number;
  response_rate: number;
  pending_followups: number;
  applications_last_7_days: number;
  applications_last_30_days: number;
  unread_inbox_insights: number;
  stale_applications: number;
}

export interface EmailAccount {
  id: string;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  from_name: string | null;
  imap_host: string | null;
  imap_port: number;
  imap_enabled: boolean;
  is_active: boolean;
}

export type EmailInsightType =
  | "application_confirmation"
  | "interview_invite"
  | "rejection"
  | "offer"
  | "job_alert"
  | "other";

export interface ExtractedJob {
  title: string;
  company?: string;
  url?: string;
}

export interface EmailInsight {
  id: string;
  from_address: string | null;
  subject: string | null;
  received_at: string | null;
  insight_type: EmailInsightType;
  company: string | null;
  job_title: string | null;
  summary: string | null;
  matched_application_id: string | null;
  extracted_jobs: ExtractedJob[] | null;
  platform: string | null;
  is_read: boolean;
  created_at: string;
}

export interface PlatformTrend {
  platform: string;
  applied: number;
  replies: number;
  reply_rate: number;
}

export interface PlatformTrendsOut {
  platforms: PlatformTrend[];
  summary: string;
}

export interface CandidateProfile {
  id: string;
  full_name: string | null;
  email: string | null;
  phone: string | null;
  primary_roles: string[] | null;
  skills: string[] | null;
  experience_years: number;
  preferred_locations: string[] | null;
  naukri_search_queries: string[] | null;
  summary: string | null;
  resume_filename: string | null;
  updated_at: string;
}

export interface NaukriBotConfig {
  id: string;
  enabled: boolean;
  has_session: boolean;
  daily_max_applications: number;
  runs_per_day: number;
  target_keywords: string | null;
  target_locations: string | null;
  experience_years: number;
  applications_today: number;
  last_run_at: string | null;
  next_run_at: string | null;
  status: string;
  status_message: string | null;
  updated_at: string;
}

export interface NaukriBotLog {
  id: string;
  job_title: string;
  company: string | null;
  location: string | null;
  url: string | null;
  action: string;
  notes: string | null;
  created_at: string;
}

