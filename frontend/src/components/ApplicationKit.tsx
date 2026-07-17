import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CheckCircle2, Circle, HelpCircle, Rocket } from "lucide-react";
import {
  api,
  type ApplicationSessionOutcome,
  type Job,
  type SectionReadiness,
} from "../api/client";
import { useToast } from "../hooks/useToast";
import { errorMessage, formatDate, formatRelativeTime } from "../shared";
import { ScoreGauge, ProgressBar } from "../design/ScoreGauge";
import { Surface, SectionLabel } from "../design/Surface";
import { buttonClasses, scoreTone } from "../design/tokens";

// The Application Kit — Kiwi assists, the user submits. Launch only ever
// opens the employer's original job URL in a new tab; Kiwi never fills in
// or submits the employer's form itself. Every readiness signal here comes
// from the single Application Readiness Engine (backend/core/
// application_readiness.py) via GET /jobs/{id}/application-kit — nothing is
// re-derived on the frontend. See docs/ROADMAP.md Phase 8.
//
// "Application Launch" — this is meant to be one of the most crafted
// screens in Kiwi: readiness visualized as a gauge + progress bar, the
// section checklist as a clear scannable list, and Launch treated as the
// climax of the preparation workflow rather than another card footer.

function formatDuration(seconds: number): string {
  if (seconds < 60) return "less than a minute";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return rem ? `${hours}h ${rem}m` : `${hours}h`;
}

const SECTION_CONFIG: {
  key: keyof SectionReadiness;
  label: string;
  readyDetail: (job: Job) => string;
  missingDetail: string;
  action: { label: string; to: string };
}[] = [
  {
    key: "resume",
    label: "Resume",
    readyDetail: () => "Active Resume Vault document set.",
    missingDetail: "No active resume set in the Resume Vault.",
    action: { label: "Go to Resume Vault", to: "/resume" },
  },
  {
    key: "cover_letter",
    label: "Cover Letter",
    readyDetail: (job) =>
      job.cover_letter_generated_at
        ? `Generated ${formatRelativeTime(job.cover_letter_generated_at)}.`
        : "Generated.",
    missingDetail: "No cover letter generated yet for this job.",
    action: { label: "Generate in AI Workspace", to: "workspace" },
  },
  {
    key: "application_profile",
    label: "Application Profile",
    readyDetail: () => "Profile filled in.",
    missingDetail: "Application Profile hasn't been filled in yet.",
    action: { label: "Go to Application Profile", to: "/application-profile" },
  },
  {
    key: "references",
    label: "References",
    readyDetail: () => "At least one reference on file.",
    missingDetail: "No references added yet.",
    action: { label: "Add a Reference", to: "/application-profile" },
  },
  {
    key: "work_rights",
    label: "Work Rights",
    readyDetail: () => "Visa status / current country recorded.",
    missingDetail: "Visa status and current country not recorded.",
    action: { label: "Go to Application Profile", to: "/application-profile" },
  },
];

function SectionRow({
  config,
  ready,
  job,
  onGoToWorkspace,
}: {
  config: (typeof SECTION_CONFIG)[number];
  ready: boolean;
  job: Job;
  onGoToWorkspace: () => void;
}) {
  const Icon = ready ? CheckCircle2 : Circle;
  return (
    <div className="flex items-start justify-between gap-3 py-2.5 border-b border-gray-800 last:border-0">
      <div className="flex items-start gap-2.5 min-w-0">
        <Icon
          className={`w-4 h-4 flex-none mt-0.5 ${ready ? "text-emerald-400" : "text-gray-600"}`}
          strokeWidth={2}
        />
        <div className="min-w-0">
          <p className="text-sm text-gray-200 font-medium">{config.label}</p>
          <p className="text-xs text-gray-500 mt-0.5">
            {ready ? config.readyDetail(job) : config.missingDetail}
          </p>
        </div>
      </div>
      {!ready &&
        (config.action.to === "workspace" ? (
          <button onClick={onGoToWorkspace} className={`flex-none ${buttonClasses("secondary", "sm")}`}>
            {config.action.label}
          </button>
        ) : (
          <Link to={config.action.to} className={`flex-none ${buttonClasses("secondary", "sm")}`}>
            {config.action.label}
          </Link>
        ))}
    </div>
  );
}

const OUTCOME_BUTTONS: { outcome: ApplicationSessionOutcome; label: string; cls: string }[] = [
  { outcome: "applied", label: "Applied", cls: "bg-emerald-600 hover:bg-emerald-500 text-white" },
  { outcome: "not_yet", label: "Not Yet", cls: "border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500" },
  { outcome: "cancelled", label: "Cancelled", cls: "border border-gray-700 text-gray-400 hover:text-red-400 hover:border-red-900" },
];

export default function ApplicationKit({
  job,
  onGoToWorkspace,
}: {
  job: Job;
  onGoToWorkspace: () => void;
}) {
  const qc = useQueryClient();
  const { push } = useToast();

  const { data: kit, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["applicationKit", job.id],
    queryFn: () => api.applicationKit(job.id),
  });

  const invalidateAfterChange = () => {
    qc.invalidateQueries({ queryKey: ["applicationKit", job.id] });
    qc.invalidateQueries({ queryKey: ["applications"] });
    qc.invalidateQueries({ queryKey: ["readinessSummary"] });
    if (kit?.application) {
      qc.invalidateQueries({ queryKey: ["applicationTimeline", kit.application.id] });
    }
  };

  const launchMutation = useMutation({
    mutationFn: () => api.launchApplication(job.id),
    onSuccess: (data) => {
      window.open(data.url, "_blank", "noopener,noreferrer");
      invalidateAfterChange();
    },
    onError: (err) => push(`Couldn't launch: ${errorMessage(err)}`, "error"),
  });

  const completeMutation = useMutation({
    mutationFn: (outcome: ApplicationSessionOutcome) =>
      api.completeApplicationSession(job.id, outcome),
    onSuccess: (_, outcome) => {
      const messages: Record<ApplicationSessionOutcome, string> = {
        applied: "Marked as Applied — nice work.",
        not_yet: "No problem — come back and Launch again when you're ready.",
        cancelled: "Application cancelled.",
      };
      push(messages[outcome], outcome === "cancelled" ? "info" : "success");
      invalidateAfterChange();
    },
    onError: (err) => push(`Couldn't update: ${errorMessage(err)}`, "error"),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-40 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
        <div className="h-64 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
      </div>
    );
  }

  if (isError || !kit) {
    return (
      <div className="bg-red-950/30 border border-red-900/50 rounded-xl p-6 text-center">
        <p className="text-red-400 font-medium">Couldn't load the Application Kit</p>
        <p className="text-gray-500 text-sm mt-1">{errorMessage(error)}</p>
        <button onClick={() => refetch()} className={`mt-4 ${buttonClasses("secondary")}`}>
          Retry
        </button>
      </div>
    );
  }

  const { readiness, active_session } = kit;
  const sectionValues = Object.values(readiness.sections);
  const readyCount = sectionValues.filter(Boolean).length;
  const totalSections = sectionValues.length;

  return (
    <div className="space-y-5">
      {/* Manual completion banner — shown whenever a launched session is awaiting an outcome */}
      {active_session && (
        <Surface tier="primary" className="!border-blue-800/60 bg-blue-950/20">
          <div className="flex items-start gap-3">
            <HelpCircle className="w-5 h-5 text-blue-400 flex-none mt-0.5" />
            <div>
              <p className="text-white font-medium">Did you successfully submit this application?</p>
              <p className="text-xs text-gray-400 mt-1">
                Launched {formatRelativeTime(active_session.started_at)} · Kiwi never submits anything on
                its own — you tell it what happened.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 mt-4">
            {OUTCOME_BUTTONS.map((b) => (
              <button
                key={b.outcome}
                onClick={() => completeMutation.mutate(b.outcome)}
                disabled={completeMutation.isPending}
                className={`text-sm px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 ${b.cls}`}
              >
                {completeMutation.isPending && completeMutation.variables === b.outcome
                  ? "Saving…"
                  : b.label}
              </button>
            ))}
          </div>
        </Surface>
      )}

      {/* Readiness overview — the gauge + progress bar visualization */}
      <Surface>
        <div className="flex items-start gap-5 flex-wrap">
          <ScoreGauge score={readiness.score} size="lg" caption="Readiness" />
          <div className="flex-1 min-w-[200px]">
            <div className="flex items-center justify-between gap-3">
              <SectionLabel>{readyCount} of {totalSections} ready</SectionLabel>
              <span className="text-xs text-gray-500">~{readiness.estimated_minutes} min to finish prep</span>
            </div>
            <ProgressBar value={readyCount} max={totalSections} tone={scoreTone(readiness.score)} className="mt-2" />

            {readiness.missing.length > 0 && (
              <div className="mt-4">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  Missing Information
                </p>
                <ul className="text-sm text-gray-300 space-y-1">
                  {readiness.missing.map((m) => (
                    <li key={m}>• {m} missing</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </Surface>

      {/* Section checklist */}
      <Surface>
        {SECTION_CONFIG.map((config) => (
          <SectionRow
            key={config.key}
            config={config}
            ready={readiness.sections[config.key]}
            job={job}
            onGoToWorkspace={onGoToWorkspace}
          />
        ))}
      </Surface>

      {/* Launch — the climax of the preparation workflow */}
      <Surface tier="primary" className="!border-blue-900/50">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-start gap-3">
            <Rocket className="w-6 h-6 text-blue-400 flex-none mt-0.5" strokeWidth={1.75} />
            <div>
              <p className="text-white font-semibold">
                {active_session ? "Application in progress" : "Ready to open the employer's site?"}
              </p>
              <p className="text-xs text-gray-500 mt-1 max-w-md">
                Kiwi opens the original job listing in a new tab. You fill in and submit the form yourself
                — Kiwi never does it for you.
              </p>
            </div>
          </div>
          <button
            onClick={() => launchMutation.mutate()}
            disabled={launchMutation.isPending}
            className={`flex-none text-base px-6 py-3 ${buttonClasses("primary")}`}
          >
            {launchMutation.isPending ? "Launching…" : active_session ? "Reopen Listing" : "Launch Application"}
          </button>
        </div>
      </Surface>

      {/* Session detail */}
      {active_session && (
        <Surface>
          <SectionLabel className="mb-3">Application Session</SectionLabel>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Started</p>
              <p className="text-gray-200 mt-0.5" title={formatDate(active_session.started_at)}>
                {formatRelativeTime(active_session.started_at)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Last Opened</p>
              <p className="text-gray-200 mt-0.5" title={formatDate(active_session.last_opened_at)}>
                {formatRelativeTime(active_session.last_opened_at)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Duration</p>
              <p className="text-gray-200 mt-0.5">{formatDuration(active_session.duration_seconds)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Resume Version</p>
              <p className="text-gray-200 mt-0.5 truncate">{active_session.resume_version ?? "—"}</p>
            </div>
          </div>
        </Surface>
      )}
    </div>
  );
}
