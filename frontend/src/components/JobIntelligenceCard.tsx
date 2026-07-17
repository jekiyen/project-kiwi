import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CheckCircle2, CircleDashed } from "lucide-react";
import { api, type Job } from "../api/client";
import { errorMessage } from "../shared";
import { Surface, SectionLabel } from "../design/Surface";

// Job Intelligence (Phase 9) — deterministic scoring, recommendation, and
// gap analysis. Every number and reason here comes from backend/core/
// job_intelligence.py, the single evaluator — nothing is computed or
// invented on the frontend. Never calls an AI provider.
//
// Score/Confidence/Recommendation are shown once, above the fold, in
// JobDetailPage's DecisionHeader — this card covers the supporting detail:
// why (positive signals), what's missing (gaps), and what else is similar.
// Why This Job and Missing Requirements get deliberately different visual
// treatments (success vs. warning) since they're opposite-valence content
// that used to look like two identical plain bullet lists.

function WhyThisJobCard({ reasons }: { reasons: string[] }) {
  return (
    <div className="bg-gray-900 border border-emerald-900/40 rounded-xl p-5">
      <SectionLabel className="mb-3">Why This Job</SectionLabel>
      <ul className="text-sm text-gray-300 space-y-2 leading-relaxed">
        {reasons.map((r, i) => (
          <li key={i} className="flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-500/80 flex-none mt-0.5" />
            <span>{r}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MissingRequirementsCard({ missing }: { missing: string[] }) {
  if (missing.length === 0) return null;
  return (
    <div className="bg-gray-900 border border-amber-900/30 rounded-xl p-5">
      <SectionLabel className="mb-3">Missing Requirements</SectionLabel>
      <ul className="text-sm text-gray-400 space-y-2 leading-relaxed">
        {missing.map((m, i) => (
          <li key={i} className="flex items-start gap-2">
            <CircleDashed className="w-4 h-4 text-amber-600/70 flex-none mt-0.5" />
            <span>{m}</span>
          </li>
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
    <Surface>
      <SectionLabel className="mb-3">Similar Jobs</SectionLabel>
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
    </Surface>
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
      <WhyThisJobCard reasons={intelligence.reasons} />
      <MissingRequirementsCard missing={intelligence.missing_requirements} />
      <SimilarJobsCard jobId={job.id} />
    </div>
  );
}
