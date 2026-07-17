import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type Job } from "../api/client";
import { RecommendationBadge, errorMessage } from "../shared";

// Job Intelligence (Phase 9) — deterministic scoring, recommendation, and
// gap analysis. Every number and reason here comes from backend/core/
// job_intelligence.py, the single evaluator — nothing is computed or
// invented on the frontend. Never calls an AI provider.

function scoreTextColor(score: number): string {
  if (score >= 70) return "text-green-300";
  if (score >= 40) return "text-yellow-300";
  return "text-red-300";
}

function WhyThisJobCard({ reasons }: { reasons: string[] }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Why This Job</p>
      <ul className="text-sm text-gray-300 space-y-1.5 leading-relaxed">
        {reasons.map((r, i) => (
          <li key={i}>• {r}</li>
        ))}
      </ul>
    </div>
  );
}

function MissingRequirementsCard({ missing }: { missing: string[] }) {
  if (missing.length === 0) return null;
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
        Missing Requirements
      </p>
      <ul className="text-sm text-gray-400 space-y-1.5 leading-relaxed">
        {missing.map((m, i) => (
          <li key={i}>• {m}</li>
        ))}
      </ul>
    </div>
  );
}

function SimilarJobsCard({ jobId }: { jobId: number }) {
  const { data: similar = [], isLoading } = useQuery({
    queryKey: ["similarJobs", jobId],
    queryFn: () => api.similarJobs(jobId),
  });

  if (isLoading) {
    return <div className="h-24 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />;
  }
  if (similar.length === 0) return null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Similar Jobs</p>
      <ul className="space-y-2">
        {similar.map((s) => (
          <li key={s.id}>
            <Link
              to={`/jobs/${s.id}`}
              className="flex items-center justify-between gap-3 text-sm text-gray-300 hover:text-white transition-colors"
            >
              <span className="truncate">
                {s.title} <span className="text-gray-600">· {s.employer}</span>
              </span>
              <span className="flex-none text-xs text-gray-500">{s.location}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function JobIntelligenceCard({ job }: { job: Job }) {
  const { data: intelligence, isLoading, isError, error } = useQuery({
    queryKey: ["jobIntelligence", job.id],
    queryFn: () => api.jobIntelligence(job.id),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-28 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
        <div className="h-28 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
      </div>
    );
  }

  if (isError || !intelligence) {
    return (
      <p className="text-sm text-red-400">
        Couldn't load Job Intelligence: {errorMessage(error)}
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Job Intelligence
          </p>
          <RecommendationBadge level={intelligence.recommendation} />
        </div>
        <div className="grid grid-cols-2 gap-4 mt-4">
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide">Score</p>
            <p className={`text-2xl font-bold mt-0.5 ${scoreTextColor(intelligence.score)}`}>
              {intelligence.score}/100
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide">Confidence</p>
            <p className="text-2xl font-bold mt-0.5 text-gray-200">{intelligence.confidence}%</p>
          </div>
        </div>
      </div>

      <WhyThisJobCard reasons={intelligence.reasons} />
      <MissingRequirementsCard missing={intelligence.missing_requirements} />
      <SimilarJobsCard jobId={job.id} />
    </div>
  );
}
