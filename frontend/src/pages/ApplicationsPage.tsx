import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ApplicationWithJob, type ApplicationStatus, type ApplicationEvent } from "../api/client";
import { useToast } from "../hooks/useToast";
import {
  AppStatusBadge,
  APP_STATUS_LABELS,
  ALL_STATUSES,
  ErrorBanner,
  errorMessage,
  formatDate,
  formatRelativeTime,
  scoreColor,
} from "../shared";

// ── Timeline ──────────────────────────────────────────────────────────────────

function timelineEventLabel(event: ApplicationEvent): string {
  if (event.event_type === "created") {
    return `Application created — ${APP_STATUS_LABELS[event.to_status as ApplicationStatus]}`;
  }
  if (event.event_type === "status_change") {
    const from = event.from_status ? APP_STATUS_LABELS[event.from_status] : "—";
    const to = event.to_status ? APP_STATUS_LABELS[event.to_status] : "—";
    return `${from} → ${to}`;
  }
  return event.detail ?? event.event_type;
}

function Timeline({ applicationId }: { applicationId: number }) {
  const { data: events = [], isLoading, isError } = useQuery({
    queryKey: ["applicationTimeline", applicationId],
    queryFn: () => api.applicationTimeline(applicationId),
  });

  if (isLoading) return <p className="text-xs text-gray-600 mt-2">Loading history…</p>;
  if (isError) return <p className="text-xs text-red-400 mt-2">Couldn't load history.</p>;
  if (events.length === 0) return <p className="text-xs text-gray-600 mt-2">No history yet.</p>;

  return (
    <ol className="mt-2 space-y-2 border-l border-gray-800 pl-3">
      {events.map((event) => (
        <li key={event.id} className="relative text-xs">
          <span className="absolute -left-[15px] top-1 w-2 h-2 rounded-full bg-gray-600" />
          <p className="text-gray-300">{timelineEventLabel(event)}</p>
          <p className="text-gray-600" title={formatDate(event.created_at)}>
            {formatRelativeTime(event.created_at)}
          </p>
        </li>
      ))}
    </ol>
  );
}

// ── Status filter tabs ─────────────────────────────────────────────────────────

type FilterStatus = ApplicationStatus | "all";

const TABS: { value: FilterStatus; label: string }[] = [
  { value: "all", label: "All" },
  ...ALL_STATUSES.map((s) => ({ value: s as FilterStatus, label: APP_STATUS_LABELS[s] })),
];

// ── Application card ───────────────────────────────────────────────────────────

interface AppCardProps {
  app: ApplicationWithJob;
  onPatch: (body: Parameters<typeof api.patchApplication>[1]) => void;
  onDelete: () => void;
  isSaving: boolean;
}

function AppCard({ app, onPatch, onDelete, isSaving }: AppCardProps) {
  const [notes, setNotes] = useState(app.notes ?? "");
  const [interviewDate, setInterviewDate] = useState(
    app.interview_date ? app.interview_date.slice(0, 10) : ""
  );
  const [followUpDate, setFollowUpDate] = useState(
    app.follow_up_date ? app.follow_up_date.slice(0, 10) : ""
  );
  const [resumeVersion, setResumeVersion] = useState(app.resume_version ?? "");
  const [coverLetterVersion, setCoverLetterVersion] = useState(app.cover_letter_version ?? "");
  const [showTimeline, setShowTimeline] = useState(false);

  // Sync local state when server data refreshes
  useEffect(() => setNotes(app.notes ?? ""), [app.notes]);
  useEffect(
    () => setInterviewDate(app.interview_date ? app.interview_date.slice(0, 10) : ""),
    [app.interview_date]
  );
  useEffect(
    () => setFollowUpDate(app.follow_up_date ? app.follow_up_date.slice(0, 10) : ""),
    [app.follow_up_date]
  );
  useEffect(() => setResumeVersion(app.resume_version ?? ""), [app.resume_version]);
  useEffect(
    () => setCoverLetterVersion(app.cover_letter_version ?? ""),
    [app.cover_letter_version]
  );

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-white font-medium truncate">{app.job_title}</h3>
          <p className="text-gray-400 text-sm">
            {app.job_employer} · {app.job_location}
          </p>
        </div>
        <div className="flex-none flex items-center gap-2">
          <AppStatusBadge status={app.status} />
          {/* Status change */}
          <select
            value={app.status}
            onChange={(e) => onPatch({ status: e.target.value })}
            className="text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300 focus:outline-none focus:border-gray-500"
          >
            {ALL_STATUSES.map((s) => (
              <option key={s} value={s}>
                {APP_STATUS_LABELS[s]}
              </option>
            ))}
          </select>
          <button
            onClick={onDelete}
            className="text-gray-600 hover:text-red-400 text-lg leading-none transition-colors"
            title="Remove application"
          >
            ×
          </button>
        </div>
      </div>

      {/* Score + salary + view link */}
      <div className="flex items-center gap-3 mt-2">
        {app.job_ai_match_score !== null && (
          <span
            className={`text-xs px-2 py-0.5 rounded font-medium ${scoreColor(app.job_ai_match_score)}`}
          >
            {app.job_ai_match_score}/100
          </span>
        )}
        {app.job_salary_text && (
          <span className="text-xs text-gray-500">{app.job_salary_text}</span>
        )}
        <a
          href={app.job_url}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
        >
          View listing →
        </a>
        {app.applied_at && (
          <span className="text-xs text-gray-600">
            Applied {formatDate(app.applied_at)}
          </span>
        )}
        {isSaving && (
          <span className="text-xs text-gray-500 italic">Saving…</span>
        )}
      </div>

      {/* Notes + dates */}
      <div className="mt-3 space-y-3">
        <div>
          <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">
            Notes
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            onBlur={() => {
              if (notes !== (app.notes ?? "")) onPatch({ notes });
            }}
            placeholder="Add notes about this application…"
            rows={2}
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 resize-none focus:outline-none focus:border-gray-500 transition-colors"
          />
        </div>
        <div className="flex flex-wrap gap-4">
          <div>
            <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">
              Interview Date
            </label>
            <input
              type="date"
              value={interviewDate}
              onChange={(e) => {
                setInterviewDate(e.target.value);
                if (e.target.value) {
                  onPatch({ interview_date: `${e.target.value}T00:00:00` });
                }
              }}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 focus:outline-none focus:border-gray-500 transition-colors"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">
              Follow-up Date
            </label>
            <input
              type="date"
              value={followUpDate}
              onChange={(e) => {
                setFollowUpDate(e.target.value);
                if (e.target.value) {
                  onPatch({ follow_up_date: `${e.target.value}T00:00:00` });
                }
              }}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 focus:outline-none focus:border-gray-500 transition-colors"
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[180px]">
            <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">
              Resume Version
            </label>
            <input
              type="text"
              value={resumeVersion}
              onChange={(e) => setResumeVersion(e.target.value)}
              onBlur={() => {
                if (resumeVersion !== (app.resume_version ?? "")) {
                  onPatch({ resume_version: resumeVersion });
                }
              }}
              placeholder="e.g. resume_v2_warehouse.pdf"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500 transition-colors"
            />
          </div>
          <div className="flex-1 min-w-[180px]">
            <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">
              Cover Letter Version
            </label>
            <input
              type="text"
              value={coverLetterVersion}
              onChange={(e) => setCoverLetterVersion(e.target.value)}
              onBlur={() => {
                if (coverLetterVersion !== (app.cover_letter_version ?? "")) {
                  onPatch({ cover_letter_version: coverLetterVersion });
                }
              }}
              placeholder="e.g. cl_seek_fruitpicker.docx"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500 transition-colors"
            />
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between mt-3">
        <p className="text-xs text-gray-600">Updated {formatDate(app.updated_at)}</p>
        <button
          type="button"
          onClick={() => setShowTimeline((v) => !v)}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          {showTimeline ? "Hide history" : "Show history"}
        </button>
      </div>

      {showTimeline && <Timeline applicationId={app.id} />}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function ApplicationsPage() {
  const qc = useQueryClient();
  const { push } = useToast();
  const [activeStatus, setActiveStatus] = useState<FilterStatus>("all");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // Debounce search 300ms
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const {
    data: apps = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["applications", activeStatus, debouncedSearch],
    queryFn: () =>
      api.applications({
        status: activeStatus === "all" ? undefined : activeStatus,
        search: debouncedSearch || undefined,
      }),
  });

  const patchMutation = useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: number;
      body: Parameters<typeof api.patchApplication>[1];
    }) => api.patchApplication(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
    onError: (err) => push(`Couldn't save changes: ${errorMessage(err)}`, "error"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteApplication(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      push("Application removed", "success");
    },
    onError: (err) => push(`Couldn't remove application: ${errorMessage(err)}`, "error"),
  });

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Page heading */}
      <div className="mb-6">
        <h2 className="text-xl font-bold text-white">Applications</h2>
        <p className="text-gray-500 text-sm mt-0.5">
          {apps.length} {apps.length === 1 ? "application" : "applications"}
          {activeStatus !== "all" ? ` · ${APP_STATUS_LABELS[activeStatus as ApplicationStatus]}` : ""}
        </p>
      </div>

      {/* Search */}
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search by title or employer…"
        className="w-full bg-gray-900 border border-gray-800 rounded-lg px-4 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-600 mb-4 transition-colors"
      />

      {/* Status filter tabs */}
      <div className="flex gap-1.5 flex-wrap mb-5">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setActiveStatus(tab.value)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeStatus === tab.value
                ? "bg-gray-700 text-white"
                : "bg-gray-900 text-gray-400 border border-gray-800 hover:text-gray-200 hover:border-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* List */}
      {isLoading ? (
        <p className="text-gray-500 text-sm">Loading…</p>
      ) : isError ? (
        <ErrorBanner
          title="Couldn't load applications"
          message={errorMessage(error)}
          onRetry={() => refetch()}
        />
      ) : apps.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
          <p className="text-gray-500 text-sm">
            {activeStatus === "all" && !debouncedSearch
              ? "No applications yet. Save or apply to jobs from the Jobs page."
              : "No applications match this filter."}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {apps.map((app) => (
            <AppCard
              key={app.id}
              app={app}
              onPatch={(body) => patchMutation.mutate({ id: app.id, body })}
              onDelete={() => deleteMutation.mutate(app.id)}
              isSaving={
                patchMutation.isPending &&
                (patchMutation.variables as { id: number })?.id === app.id
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
