import { useEffect, useMemo, useRef, useState } from "react";
import {
  QueryClient,
  QueryClientProvider,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Link, NavLink, Route, Routes } from "react-router-dom";
import {
  Bell,
  BellRing,
  Briefcase,
  ClipboardList,
  ExternalLink,
  FileText,
  History,
  IdCard,
  RefreshCw,
  Search,
  Sparkles,
} from "lucide-react";
import {
  api,
  type ApplicationReadinessStatus,
  type ApplicationWithJob,
  type Job,
  type JobIntelligenceSummaryItem,
} from "./api/client";
import ScanHistoryPage from "./pages/ScanHistoryPage";
import JobDetailPage from "./pages/JobDetailPage";
import {
  ErrorBanner,
  ErrorBoundary,
  RECOMMENDATION_RANK,
  RecommendationBadge,
  SkeletonJobCard,
  WorkflowBadge,
  computeWorkflowState,
  errorMessage as mutationErrorMessage,
  formatDate,
  formatRelativeTime,
  priorityBadgeTone,
  sourceLabel,
} from "./shared";
import { Badge } from "./design/Badge";
import { Pagination } from "./design/Pagination";
import { ScoreGauge } from "./design/ScoreGauge";
import { Surface, SectionLabel } from "./design/Surface";
import { buttonClasses } from "./design/tokens";
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

type JobSort = "recommendation" | "score_desc" | "score_asc" | "newest" | "oldest" | "employer";

const SORT_OPTIONS: { value: JobSort; label: string }[] = [
  { value: "recommendation", label: "Priority Queue (recommendation)" },
  { value: "score_desc", label: "Match score (high → low)" },
  { value: "score_asc", label: "Match score (low → high)" },
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "employer", label: "Employer (A → Z)" },
];

function sortJobs(
  jobs: Job[],
  sort: JobSort,
  intelligence: Record<string, JobIntelligenceSummaryItem>,
): Job[] {
  const copy = [...jobs];
  switch (sort) {
    case "recommendation":
      return copy.sort((a, b) => {
        const ia = intelligence[a.id];
        const ib = intelligence[b.id];
        const rankA = ia ? RECOMMENDATION_RANK[ia.recommendation] : RECOMMENDATION_RANK.low_priority;
        const rankB = ib ? RECOMMENDATION_RANK[ib.recommendation] : RECOMMENDATION_RANK.low_priority;
        if (rankA !== rankB) return rankA - rankB;
        return (ib?.score ?? -1) - (ia?.score ?? -1);
      });
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
    <Badge tone={online ? "success" : "danger"} dot pulse={online}>
      {online ? "Online" : "Offline"}
    </Badge>
  );
}

function NotificationHealthCard() {
  const { data: config, isLoading, isError } = useQuery({
    queryKey: ["notificationConfig"],
    queryFn: api.notificationConfig,
    staleTime: 60_000,
  });

  const configured = config?.telegram.configured ?? false;
  const tone = isLoading ? "neutral" : isError ? "danger" : configured ? "success" : "neutral";
  const label = isLoading ? "Checking…" : isError ? "Unavailable" : configured ? "Healthy" : "Not Configured";

  return (
    <Surface className="flex flex-col justify-center">
      <SectionLabel>Notifications</SectionLabel>
      <div className="mt-1.5">
        <Badge tone={tone} dot>
          {label}
        </Badge>
      </div>
    </Surface>
  );
}

const PIPELINE_ITEMS: { key: "saved" | "applied" | "interview" | "offer"; label: string; tone: "neutral" | "info" | "warning" | "success" }[] = [
  { key: "saved", label: "Saved", tone: "neutral" },
  { key: "applied", label: "Applied", tone: "info" },
  { key: "interview", label: "Interview", tone: "warning" },
  { key: "offer", label: "Offer", tone: "success" },
];

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
// "AI Copilot Feed" — the score/recommendation pairing is the card's visual
// anchor (what Kiwi thinks of this job); WorkflowBadge (where you are with
// it) moves down into the action row instead of competing at the header;
// source/provider demote to a muted metadata line instead of colored pills.

interface JobCardProps {
  job: Job;
  application?: ApplicationWithJob;
  readinessStatus?: ApplicationReadinessStatus;
  intelligence?: JobIntelligenceSummaryItem;
}

function JobCard({ job, application, readinessStatus, intelligence }: JobCardProps) {
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
  const priorityLabel = job.ai_priority && job.ai_priority !== "Reject" ? job.ai_priority : job.role_priority;
  const priorityTone = priorityBadgeTone(priorityLabel ?? null);

  return (
    <article className="group bg-gray-900 border border-gray-800 rounded-xl p-4 flex gap-4 transition-colors hover:border-gray-700 hover:bg-gray-900/80">
      <ScoreGauge score={score} size="sm" />

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
            <p className="text-[11px] text-gray-600 mt-1">
              {sourceLabel(job.source)}
              {job.ai_provider && job.ai_provider !== "manual" && (
                <>
                  <span className="mx-1">·</span>
                  <span className="capitalize">{job.ai_provider}</span>
                </>
              )}
            </p>
          </div>

          <div className="flex-none flex items-center flex-wrap justify-end gap-1.5 max-w-[50%]">
            {intelligence && <RecommendationBadge level={intelligence.recommendation} />}
            {priorityLabel && priorityTone && <Badge tone={priorityTone}>{priorityLabel}</Badge>}
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

        {/* Footer: status + actions + timestamps */}
        <div className="flex items-center justify-between gap-3 mt-3 flex-wrap">
          <div className="flex items-center flex-wrap gap-2">
            <WorkflowBadge state={workflowState} />

            <Link to={`/jobs/${job.id}?tab=apply`} className={buttonClasses("primary", "sm")}>
              {application ? "View Application" : "Start Application"}
            </Link>

            <button
              onClick={() => saveMutation.mutate()}
              disabled={isSaved || saveMutation.isPending}
              className={buttonClasses("secondary", "sm")}
            >
              {saveMutation.isPending ? "Saving…" : isSaved ? "Saved ✓" : "Save"}
            </button>

            <a
              href={job.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs px-1 py-1.5 text-gray-400 hover:text-gray-200 transition-colors"
            >
              View listing <ExternalLink className="w-3 h-3" />
            </a>

            {score === null && (
              <button
                onClick={() => analyseMutation.mutate()}
                disabled={analyseMutation.isPending}
                className="inline-flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300 disabled:opacity-40 transition-colors"
              >
                <Sparkles className="w-3 h-3" />
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

const NAV_ITEMS = [
  { to: "/", end: true, icon: Briefcase, label: "Jobs" },
  { to: "/applications", end: false, icon: ClipboardList, label: "Applications" },
  { to: "/resume", end: false, icon: FileText, label: "Resume" },
  { to: "/application-profile", end: false, icon: IdCard, label: "Application Profile" },
  { to: "/scan-history", end: false, icon: History, label: "Scan History" },
  { to: "/notifications", end: false, icon: Bell, label: "Notifications" },
] as const;

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
        {NAV_ITEMS.map(({ to, end, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => `${navLink} ${isActive ? activeClass : inactiveClass}`}
          >
            <Icon className="w-4 h-4 flex-none" strokeWidth={2} />
            {label}
          </NavLink>
        ))}
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
      <Search className="w-9 h-9 text-gray-700 mx-auto mb-3" strokeWidth={1.5} />
      <h3 className="text-white font-medium text-lg">No jobs yet</h3>
      <p className="text-gray-500 text-sm mt-2 max-w-sm mx-auto leading-relaxed">
        Run a scan to discover blue-collar roles across NZ job boards. The system also
        auto-scans every 6 hours.
      </p>
      <button onClick={onScan} disabled={scanning} className={`mt-6 ${buttonClasses("primary")}`}>
        {scanning ? "Scanning…" : "Trigger Scan"}
      </button>
    </div>
  );
}

type JobFilter = "all" | "ready" | "high_match" | "visa_compatible" | "applied";

const FILTER_OPTIONS: { value: JobFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "ready", label: "Ready" },
  { value: "high_match", label: "High Match" },
  { value: "visa_compatible", label: "Visa Compatible" },
  { value: "applied", label: "Applied" },
];

const HIGH_MATCH_RECOMMENDATIONS = new Set(["highly_recommended", "recommended"]);

const JOBS_PAGE_SIZE = 10;

function Dashboard() {
  const qc = useQueryClient();
  const { push } = useToast();
  const [sort, setSort] = useState<JobSort>("score_desc");
  const [filter, setFilter] = useState<JobFilter>("all");
  const [page, setPage] = useState(1);
  const jobsHeadingRef = useRef<HTMLHeadingElement>(null);

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

  const { data: intelligenceSummary = {} } = useQuery({
    queryKey: ["jobIntelligenceSummary"],
    queryFn: api.jobIntelligenceSummary,
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

  const visaCompatible = (job: Job) =>
    (job.visa_accredited_employer || job.visa_overseas_friendly || job.visa_sponsorship_potential) &&
    !job.visa_nz_rights_required;

  // A job whose listing was reported unavailable/expired is preserved in
  // history but must never keep surfacing as something still actionable.
  const isUnavailable = (job: Job) => appsByJobId.get(job.id)?.status === "unavailable";

  const filteredJobs = useMemo(() => {
    switch (filter) {
      case "ready":
        return jobs.filter((j) => readinessSummary[j.id] === "ready" && !isUnavailable(j));
      case "high_match":
        return jobs.filter((j) => {
          const rec = intelligenceSummary[j.id]?.recommendation;
          return rec ? HIGH_MATCH_RECOMMENDATIONS.has(rec) && !isUnavailable(j) : false;
        });
      case "visa_compatible":
        return jobs.filter(visaCompatible);
      case "applied":
        return jobs.filter((j) => {
          const app = appsByJobId.get(j.id);
          return !!app && app.status !== "saved" && app.status !== "unavailable";
        });
      default:
        return jobs;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs, filter, readinessSummary, intelligenceSummary, appsByJobId]);

  const sortedJobs = useMemo(
    () => sortJobs(filteredJobs, sort, intelligenceSummary),
    [filteredJobs, sort, intelligenceSummary],
  );

  const totalPages = Math.max(1, Math.ceil(sortedJobs.length / JOBS_PAGE_SIZE));

  // Changing filter/search criteria always starts back at page 1. Sorting
  // alone never changes how many results there are (only their order), so
  // it never resets the page here — the clamp effect below only steps in
  // if the current page genuinely stopped being valid (e.g. after a filter
  // change shrinks the result set).
  useEffect(() => {
    setPage(1);
  }, [filter]);

  useEffect(() => {
    setPage((p) => Math.min(p, totalPages));
  }, [totalPages]);

  const paginatedJobs = useMemo(
    () => sortedJobs.slice((page - 1) * JOBS_PAGE_SIZE, page * JOBS_PAGE_SIZE),
    [sortedJobs, page],
  );

  const goToPage = (nextPage: number) => {
    setPage(nextPage);
    // Scroll the Jobs list back into view, not the whole page.
    jobsHeadingRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

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

      {/* Stats — condensed into three differentiated cards (hero total, a
          pipeline legend, notification health) instead of six equally-
          weighted admin KPI tiles. */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
        {statsLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-4 h-[72px] animate-pulse" />
          ))
        ) : (
          <>
            <Surface tier="primary" className="md:col-span-1">
              <SectionLabel>Job Discovery</SectionLabel>
              <p className="text-3xl font-bold text-white mt-1 leading-none">{jobs.length}</p>
              <p className="text-xs text-gray-500 mt-1.5">{scoredJobs.length} scored</p>
            </Surface>

            <Surface className="md:col-span-1">
              <SectionLabel>Pipeline</SectionLabel>
              <div className="flex items-center gap-4 flex-wrap mt-2">
                {PIPELINE_ITEMS.map((item) => (
                  <div key={item.key} className="flex items-baseline gap-1.5">
                    <span className="text-lg font-semibold text-white leading-none">
                      {pipeline[item.key]}
                    </span>
                    <span className="text-xs text-gray-500">{item.label}</span>
                  </div>
                ))}
              </div>
            </Surface>

            <NotificationHealthCard />
          </>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={() => scanMutation.mutate()}
          disabled={scanMutation.isPending}
          className={buttonClasses("primary")}
        >
          <RefreshCw className={`w-4 h-4 ${scanMutation.isPending ? "animate-spin" : ""}`} />
          {scanMutation.isPending ? "Scanning…" : "Trigger Scan"}
        </button>
        <button
          onClick={() => analyseMutation.mutate()}
          disabled={analyseMutation.isPending}
          className={buttonClasses("secondary")}
        >
          <Sparkles className="w-4 h-4" />
          {analyseMutation.isPending ? "Scoring…" : "Score Unscored Jobs"}
        </button>
        <button
          onClick={() => testMutation.mutate()}
          disabled={testMutation.isPending}
          className={buttonClasses("subtle")}
        >
          <BellRing className="w-4 h-4" />
          {testMutation.isPending ? "Sending…" : "Test Notification"}
        </button>
      </div>

      {/* Jobs list */}
      <section className="mb-6">
        <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
          <h2 ref={jobsHeadingRef} className="text-base font-semibold text-white scroll-mt-6">
            Jobs
            {!jobsLoading && jobs.length > 0 && (
              <span className="text-gray-500 font-normal text-sm ml-2">({sortedJobs.length})</span>
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

        {!jobsLoading && jobs.length > 0 && (
          <div className="flex gap-1.5 flex-wrap mb-4">
            {FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setFilter(opt.value)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  filter === opt.value
                    ? "bg-blue-600 text-white"
                    : "bg-gray-900 text-gray-400 border border-gray-800 hover:text-gray-200 hover:border-gray-700"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}

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
        ) : sortedJobs.length === 0 ? (
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
            <p className="text-gray-500 text-sm">No jobs match this filter.</p>
          </div>
        ) : (
          <>
            <div className="flex flex-col gap-3">
              {paginatedJobs.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  application={appsByJobId.get(job.id)}
                  readinessStatus={readinessSummary[job.id]}
                  intelligence={intelligenceSummary[job.id]}
                />
              ))}
            </div>
            <Pagination
              page={page}
              pageSize={JOBS_PAGE_SIZE}
              totalItems={sortedJobs.length}
              onPageChange={goToPage}
              itemLabel="jobs"
            />
          </>
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
