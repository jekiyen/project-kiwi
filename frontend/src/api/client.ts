const BASE = "/api/v1";

async function extractErrorMessage(res: Response, path: string, method: string): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.message === "string") return body.message;
  } catch {
    // Response wasn't JSON (e.g. network layer / proxy error) — fall through.
  }
  return `${method} ${path} failed: ${res.status}`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    throw new Error(await extractErrorMessage(res, path, options?.method ?? "GET"));
  }
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
  description: string | null;
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

// ── Notifications (Phase 6.2A/B) ────────────────────────────────────────────────

export interface ProviderStatus {
  enabled: boolean;
  bot_token_present: boolean;
  bot_connected: boolean;
  chat_id_present: boolean;
  configured: boolean;
}

export interface NotificationConfig {
  telegram: ProviderStatus;
}

export interface TestNotificationResponse {
  success: boolean;
  configured: boolean;
  missing: string[];
  message: string;
}

export interface DetectedChat {
  chat_id: number;
  type: string;
  username: string | null;
  title: string | null;
  display_name: string;
}

export interface ChatIdDetectionResponse {
  success: boolean;
  bot_token_present: boolean;
  detected: DetectedChat[];
  message: string;
}

// ── Resume Vault (Phase 7.3) ─────────────────────────────────────────────────
// Kiwi stores resume documents as source-of-truth files — no parsing, no AI.

export interface Resume {
  id: number;
  original_filename: string;
  filename: string;
  file_type: "pdf" | "docx";
  file_size: number;
  is_active: boolean;
  uploaded_at: string;
  updated_at: string;
}

export type PatchResumeBody = {
  filename?: string;
};

// ── AI Workspace / Prompt Engine (Phase 7.4) ────────────────────────────────
// Kiwi never calls an AI provider directly — the Prompt Engine renders plain
// text for the user to copy and paste into Claude by hand.

export interface PromptAction {
  id: string;
  label: string;
  description: string;
  icon: string;
}

export type AIReadinessStatus = "ready" | "partial" | "not_ready";

export interface GeneratedPrompt {
  title: string;
  content: string;
  readiness_status: AIReadinessStatus;
  disclaimer: string | null;
}

export interface JobChange {
  id: number;
  job_id: number;
  field_changed: string;
  old_value: string | null;
  new_value: string | null;
  detected_at: string;
}

// ── AI Readiness & Job Quality (Phase 7.5) ──────────────────────────────────
// Prevents generating a low-quality prompt from incomplete job data — see
// backend/core/ai_readiness.py for the single evaluator both the readiness
// card and the Prompt Guard rely on.

export interface AIReadiness {
  status: AIReadinessStatus;
  missing: string[];
  impact: string;
}

export type PatchJobBody = {
  title?: string;
  employer?: string;
  location?: string;
  description?: string;
};

// ── API object ────────────────────────────────────────────────────────────────

export const api = {
  // Health + infrastructure
  health: () => request<HealthResponse>("/health"),
  scans: () => request<Scan[]>("/scans"),
  triggerScan: () => request<{ message: string }>("/scans/trigger", { method: "POST" }),
  sendTestNotification: () =>
    request<TestNotificationResponse>("/notifications/test", { method: "POST" }),
  notificationConfig: () => request<NotificationConfig>("/notifications/config"),
  detectChatId: () => request<ChatIdDetectionResponse>("/notifications/chat-id"),

  // Jobs
  jobs: (limit = 100) => request<Job[]>(`/jobs?limit=${limit}`),
  job: (id: number) => request<Job>(`/jobs/${id}`),
  patchJob: (id: number, body: PatchJobBody) =>
    request<Job>(`/jobs/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  analyseJob: (jobId: number) =>
    request<Job>(`/jobs/${jobId}/analyse`, { method: "POST" }),
  analysePending: () =>
    request<{ message: string }>("/jobs/analyse-pending", { method: "POST" }),

  // AI Workspace / Prompt Engine
  promptActions: () => request<PromptAction[]>("/prompts/actions"),
  generateJobPrompt: (jobId: number, actionId: string) =>
    request<GeneratedPrompt>(`/jobs/${jobId}/prompts/${actionId}`),
  jobChanges: (jobId: number) => request<JobChange[]>(`/jobs/${jobId}/changes`),
  aiReadiness: (jobId: number) => request<AIReadiness>(`/jobs/${jobId}/ai-readiness`),

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
    if (!res.ok) {
      throw new Error(await extractErrorMessage(res, `/applications/${id}`, "DELETE"));
    }
  },

  // Resume Vault
  resumes: () => request<Resume[]>("/resumes/"),
  resume: (id: number) => request<Resume>(`/resumes/${id}`),
  uploadResume: async (file: File, filename?: string): Promise<Resume> => {
    const form = new FormData();
    form.append("file", file);
    if (filename) form.append("filename", filename);
    const res = await fetch(`${BASE}/resumes/upload`, { method: "POST", body: form });
    if (!res.ok) {
      throw new Error(await extractErrorMessage(res, "/resumes/upload", "POST"));
    }
    return res.json() as Promise<Resume>;
  },
  replaceResume: async (id: number, file: File): Promise<Resume> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/resumes/${id}/replace`, { method: "POST", body: form });
    if (!res.ok) {
      throw new Error(await extractErrorMessage(res, `/resumes/${id}/replace`, "POST"));
    }
    return res.json() as Promise<Resume>;
  },
  activateResume: (id: number) =>
    request<Resume>(`/resumes/${id}/activate`, { method: "POST" }),
  patchResume: (id: number, body: PatchResumeBody) =>
    request<Resume>(`/resumes/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteResume: async (id: number): Promise<void> => {
    const res = await fetch(`${BASE}/resumes/${id}`, { method: "DELETE" });
    if (!res.ok) {
      throw new Error(await extractErrorMessage(res, `/resumes/${id}`, "DELETE"));
    }
  },
  resumePreviewUrl: (id: number) => `${BASE}/resumes/${id}/preview`,
  resumeDownloadUrl: (id: number) => `${BASE}/resumes/${id}/download`,
};
