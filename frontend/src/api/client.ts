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
  last_seen_at: string;
  salary_text: string | null;
  // Application Copilot (Phase 8) — stamped when the Cover Letter prompt is
  // generated for this job; the only signal Kiwi has for "prepared."
  cover_letter_generated_at: string | null;
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

export type ApplicationEventType =
  | "created" | "status_change" | "note_updated"
  | "session_started" | "session_resumed" | "session_completed" | "session_cancelled";

export interface ApplicationEvent {
  id: number;
  application_id: number;
  event_type: ApplicationEventType;
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
  // Phase 8 — set when a not-yet-terminal ApplicationSession exists.
  active_session_status: "started" | null;
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

// ── Kiwi Job Summary (Phase 7.6) ─────────────────────────────────────────────
// Deterministic, regex/heuristic extraction — no LLM. Missing values stay
// empty rather than being guessed.

export interface JobSummary {
  overview: string;
  responsibilities: string[];
  requirements_required: string[];
  requirements_preferred: string[];
  benefits: string[];
  work_environment: string[];
  salary: string;
  visa_notes: string;
  warnings: string[];
}

// ── Application Profile (Phase 8.0) ─────────────────────────────────────────
// Single source of truth for reusable applicant information — the
// foundation future ATS autofill will read from. Exactly one profile ever
// exists on the backend; GET/PUT upsert it. Resume data is never duplicated
// here — it always comes from the Resume Vault.

export interface ApplicationReference {
  id: number;
  name: string;
  company: string | null;
  relationship: string | null;
  email: string | null;
  phone: string | null;
}

export type ApplicationReferenceInput = Omit<ApplicationReference, "id">;

export interface ApplicationProfile {
  id: number;
  full_name: string | null;
  preferred_name: string | null;
  email: string | null;
  phone: string | null;
  current_address: string | null;
  city: string | null;
  country: string | null;
  nationality: string | null;
  work_rights_current_country: string | null;
  visa_status: string | null;
  eligible_to_work_nz: boolean;
  need_sponsorship: boolean;
  driver_license: boolean;
  own_vehicle: boolean;
  linkedin_url: string | null;
  portfolio_url: string | null;
  github_url: string | null;
  website_url: string | null;
  emergency_contact_name: string | null;
  emergency_contact_relationship: string | null;
  emergency_contact_phone: string | null;
  notes: string | null;
  references: ApplicationReference[];
  created_at: string;
  updated_at: string;
}

export type ApplicationProfileUpdate = Omit<ApplicationProfile, "id" | "created_at" | "updated_at" | "references"> & {
  references: ApplicationReferenceInput[];
};

// ── Application Copilot (Phase 8) ────────────────────────────────────────────
// Kiwi assists, the user submits: Launch only ever opens the original job
// URL in a new tab — it never fills in or submits the employer's form.
// Application Readiness is the single evaluator (backend/core/
// application_readiness.py) used everywhere below; never re-derived here.

export type ApplicationReadinessStatus = "ready" | "partial" | "not_ready";

export interface SectionReadiness {
  resume: boolean;
  application_profile: boolean;
  cover_letter: boolean;
  references: boolean;
  work_rights: boolean;
}

export interface ApplicationReadiness {
  status: ApplicationReadinessStatus;
  sections: SectionReadiness;
  missing: string[];
  score: number;
  estimated_minutes: number;
}

export type ApplicationSessionStatus = "started" | "completed" | "cancelled";

export interface ApplicationSession {
  id: number;
  application_id: number;
  status: ApplicationSessionStatus;
  started_at: string;
  last_opened_at: string;
  completed_at: string | null;
  duration_seconds: number;
  resume_version: string | null;
  cover_letter_version: string | null;
  profile_version: string | null;
}

export interface ApplicationKit {
  readiness: ApplicationReadiness;
  application: Application | null;
  active_session: ApplicationSession | null;
}

export interface LaunchApplicationResponse {
  url: string;
  application: Application;
  session: ApplicationSession;
}

export type ApplicationSessionOutcome = "applied" | "not_yet" | "cancelled";

export interface CompleteSessionResponse {
  application: Application;
  session: ApplicationSession;
}

// ── Job Intelligence (Phase 9) ───────────────────────────────────────────────
// Deterministic scoring, recommendation, and gap-analysis — backend/core/
// job_intelligence.py is the single evaluator. It never calls an AI
// provider; Job.ai_match_score/ai_reasons already come from ManualProvider's
// own deterministic keyword analysis, and this just interprets them.

export type RecommendationLevel = "highly_recommended" | "recommended" | "consider" | "low_priority";

export interface JobIntelligence {
  score: number;
  confidence: number;
  recommendation: RecommendationLevel;
  reasons: string[];
  missing_requirements: string[];
}

export interface JobIntelligenceSummaryItem {
  score: number;
  recommendation: RecommendationLevel;
}

export interface SimilarJob {
  id: number;
  title: string;
  employer: string;
  location: string;
  source: string;
  ai_match_score: number | null;
  similarity_score: number;
}

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
  jobSummary: (jobId: number) => request<JobSummary>(`/jobs/${jobId}/summary`),
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

  // Application Profile
  applicationProfile: () => request<ApplicationProfile>("/application-profile/"),
  updateApplicationProfile: (body: ApplicationProfileUpdate) =>
    request<ApplicationProfile>("/application-profile/", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  // Application Copilot (Phase 8)
  applicationReadiness: (jobId: number) =>
    request<ApplicationReadiness>(`/jobs/${jobId}/application-readiness`),
  readinessSummary: () => request<Record<string, ApplicationReadinessStatus>>("/jobs/readiness-summary"),
  applicationKit: (jobId: number) => request<ApplicationKit>(`/jobs/${jobId}/application-kit`),
  launchApplication: (jobId: number) =>
    request<LaunchApplicationResponse>(`/jobs/${jobId}/launch-application`, { method: "POST" }),
  completeApplicationSession: (jobId: number, outcome: ApplicationSessionOutcome) =>
    request<CompleteSessionResponse>(`/jobs/${jobId}/application-session/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ outcome }),
    }),

  // Job Intelligence (Phase 9)
  jobIntelligence: (jobId: number) => request<JobIntelligence>(`/jobs/${jobId}/job-intelligence`),
  jobIntelligenceSummary: () =>
    request<Record<string, JobIntelligenceSummaryItem>>("/jobs/job-intelligence-summary"),
  similarJobs: (jobId: number) => request<SimilarJob[]>(`/jobs/${jobId}/similar`),
};
