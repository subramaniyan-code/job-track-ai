const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  const headers: Record<string, string> = {
    ...(options.body && !(options.body instanceof URLSearchParams) ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string> | undefined),
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

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
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
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
