import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type ApplicationEvent, type Job, type JobChange, type JobSummary } from "../api/client";
import AIWorkspace from "../components/AIWorkspace";
import ApplicationKit from "../components/ApplicationKit";
import JobIntelligenceCard from "../components/JobIntelligenceCard";
import { useToast } from "../hooks/useToast";
import { ErrorBanner, errorMessage, formatDate, formatRelativeTime, scoreColor, sourceLabel } from "../shared";

type Tab = "overview" | "ai_summary" | "original" | "workspace" | "apply" | "activity";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "ai_summary", label: "AI Summary" },
  { id: "original", label: "Original Description" },
  { id: "workspace", label: "AI Workspace" },
  { id: "apply", label: "Apply" },
  { id: "activity", label: "Activity" },
];

const VALID_TABS = new Set<Tab>(TABS.map((t) => t.id));

const ORIGINAL_DESCRIPTION_COLLAPSE_THRESHOLD = 600;

function isSummaryEmpty(summary: JobSummary): boolean {
  return !(
    summary.overview ||
    summary.responsibilities.length ||
    summary.requirements_required.length ||
    summary.requirements_preferred.length ||
    summary.benefits.length ||
    summary.work_environment.length ||
    summary.salary ||
    summary.visa_notes
  );
}

// ── Shared bits ───────────────────────────────────────────────────────────────

function ViewListingLink({ job }: { job: Job }) {
  return (
    <a
      href={job.url}
      target="_blank"
      rel="noreferrer"
      className="inline-block text-sm text-blue-400 hover:text-blue-300 transition-colors"
    >
      View original listing →
    </a>
  );
}

function SummaryFallbackNotice() {
  return (
    <div className="flex items-start gap-2 bg-gray-800/60 border border-gray-700 rounded-lg px-3 py-2 mb-4">
      <span className="text-gray-500 text-sm leading-none mt-0.5">ⓘ</span>
      <p className="text-gray-400 text-xs leading-relaxed">
        No structured summary available — showing the original description instead.
      </p>
    </div>
  );
}

function BulletCard({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">{label}</p>
      <ul className="text-sm text-gray-300 space-y-1.5 leading-relaxed">
        {items.map((item, i) => (
          <li key={i}>• {item}</li>
        ))}
      </ul>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-sm text-gray-200 mt-0.5">{value}</p>
    </div>
  );
}

// The raw scraped description — used both by the Original Description tab
// and as the auto-fallback inside Overview/AI Summary when there's nothing
// structured to show. Copy button + expand/collapse for long text, and
// preserves the original line breaks/whitespace exactly as scraped.
function OriginalDescriptionCard({ job }: { job: Job }) {
  const { push } = useToast();
  const [expanded, setExpanded] = useState(false);
  const hasDescription = !!job.description;
  const isLong = (job.description?.length ?? 0) > ORIGINAL_DESCRIPTION_COLLAPSE_THRESHOLD;
  const collapsed = isLong && !expanded;

  const handleCopy = async () => {
    if (!job.description) return;
    try {
      await navigator.clipboard.writeText(job.description);
      push("Description copied to clipboard", "success");
    } catch {
      push("Couldn't copy — select and copy the text manually", "error");
    }
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-400">
          <span>{sourceLabel(job.source)}</span>
          {job.salary_text && (
            <>
              <span className="text-gray-700">·</span>
              <span>{job.salary_text}</span>
            </>
          )}
          <span className="text-gray-700">·</span>
          <span>Found {formatRelativeTime(job.first_seen_at)}</span>
        </div>
        {hasDescription && (
          <button
            onClick={handleCopy}
            className="flex-none text-xs px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 transition-colors"
          >
            Copy
          </button>
        )}
      </div>

      {hasDescription ? (
        <>
          <div className={`relative ${collapsed ? "max-h-64 overflow-hidden" : ""}`}>
            <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap font-sans">
              {job.description}
            </p>
            {collapsed && (
              <div className="absolute bottom-0 inset-x-0 h-16 bg-gradient-to-t from-gray-900 to-transparent" />
            )}
          </div>
          {isLong && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-xs text-gray-500 hover:text-gray-300 mt-2 transition-colors"
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          )}
        </>
      ) : (
        <p className="text-gray-500 text-sm italic">No description available for this job.</p>
      )}
    </div>
  );
}

// ── Overview tab ──────────────────────────────────────────────────────────────

function OverviewTab({
  job,
  summary,
  isLoading,
  isError,
}: {
  job: Job;
  summary: JobSummary | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading) {
    return <div className="h-56 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />;
  }

  const salary = summary?.salary || job.salary_text || "Not specified";

  return (
    <div className="space-y-4">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Quick Facts</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <Fact label="Job Title" value={job.title} />
          <Fact label="Company" value={job.employer} />
          <Fact label="Location" value={job.location} />
          <Fact label="Employment Type" value="Not specified" />
          <Fact label="Salary" value={salary} />
          {summary?.visa_notes && <Fact label="Visa Status" value={summary.visa_notes} />}
        </div>
      </div>

      {isError || !summary || isSummaryEmpty(summary) ? (
        <>
          <SummaryFallbackNotice />
          <OriginalDescriptionCard job={job} />
        </>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Overview</p>
          {summary.overview ? (
            <p className="text-gray-300 text-sm leading-relaxed">{summary.overview}</p>
          ) : (
            <p className="text-gray-500 text-sm italic">No overview could be extracted.</p>
          )}
        </div>
      )}

      <JobIntelligenceCard job={job} />

      <ViewListingLink job={job} />
    </div>
  );
}

// ── AI Summary tab ───────────────────────────────────────────────────────────

function AISummaryTab({
  job,
  summary,
  isLoading,
  isError,
}: {
  job: Job;
  summary: JobSummary | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-24 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  const hasAnySection =
    !!summary &&
    (summary.responsibilities.length ||
      summary.requirements_required.length ||
      summary.requirements_preferred.length ||
      summary.benefits.length ||
      summary.work_environment.length);

  if (isError || !summary || isSummaryEmpty(summary) || !hasAnySection) {
    return (
      <div className="space-y-4">
        <SummaryFallbackNotice />
        <OriginalDescriptionCard job={job} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <BulletCard label="Responsibilities" items={summary.responsibilities} />
      <BulletCard label="Required Qualifications" items={summary.requirements_required} />
      <BulletCard label="Preferred Qualifications" items={summary.requirements_preferred} />
      <BulletCard label="Benefits" items={summary.benefits} />
      <BulletCard label="Work Environment" items={summary.work_environment} />
      {summary.warnings.length > 0 && (
        <div className="bg-yellow-950/30 border border-yellow-900/50 rounded-xl p-5">
          <p className="text-xs font-semibold text-yellow-500/80 uppercase tracking-wide mb-3">Warnings</p>
          <ul className="text-sm text-yellow-200/90 space-y-1.5 leading-relaxed">
            {summary.warnings.map((w, i) => (
              <li key={i}>⚠ {w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Original Description tab ─────────────────────────────────────────────────

function OriginalDescriptionTab({ job }: { job: Job }) {
  return (
    <div className="space-y-4">
      <OriginalDescriptionCard job={job} />
      <ViewListingLink job={job} />
    </div>
  );
}

// ── Activity tab ──────────────────────────────────────────────────────────────

type TimelineEntry =
  | { kind: "discovered"; at: string }
  | { kind: "rescanned"; at: string }
  | { kind: "analysed"; at: string; score: number | null }
  | { kind: "change"; at: string; change: JobChange }
  | { kind: "session"; at: string; event: ApplicationEvent };

const SESSION_EVENT_LABELS: Record<string, { icon: string; title: string }> = {
  session_started: { icon: "🚀", title: "Application started" },
  session_resumed: { icon: "▶️", title: "Application resumed" },
  session_completed: { icon: "✅", title: "Application completed" },
  session_cancelled: { icon: "✖️", title: "Application cancelled" },
};

function buildTimeline(job: Job, changes: JobChange[], events: ApplicationEvent[]): TimelineEntry[] {
  const entries: TimelineEntry[] = [{ kind: "discovered", at: job.first_seen_at }];

  if (job.ai_analysed_at) {
    entries.push({ kind: "analysed", at: job.ai_analysed_at, score: job.ai_match_score });
  }

  if (job.last_seen_at && job.last_seen_at !== job.first_seen_at) {
    entries.push({ kind: "rescanned", at: job.last_seen_at });
  }

  for (const change of changes) {
    entries.push({ kind: "change", at: change.detected_at, change });
  }

  for (const event of events) {
    if (event.event_type in SESSION_EVENT_LABELS) {
      entries.push({ kind: "session", at: event.created_at, event });
    }
  }

  return entries.sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime());
}

function TimelineRow({ entry }: { entry: TimelineEntry }) {
  let icon = "•";
  let title = "";
  let detail: string | null = null;

  switch (entry.kind) {
    case "discovered":
      icon = "🔍";
      title = "Job discovered";
      break;
    case "rescanned":
      icon = "🔁";
      title = "Seen again in a scan";
      break;
    case "analysed":
      icon = "✨";
      title = "AI analysis completed";
      detail = entry.score !== null ? `Match score: ${Math.round(entry.score)}/100` : null;
      break;
    case "change": {
      icon = "✏️";
      const field = entry.change.field_changed.replace(/_/g, " ");
      title = `${field.charAt(0).toUpperCase()}${field.slice(1)} changed`;
      detail = `${entry.change.old_value ?? "—"} → ${entry.change.new_value ?? "—"}`;
      break;
    }
    case "session": {
      const cfg = SESSION_EVENT_LABELS[entry.event.event_type];
      icon = cfg.icon;
      title = cfg.title;
      detail = entry.event.detail;
      break;
    }
  }

  return (
    <li className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-gray-200 font-medium flex items-center gap-2">
          <span>{icon}</span>
          {title}
        </p>
        <span className="text-xs text-gray-600" title={formatDate(entry.at)}>
          {formatRelativeTime(entry.at)}
        </span>
      </div>
      {detail && <p className="text-xs text-gray-500 mt-1 ml-6">{detail}</p>}
    </li>
  );
}

function ActivityTab({ job }: { job: Job }) {
  const {
    data: changes = [],
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["jobChanges", job.id],
    queryFn: () => api.jobChanges(job.id),
  });

  // Application Session lifecycle events (Phase 8) — merged in only when an
  // Application record exists for this job yet.
  const { data: kit } = useQuery({
    queryKey: ["applicationKit", job.id],
    queryFn: () => api.applicationKit(job.id),
  });
  const applicationId = kit?.application?.id;

  const { data: events = [] } = useQuery({
    queryKey: ["applicationTimeline", applicationId],
    queryFn: () => api.applicationTimeline(applicationId!),
    enabled: !!applicationId,
  });

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-14 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (isError) {
    return <ErrorBanner title="Couldn't load activity" message={errorMessage(error)} />;
  }

  const timeline = buildTimeline(job, changes, events);

  return (
    <ul className="space-y-2">
      {timeline.map((entry, i) => (
        <TimelineRow key={i} entry={entry} />
      ))}
    </ul>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const jobId = Number(id);
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get("tab");
  const [tab, setTab] = useState<Tab>(
    initialTab && VALID_TABS.has(initialTab as Tab) ? (initialTab as Tab) : "overview",
  );

  // Keep the URL's ?tab= in sync so deep links (e.g. "Start Application"
  // from the Jobs page) and in-page tab switches both work.
  useEffect(() => {
    const current = searchParams.get("tab");
    if (current !== tab) {
      const next = new URLSearchParams(searchParams);
      next.set("tab", tab);
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const {
    data: job,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.job(jobId),
    enabled: Number.isFinite(jobId),
  });

  const {
    data: summary,
    isLoading: summaryLoading,
    isError: summaryError,
  } = useQuery({
    queryKey: ["jobSummary", jobId],
    queryFn: () => api.jobSummary(jobId),
    enabled: Number.isFinite(jobId),
  });

  if (isLoading) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="h-24 bg-gray-900 border border-gray-800 rounded-xl animate-pulse mb-6" />
        <div className="h-64 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
      </div>
    );
  }

  if (isError || !job) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <Link to="/" className="text-sm text-gray-500 hover:text-gray-300 transition-colors">
          ← Back to Jobs
        </Link>
        <div className="mt-4">
          <ErrorBanner
            title="Couldn't load job"
            message={errorMessage(error)}
            onRetry={() => refetch()}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <Link to="/" className="text-sm text-gray-500 hover:text-gray-300 transition-colors">
        ← Back to Jobs
      </Link>

      <header className="mt-4 mb-6 flex items-start gap-4">
        <div
          className={`flex-none w-14 h-14 rounded-lg flex flex-col items-center justify-center text-center shrink-0 ${scoreColor(job.ai_match_score)}`}
        >
          {job.ai_match_score !== null ? (
            <>
              <span className="text-xl font-bold leading-none">{Math.round(job.ai_match_score)}</span>
              <span className="text-[10px] opacity-70">/100</span>
            </>
          ) : (
            <span className="text-[10px] leading-tight text-center px-1">Unscored</span>
          )}
        </div>
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-white leading-snug">{job.title}</h1>
          <p className="text-gray-400 text-sm mt-1">
            {job.employer}
            <span className="text-gray-600 mx-1.5">·</span>
            {job.location}
          </p>
        </div>
      </header>

      <div className="border-b border-gray-800 mb-6">
        <nav className="flex gap-1 overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${
                tab === t.id
                  ? "border-blue-500 text-white"
                  : "border-transparent text-gray-500 hover:text-gray-300"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {tab === "overview" && (
        <OverviewTab job={job} summary={summary} isLoading={summaryLoading} isError={summaryError} />
      )}
      {tab === "ai_summary" && (
        <AISummaryTab job={job} summary={summary} isLoading={summaryLoading} isError={summaryError} />
      )}
      {tab === "original" && <OriginalDescriptionTab job={job} />}
      {tab === "workspace" && <AIWorkspace job={job} />}
      {tab === "apply" && <ApplicationKit job={job} onGoToWorkspace={() => setTab("workspace")} />}
      {tab === "activity" && <ActivityTab job={job} />}
    </div>
  );
}
