import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, type Job, type JobChange } from "../api/client";
import AIWorkspace from "../components/AIWorkspace";
import { ErrorBanner, errorMessage, formatDate, formatRelativeTime, scoreColor, sourceLabel } from "../shared";

type Tab = "description" | "workspace" | "activity";

const TABS: { id: Tab; label: string }[] = [
  { id: "description", label: "Description" },
  { id: "workspace", label: "AI Workspace" },
  { id: "activity", label: "Activity" },
];

function DescriptionTab({ job }: { job: Job }) {
  return (
    <div className="space-y-4">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-400 mb-4">
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
        {job.description ? (
          <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">{job.description}</p>
        ) : (
          <p className="text-gray-500 text-sm italic">No description available for this job.</p>
        )}
      </div>
      <a
        href={job.url}
        target="_blank"
        rel="noreferrer"
        className="inline-block text-sm text-blue-400 hover:text-blue-300 transition-colors"
      >
        View original listing →
      </a>
    </div>
  );
}

function ActivityTab({ jobId }: { jobId: number }) {
  const {
    data: changes = [],
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["jobChanges", jobId],
    queryFn: () => api.jobChanges(jobId),
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

  if (changes.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 border-dashed rounded-xl p-8 text-center">
        <p className="text-gray-500 text-sm">No changes detected for this job yet.</p>
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {changes.map((change: JobChange) => (
        <li key={change.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-gray-200 font-medium capitalize">
              {change.field_changed.replace(/_/g, " ")} changed
            </p>
            <span className="text-xs text-gray-600" title={formatDate(change.detected_at)}>
              {formatRelativeTime(change.detected_at)}
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {change.old_value ?? "—"} <span className="text-gray-700">→</span> {change.new_value ?? "—"}
          </p>
        </li>
      ))}
    </ul>
  );
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const jobId = Number(id);
  const [tab, setTab] = useState<Tab>("description");

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
        <nav className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
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

      {tab === "description" && <DescriptionTab job={job} />}
      {tab === "workspace" && <AIWorkspace job={job} />}
      {tab === "activity" && <ActivityTab jobId={job.id} />}
    </div>
  );
}
