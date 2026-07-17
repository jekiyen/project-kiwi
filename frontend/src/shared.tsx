import { AlertTriangle } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";
import type { ApplicationReadinessStatus, ApplicationStatus, RecommendationLevel } from "./api/client";
import { Badge } from "./design/Badge";
import { buttonClasses, type Tone } from "./design/tokens";

// Backend serializes naive UTC datetimes with no timezone designator
// (e.g. "2026-07-10T06:33:02"). JS Date parses that as local time, so
// treat it as UTC explicitly before handing it to Date.
function toUtcDate(iso: string): Date {
  const hasTimezone = /Z$|[+-]\d{2}:\d{2}$/.test(iso);
  return new Date(hasTimezone ? iso : `${iso}Z`);
}

// The app always displays in Asia/Jakarta (GMT+7), regardless of the
// browser's own timezone, so timestamps read the same no matter where the
// dashboard is opened from.
const DISPLAY_TZ = "Asia/Jakarta";

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return (
    toUtcDate(iso).toLocaleString("en-NZ", {
      timeZone: DISPLAY_TZ,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }) + " WIB"
  );
}

export function formatRelativeTime(iso: string | null): string {
  if (!iso) return "—";
  const then = toUtcDate(iso).getTime();
  const now = Date.now();
  const diffSec = Math.round((then - now) / 1000);
  const absSec = Math.abs(diffSec);

  if (absSec < 60) return "just now";

  const absMin = Math.round(absSec / 60);
  if (absMin < 60) return `${absMin}m ago`;

  const absHr = Math.round(absMin / 60);
  if (absHr < 24) return `${absHr}h ago`;

  const absDay = Math.round(absHr / 24);
  if (absDay < 7) return `${absDay}d ago`;

  return formatDate(iso);
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong";
}

export function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    seek: "SEEK",
    trademe: "Trade Me",
    picknz: "PickNZ",
    backpacker: "Backpacker Board",
    seasonal: "Seasonal Jobs",
    indeed: "Indeed",
  };
  return labels[source.toLowerCase()] ?? source.charAt(0).toUpperCase() + source.slice(1);
}

/** The one 0-100 score → tone mapping used by ScoreGauge and anywhere a raw
 * score needs a text/accent color without the full gauge (see design/tokens.ts). */
export { scoreTone } from "./design/tokens";

export function priorityBadgeTone(p: string | null): Tone | null {
  if (p === "P1") return "info";
  if (p === "P2") return "brand";
  if (p === "P3") return "neutral";
  return null;
}

export const APP_STATUS_TONE: Record<ApplicationStatus, Tone> = {
  saved: "neutral",
  applied: "info",
  interview: "warning",
  offer: "success",
  visa: "success",
  rejected: "danger",
  archived: "neutral",
};

export const APP_STATUS_LABELS: Record<ApplicationStatus, string> = {
  saved: "Saved",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  visa: "Visa",
  rejected: "Rejected",
  archived: "Archived",
};

export const ALL_STATUSES: ApplicationStatus[] = [
  "saved",
  "applied",
  "interview",
  "offer",
  "visa",
  "rejected",
  "archived",
];

export function AppStatusBadge({ status }: { status: ApplicationStatus }) {
  return <Badge tone={APP_STATUS_TONE[status]}>{APP_STATUS_LABELS[status]}</Badge>;
}

// ── Application Copilot workflow state (Phase 8) ────────────────────────────
// The Dashboard's per-job badge: before an Application record exists (or
// while it's still just "saved" with no application in progress), the job
// is either Ready or Preparing to apply, based on Application Readiness
// (backend/core/application_readiness.py — the single evaluator, never
// re-derived here). Once a session has been launched or the application has
// moved past "saved," the real ApplicationStatus takes over.

export type WorkflowState = "ready" | "preparing" | ApplicationStatus;

export function computeWorkflowState(
  applicationStatus: ApplicationStatus | undefined,
  hasActiveSession: boolean,
  readinessStatus: ApplicationReadinessStatus | undefined,
): WorkflowState {
  if (applicationStatus && applicationStatus !== "saved") return applicationStatus;
  if (hasActiveSession) return "preparing";
  return readinessStatus === "ready" ? "ready" : "preparing";
}

const WORKFLOW_STATE_CONFIG: Record<"ready" | "preparing", { label: string; tone: Tone }> = {
  ready: { label: "Ready", tone: "success" },
  preparing: { label: "Preparing", tone: "warning" },
};

export function WorkflowBadge({ state }: { state: WorkflowState }) {
  if (state === "ready" || state === "preparing") {
    const cfg = WORKFLOW_STATE_CONFIG[state];
    return <Badge tone={cfg.tone}>{cfg.label}</Badge>;
  }
  return <AppStatusBadge status={state} />;
}

// ── Job Intelligence (Phase 9) ──────────────────────────────────────────────
// Recommendation levels come from a single deterministic evaluator
// (backend/core/job_intelligence.py) — this is presentation only.

export const RECOMMENDATION_CONFIG: Record<RecommendationLevel, { label: string; tone: Tone }> = {
  highly_recommended: { label: "Highly Recommended", tone: "success" },
  recommended: { label: "Recommended", tone: "info" },
  consider: { label: "Consider", tone: "warning" },
  low_priority: { label: "Low Priority", tone: "neutral" },
};

// Lower rank = higher priority — used to sort the Priority Queue.
export const RECOMMENDATION_RANK: Record<RecommendationLevel, number> = {
  highly_recommended: 0,
  recommended: 1,
  consider: 2,
  low_priority: 3,
};

export function RecommendationBadge({ level }: { level: RecommendationLevel }) {
  const cfg = RECOMMENDATION_CONFIG[level];
  return <Badge tone={cfg.tone}>{cfg.label}</Badge>;
}

export function SkeletonJobCard() {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex gap-4 animate-pulse">
      <div className="flex-none w-14 h-14 rounded-lg bg-gray-800" />
      <div className="flex-1 space-y-2">
        <div className="h-4 bg-gray-800 rounded w-3/4" />
        <div className="h-3 bg-gray-800 rounded w-1/2" />
        <div className="h-3 bg-gray-800 rounded w-full" />
        <div className="flex gap-2 pt-1">
          <div className="h-6 bg-gray-800 rounded w-16" />
          <div className="h-6 bg-gray-800 rounded w-14" />
        </div>
      </div>
    </div>
  );
}

export function SkeletonScanRow() {
  return (
    <tr className="border-t border-gray-800 animate-pulse">
      {[16, 12, 8, 10].map((w) => (
        <td key={w} className="py-2.5 pr-4">
          <div className={`h-3 bg-gray-800 rounded w-${w}`} style={{ width: `${w * 4}px` }} />
        </td>
      ))}
    </tr>
  );
}

export function ErrorBanner({
  title,
  message,
  onRetry,
}: {
  title: string;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="bg-red-950/30 border border-red-900/50 rounded-xl p-6 text-center">
      <p className="text-red-400 font-medium">{title}</p>
      {message && <p className="text-gray-500 text-sm mt-1">{message}</p>}
      {onRetry && (
        <button onClick={onRetry} className={`mt-4 ${buttonClasses("secondary")}`}>
          Retry
        </button>
      )}
    </div>
  );
}

// ── Error boundary ────────────────────────────────────────────────────────────
// Catches render-time crashes anywhere below it so a bug in one page can't
// blank the entire app. Must be a class component — no hook equivalent.

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled render error:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950 p-6">
        <div className="max-w-md w-full bg-gray-900 border border-red-900/50 rounded-xl p-8 text-center">
          <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-3" strokeWidth={1.5} />
          <h1 className="text-white font-semibold text-lg">Something went wrong</h1>
          <p className="text-gray-500 text-sm mt-2 leading-relaxed">
            The dashboard hit an unexpected error. Reloading usually fixes it — if it keeps
            happening, check the browser console for details.
          </p>
          <button onClick={() => window.location.reload()} className={`mt-5 ${buttonClasses("primary")}`}>
            Reload
          </button>
        </div>
      </div>
    );
  }
}
