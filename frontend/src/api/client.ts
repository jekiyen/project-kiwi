const BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) throw new Error(`${options?.method ?? "GET"} ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp: string;
}

export interface ScraperRun {
  id: number;
  scan_id: number;
  source: string;
  status: "success" | "partial" | "failed";
  jobs_found: number;
  jobs_inserted: number;
  duplicates_skipped: number;
  errors: string | null;
  duration_ms: number;
  started_at: string;
  finished_at: string | null;
}

export interface Scan {
  id: number;
  started_at: string;
  completed_at: string | null;
  source: string;
  jobs_found: number;
  new_jobs: number;
  changed_jobs: number;
  status: "running" | "completed" | "failed";
  total_duplicates: number;
  total_errors: number;
  duration_ms: number | null;
  scraper_runs: ScraperRun[];
}

export interface Job {
  id: number;
  title: string;
  employer: string;
  location: string;
  source: string;
  url: string;
  role_priority: "P1" | "P2" | "P3" | null;
  // AI analysis — core
  ai_match_score: number | null;
  ai_explanation: string | null;
  ai_analysed_at: string | null;
  // AI analysis — extended (Phase 3)
  ai_priority: string | null;
  ai_reasons: string | null;      // JSON-encoded string[]
  ai_pros: string | null;         // JSON-encoded string[]
  ai_cons: string | null;         // JSON-encoded string[]
  ai_visa_probability: number | null;
  ai_confidence: number | null;
  ai_provider: string | null;
  ai_model: string | null;
  // Visa signals
  visa_accredited_employer: boolean;
  visa_overseas_friendly: boolean;
  visa_sponsorship_potential: boolean;
  visa_nz_rights_required: boolean;
  first_seen_at: string;
  salary_text: string | null;
}

// ── Application tracker types (Phase 4) ───────────────────────────────────────

export type ApplicationStatus =
  | "saved" | "applied" | "interview" | "offer"
  | "rejected" | "visa" | "archived";

export interface Application {
  id: number;
  job_id: number;
  status: ApplicationStatus;
  notes: string | null;
  applied_at: string | null;
  interview_date: string | null;
  follow_up_date: string | null;
  resume_version: string | null;
  cover_letter_version: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationEvent {
  id: number;
  application_id: number;
  event_type: "created" | "status_change" | "note_updated";
  from_status: ApplicationStatus | null;
  to_status: ApplicationStatus | null;
  detail: string | null;
  created_at: string;
}

export interface ApplicationWithJob extends Application {
  job_title: string;
  job_employer: string;
  job_location: string;
  job_url: string;
  job_source: string;
  job_ai_match_score: number | null;
  job_role_priority: string | null;
  job_ai_priority: string | null;
  job_salary_text: string | null;
}

export interface PipelineCounts {
  saved: number;
  applied: number;
  interview: number;
  offer: number;
  rejected: number;
  visa: number;
  archived: number;
  total: number;
}

export type PatchApplicationBody = {
  status?: string;
  notes?: string;
  applied_at?: string;
  interview_date?: string;
  follow_up_date?: string;
  resume_version?: string;
  cover_letter_version?: string;
};

// ── API object ────────────────────────────────────────────────────────────────

export const api = {
  // Health + infrastructure
  health: () => request<HealthResponse>("/health"),
  scans: () => request<Scan[]>("/scans"),
  triggerScan: () => request<{ message: string }>("/scans/trigger", { method: "POST" }),
  sendTestNotification: () =>
    request<{ message: string }>("/notifications/test", { method: "POST" }),

  // Jobs
  jobs: (limit = 100) => request<Job[]>(`/jobs?limit=${limit}`),
  analyseJob: (jobId: number) =>
    request<Job>(`/jobs/${jobId}/analyse`, { method: "POST" }),
  analysePending: () =>
    request<{ message: string }>("/jobs/analyse-pending", { method: "POST" }),

  // Application tracker
  saveJob: (jobId: number) =>
    request<Application>(`/jobs/${jobId}/save`, { method: "POST" }),
  applyJob: (jobId: number) =>
    request<Application>(`/jobs/${jobId}/apply`, { method: "POST" }),
  applications: (params?: { status?: string; search?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.search) q.set("search", params.search);
    const qs = q.toString();
    return request<ApplicationWithJob[]>(`/applications/${qs ? `?${qs}` : ""}`);
  },
  pipeline: () => request<PipelineCounts>("/applications/pipeline"),
  applicationTimeline: (id: number) =>
    request<ApplicationEvent[]>(`/applications/${id}/timeline`),
  patchApplication: (id: number, body: PatchApplicationBody) =>
    request<Application>(`/applications/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteApplication: async (id: number): Promise<void> => {
    const res = await fetch(`${BASE}/applications/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`DELETE /applications/${id} failed: ${res.status}`);
  },
};
