import { useMemo, useState } from "react";
import {
  QueryClient,
  QueryClientProvider,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Link, NavLink, Route, Routes } from "react-router-dom";
import { api, type ApplicationReadinessStatus, type ApplicationWithJob, type Job } from "./api/client";
import ScanHistoryPage from "./pages/ScanHistoryPage";
import JobDetailPage from "./pages/JobDetailPage";
import {
  ErrorBanner,
  ErrorBoundary,
  SkeletonJobCard,
  SkeletonStatCard,
  WorkflowBadge,
  computeWorkflowState,
  errorMessage as mutationErrorMessage,
  formatDate,
  formatRelativeTime,
  priorityColor,
  scoreColor,
  sourceLabel,
} from "./shared";
import ApplicationsPage from "./pages/ApplicationsPage";
import ApplicationProfilePage from "./pages/ApplicationProfilePage";
import NotificationsPage from "./pages/NotificationsPage";
import ResumePage from "./pages/ResumePage";
import { ToastProvider, useToast } from "./hooks/useToast";

// A downed backend can surface two different ways depending on how the
// request reached it:
//  - fetch() throws a plain TypeError ("Failed to fetch") when nothing at
//    all is listening on the page's own origin (e.g. the Vite dev server
//    itself is mid-restart).
//  - When Vite's dev proxy IS up but the backend it forwards to isn't, the
//    browser gets a real HTTP response — a 502/500 from the proxy — which
//    our request() helper turns into a plain Error ending in "failed: 5xx".
// Both are transient (the server is starting up / restarting) and worth
// retrying harder than a real 4xx, which means the request itself was bad
// and hammering it won't help.
function isTransientError(error: unknown): boolean {
  if (error instanceof TypeError) return true;
  if (error instanceof Error) {
    const status = Number(error.message.match(/failed: (\d{3})$/)?.[1]);
    if (!Number.isNaN(status)) return status >= 500;
  }
  return false;
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => (isTransientError(error) ? failureCount < 5 : failureCount < 1),
      staleTime: 30_000,
    },
  },
});

type JobSort = "score_desc" | "score_asc" | "newest" | "oldest" | "employer";

const SORT_OPTIONS: { value: JobSort; label: string }[] = [
  { value: "score_desc", label: "Match score (high → low)" },
  { value: "score_asc", label: "Match score (low → high)" },
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "employer", label: "Employer (A → Z)" },
];

function sortJobs(jobs: Job[], sort: JobSort): Job[] {
  const copy = [...jobs];
  switch (sort) {
    case "score_desc":
      return copy.sort((a, b) => (b.ai_match_score ?? -1) - (a.ai_match_score ?? -1));
    case "score_asc":
      return copy.sort((a, b) => (a.ai_match_score ?? 999) - (b.ai_match_score ?? 999));
    case "newest":
      return copy.sort(
        (a, b) => new Date(b.first_seen_at).getTime() - new Date(a.first_seen_at).getTime(),
      );
    case "oldest":
      return copy.sort(
        (a, b) => new Date(a.first_seen_at).getTime() - new Date(b.first_seen_at).getTime(),
      );
    case "employer":
      return copy.sort((a, b) => a.employer.localeCompare(b.employer));
    default:
      return copy;
  }
}

// ── Atom components ───────────────────────────────────────────────────────────

function OnlineBadge({ online }: { online: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${
        online ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400"
      }`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${online ? "bg-green-400 animate-pulse" : "bg-red-400"}`}
      />
      {online ? "Online" : "Offline"}
    </span>
  );
}

function NotificationHealthCard() {
  const { data: config, isLoading, isError } = useQuery({
    queryKey: ["notificationConfig"],
    queryFn: api.notificationConfig,
    staleTime: 60_000,
  });

  const configured = config?.telegram.configured ?? false;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-gray-400 text-xs uppercase tracking-wide">Notifications</p>
      <div className="flex items-center gap-2 mt-1.5">
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            isLoading ? "bg-gray-600" : configured ? "bg-green-400" : "bg-gray-500"
          }`}
        />
        <p className="text-sm text-gray-300">
          {isLoading ? "Checking…" : isError ? "Unavailable" : "Telegram"}
          {!isLoading && !isError && (
            <span className={configured ? "text-green-400" : "text-gray-500"}>
              {" "}
              {configured ? "Healthy" : "Not Configured"}
            </span>
          )}
        </p>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
  loading,
}: {
  label: string;
  value: string | number;
  accent?: string;
  loading?: boolean;
}) {
  return (
    <div
      className={`bg-gray-900 border border-gray-800 rounded-xl p-4 transition-opacity ${loading ? "opacity-60" : ""}`}
    >
      <p className="text-gray-400 text-xs uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-semibold mt-1 ${accent ?? "text-white"}`}>{value}</p>
    </div>
  );
}

function VisaTags({ job }: { job: Job }) {
  const tags = [
    job.visa_accredited_employer && { label: "Accredited", cls: "bg-emerald-900/40 text-emerald-400" },
    job.visa_overseas_friendly && { label: "Overseas OK", cls: "bg-sky-900/40 text-sky-400" },
    job.visa_sponsorship_potential && { label: "Visa Support", cls: "bg-indigo-900/40 text-indigo-400" },
    job.visa_nz_rights_required && { label: "NZ Rights Required", cls: "bg-red-900/40 text-red-400" },
  ].filter(Boolean) as { label: string; cls: string }[];

  if (tags.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1 mt-2">
      {tags.map((t) => (
        <span key={t.label} className={`text-xs px-1.5 py-0.5 rounded ${t.cls}`}>
          {t.label}
        </span>
      ))}
    </div>
  );
}

function RelativeTime({
  iso,
  prefix,
  className = "text-xs text-gray-600",
}: {
  iso: string;
  prefix?: string;
  className?: string;
}) {
  return (
    <span className={className} title={formatDate(iso)}>
      {prefix}
      {formatRelativeTime(iso)}
    </span>
  );
}

// ── Job card ──────────────────────────────────────────────────────────────────

interface JobCardProps {
  job: Job;
  application?: ApplicationWithJob;
  readinessStatus?: ApplicationReadinessStatus;
}

function JobCard({ job, application, readinessStatus }: JobCardProps) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);

  const analyseMutation = useMutation({
    mutationFn: () => api.analyseJob(job.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });

  const saveMutation = useMutation({
    mutationFn: () => api.saveJob(job.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });

  const score = job.ai_match_score;
  const isSaved = !!application;
  const explanationLong = (job.ai_explanation?.length ?? 0) > 160;
  const workflowState = computeWorkflowState(
    application?.status,
    application?.active_session_status === "started",
    readinessStatus,
  );

  return (
    <article className="group bg-gray-900 border border-gray-800 rounded-xl p-4 flex gap-4 transition-colors hover:border-gray-700 hover:bg-gray-900/80">
      {/* Score badge */}
      <div
        className={`flex-none w-14 h-14 rounded-lg flex flex-col items-center justify-center text-center shrink-0 ${scoreColor(score)}`}
      >
        {score !== null ? (
          <>
            <span className="text-xl font-bold leading-none">{Math.round(score)}</span>
            <span className="text-[10px] opacity-70">/100</span>
          </>
        ) : (
          <span className="text-[10px] leading-tight text-center px-1">Unscored</span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Link
              to={`/jobs/${job.id}`}
              className="text-white font-medium leading-snug hover:text-blue-400 transition-colors"
            >
              <h3>{job.title}</h3>
            </Link>
            <p className="text-gray-400 text-sm mt-0.5">
              {job.employer}
              <span className="text-gray-600 mx-1">·</span>
              {job.location}
              {job.salary_text && (
                <>
                  <span className="text-gray-600 mx-1">·</span>
                  <span className="text-gray-500">{job.salary_text}</span>
                </>
              )}
            </p>
          </div>

          <div className="flex-none flex items-center flex-wrap justify-end gap-1.5 max-w-[45%]">
            <WorkflowBadge state={workflowState} />
            {job.ai_priority && job.ai_priority !== "Reject" && (
              <span
                className={`text-xs px-2 py-0.5 rounded font-medium ${priorityColor(job.ai_priority)}`}
              >
                {job.ai_priority}
              </span>
            )}
            {!job.ai_priority && job.role_priority && (
              <span
                className={`text-xs px-2 py-0.5 rounded font-medium ${priorityColor(job.role_priority)}`}
              >
                {job.role_priority}
              </span>
            )}
            <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-400">
              {sourceLabel(job.source)}
            </span>
            {job.ai_provider && job.ai_provider !== "manual" && (
              <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-500 capitalize">
                {job.ai_provider}
              </span>
            )}
          </div>
        </div>

        <VisaTags job={job} />

        {job.ai_explanation && (
          <div className="mt-2">
            <p
              className={`text-gray-400 text-xs leading-relaxed ${expanded ? "" : "line-clamp-2"}`}
            >
              {job.ai_explanation}
            </p>
            {explanationLong && (
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="text-xs text-gray-500 hover:text-gray-300 mt-1 transition-colors"
              >
                {expanded ? "Show less" : "Show more"}
              </button>
            )}
          </div>
        )}

        {/* Footer: actions + timestamps */}
        <div className="flex items-center justify-between gap-3 mt-3 flex-wrap">
          <div className="flex items-center flex-wrap gap-2">
            <Link
              to={`/jobs/${job.id}?tab=apply`}
              className="text-xs px-3 py-1.5 rounded-lg font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors"
            >
              {application ? "View Application" : "Start Application"}
            </Link>

            <button
              onClick={() => saveMutation.mutate()}
              disabled={isSaved || saveMutation.isPending}
              className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                isSaved
                  ? "border-gray-700 text-gray-600 cursor-not-allowed"
                  : "border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500 disabled:opacity-50"
              }`}
            >
              {saveMutation.isPending ? "Saving…" : isSaved ? "Saved ✓" : "Save"}
            </button>

            <a
              href={job.url}
              target="_blank"
              rel="noreferrer"
              className="text-xs px-3 py-1.5 text-gray-400 hover:text-gray-200 transition-colors"
            >
              View listing →
            </a>

            {score === null && (
              <button
                onClick={() => analyseMutation.mutate()}
                disabled={analyseMutation.isPending}
                className="text-xs text-violet-400 hover:text-violet-300 disabled:opacity-40 transition-colors"
              >
                {analyseMutation.isPending ? "Scoring…" : "Score now"}
              </button>
            )}
          </div>

          <div className="flex items-center gap-3 text-xs text-gray-600">
            <RelativeTime iso={job.first_seen_at} prefix="Found " />
            {job.ai_analysed_at && (
              <RelativeTime iso={job.ai_analysed_at} prefix="Scored " />
            )}
          </div>
        </div>

        {(saveMutation.isError || analyseMutation.isError) && (
          <p className="text-red-400 text-xs mt-2">
            {mutationErrorMessage(saveMutation.error ?? analyseMutation.error)}
          </p>
        )}
      </div>
    </article>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

function Sidebar() {
  const { data: health, isError: healthError } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
  });
  const isOnline = !healthError && health?.status === "ok";

  const navLink =
    "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors";
  const activeClass = "bg-gray-800 text-white font-medium";
  const inactiveClass = "text-gray-400 hover:text-gray-200 hover:bg-gray-800/50";

  return (
    <aside className="fixed left-0 top-0 h-full w-52 bg-gray-900 border-r border-gray-800 flex flex-col z-10">
      <div className="p-5 border-b border-gray-800">
        <h1 className="text-white font-bold text-base tracking-tight">Project Kiwi</h1>
        <p className="text-gray-500 text-xs mt-0.5">NZ Migration Copilot</p>
      </div>

      <nav className="flex-1 p-2 space-y-0.5 mt-1">
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `${navLink} ${isActive ? activeClass : inactiveClass}`
          }
        >
          <span>💼</span>
          Jobs
        </NavLink>
        <NavLink
          to="/applications"
          className={({ isActive }) =>
            `${navLink} ${isActive ? activeClass : inactiveClass}`
          }
        >
          <span>📋</span>
          Applications
        </NavLink>
        <NavLink
          to="/resume"
          className={({ isActive }) =>
            `${navLink} ${isActive ? activeClass : inactiveClass}`
          }
        >
          <span>📄</span>
          Resume
        </NavLink>
        <NavLink
          to="/application-profile"
          className={({ isActive }) =>
            `${navLink} ${isActive ? activeClass : inactiveClass}`
          }
        >
          <span>🧾</span>
          Application Profile
        </NavLink>
        <NavLink
          to="/scan-history"
          className={({ isActive }) =>
            `${navLink} ${isActive ? activeClass : inactiveClass}`
          }
        >
          <span>📜</span>
          Scan History
        </NavLink>
        <NavLink
          to="/notifications"
          className={({ isActive }) =>
            `${navLink} ${isActive ? activeClass : inactiveClass}`
          }
        >
          <span>🔔</span>
          Notifications
        </NavLink>
      </nav>

      <div className="p-4 border-t border-gray-800">
        <OnlineBadge online={isOnline} />
      </div>
    </aside>
  );
}

// ── Dashboard (Jobs page) ─────────────────────────────────────────────────────

function JobsEmptyState({ onScan, scanning }: { onScan: () => void; scanning: boolean }) {
  return (
    <div className="bg-gray-900 border border-gray-800 border-dashed rounded-xl p-10 text-center">
      <div className="text-4xl mb-3">🔍</div>
      <h3 className="text-white font-medium text-lg">No jobs yet</h3>
      <p className="text-gray-500 text-sm mt-2 max-w-sm mx-auto leading-relaxed">
        Run a scan to discover blue-collar roles across NZ job boards. The system also
        auto-scans every 6 hours.
      </p>
      <button
        onClick={onScan}
        disabled={scanning}
        className="mt-6 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 rounded-lg text-sm font-medium text-white transition-colors"
      >
        {scanning ? "Scanning…" : "Trigger Scan"}
      </button>
    </div>
  );
}

function Dashboard() {
  const qc = useQueryClient();
  const { push } = useToast();
  const [sort, setSort] = useState<JobSort>("score_desc");

  const {
    data: jobs = [],
    isLoading: jobsLoading,
    isFetching: jobsFetching,
    isError: jobsError,
    error: jobsErr,
    refetch: refetchJobs,
  } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.jobs(),
  });

  const { data: scans = [] } = useQuery({
    queryKey: ["scans"],
    queryFn: api.scans,
    staleTime: 60_000,
  });

  const { data: apps = [], isLoading: appsLoading } = useQuery({
    queryKey: ["applications"],
    queryFn: () => api.applications(),
  });

  const { data: readinessSummary = {} } = useQuery({
    queryKey: ["readinessSummary"],
    queryFn: api.readinessSummary,
  });

  const appsByJobId = useMemo(() => {
    const map = new Map<number, ApplicationWithJob>();
    for (const app of apps) map.set(app.job_id, app);
    return map;
  }, [apps]);

  const pipeline = useMemo(() => {
    const c = { saved: 0, applied: 0, interview: 0, offer: 0 };
    for (const app of apps) {
      if (app.status in c) c[app.status as keyof typeof c]++;
    }
    return c;
  }, [apps]);

  const sortedJobs = useMemo(() => sortJobs(jobs, sort), [jobs, sort]);

  const scanMutation = useMutation({
    mutationFn: api.triggerScan,
    onSuccess: (data) => {
      push(data.message, "success");
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["scans"] });
        qc.invalidateQueries({ queryKey: ["jobs"] });
      }, 1500);
    },
    onError: (error) => push(`Scan failed: ${mutationErrorMessage(error)}`, "error"),
  });

  const testMutation = useMutation({
    mutationFn: api.sendTestNotification,
    onSuccess: (data) => push(data.message, data.success ? "success" : "info"),
    onError: (error) => push(`Notification failed: ${mutationErrorMessage(error)}`, "error"),
  });

  const analyseMutation = useMutation({
    mutationFn: api.analysePending,
    onSuccess: (data) => {
      push(data.message, "success");
      setTimeout(() => qc.invalidateQueries({ queryKey: ["jobs"] }), 1500);
    },
    onError: (error) => push(`Scoring failed: ${mutationErrorMessage(error)}`, "error"),
  });

  const lastScan = scans[0] ?? null;
  const scoredJobs = jobs.filter((j) => j.ai_match_score !== null);
  const statsLoading = jobsLoading || appsLoading;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Page header */}
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-white">Job Discovery</h1>
        <p className="text-gray-500 text-sm mt-1">
          {lastScan ? (
            <>
              Last scan{" "}
              <span title={formatDate(lastScan.started_at)}>
                {formatRelativeTime(lastScan.started_at)}
              </span>
              {lastScan.new_jobs > 0 && (
                <span className="text-gray-600">
                  {" "}
                  · {lastScan.new_jobs} new job{lastScan.new_jobs !== 1 ? "s" : ""}
                </span>
              )}
            </>
          ) : (
            "No scans yet — trigger one to get started"
          )}
        </p>
      </header>

      {/* Background refresh indicator */}
      {jobsFetching && !jobsLoading && (
        <div className="h-0.5 bg-blue-600/80 rounded-full mb-4 animate-pulse" />
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        {statsLoading ? (
          Array.from({ length: 6 }).map((_, i) => <SkeletonStatCard key={i} />)
        ) : (
          <>
            <StatCard label="Total Jobs" value={jobs.length} loading={jobsFetching} />
            <StatCard label="Scored" value={scoredJobs.length} loading={jobsFetching} />
            <StatCard
              label="Saved"
              value={pipeline.saved}
              accent="text-gray-300"
              loading={jobsFetching}
            />
            <StatCard
              label="Applied"
              value={pipeline.applied}
              accent="text-blue-400"
              loading={jobsFetching}
            />
            <StatCard
              label="Interview"
              value={pipeline.interview}
              accent="text-yellow-400"
              loading={jobsFetching}
            />
            <StatCard
              label="Offer"
              value={pipeline.offer}
              accent="text-green-400"
              loading={jobsFetching}
            />
            <NotificationHealthCard />
          </>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={() => scanMutation.mutate()}
          disabled={scanMutation.isPending}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 rounded-lg text-sm font-medium transition-colors"
        >
          {scanMutation.isPending ? "Scanning…" : "Trigger Scan"}
        </button>
        <button
          onClick={() => analyseMutation.mutate()}
          disabled={analyseMutation.isPending}
          className="px-4 py-2 bg-violet-700 hover:bg-violet-600 disabled:opacity-40 rounded-lg text-sm font-medium transition-colors"
        >
          {analyseMutation.isPending ? "Scoring…" : "Score Unscored Jobs"}
        </button>
        <button
          onClick={() => testMutation.mutate()}
          disabled={testMutation.isPending}
          className="px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 rounded-lg text-sm font-medium transition-colors"
        >
          {testMutation.isPending ? "Sending…" : "Test Notification"}
        </button>
      </div>

      {/* Jobs list */}
      <section className="mb-6">
        <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
          <h2 className="text-base font-semibold text-white">
            Jobs
            {!jobsLoading && jobs.length > 0 && (
              <span className="text-gray-500 font-normal text-sm ml-2">({jobs.length})</span>
            )}
          </h2>
          {!jobsLoading && jobs.length > 0 && (
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as JobSort)}
              className="text-xs bg-gray-900 border border-gray-700 text-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:border-gray-500 cursor-pointer"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}
        </div>

        {jobsLoading ? (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <SkeletonJobCard key={i} />
            ))}
          </div>
        ) : jobsError ? (
          <ErrorBanner
            title="Couldn't load jobs"
            message={mutationErrorMessage(jobsErr)}
            onRetry={() => refetchJobs()}
          />
        ) : jobs.length === 0 ? (
          <JobsEmptyState
            onScan={() => scanMutation.mutate()}
            scanning={scanMutation.isPending}
          />
        ) : (
          <div className="flex flex-col gap-3">
            {sortedJobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                application={appsByJobId.get(job.id)}
                readinessStatus={readinessSummary[job.id]}
              />
            ))}
          </div>
        )}
      </section>

    </div>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────

function AppShell() {
  return (
    <div className="flex min-h-screen bg-gray-950 text-gray-100">
      <Sidebar />
      <main className="flex-1 ml-52 min-h-screen overflow-y-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/jobs/:id" element={<JobDetailPage />} />
          <Route path="/applications" element={<ApplicationsPage />} />
          <Route path="/resume" element={<ResumePage />} />
          <Route path="/application-profile" element={<ApplicationProfilePage />} />
          <Route path="/scan-history" element={<ScanHistoryPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <AppShell />
        </ToastProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
