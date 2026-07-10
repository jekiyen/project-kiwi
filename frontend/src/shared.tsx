import type { ApplicationStatus } from "./api/client";

// Backend serializes naive UTC datetimes with no timezone designator
// (e.g. "2026-07-10T06:33:02"). JS Date parses that as local time, so
// treat it as UTC explicitly before handing it to Date.
function toUtcDate(iso: string): Date {
  const hasTimezone = /Z$|[+-]\d{2}:\d{2}$/.test(iso);
  return new Date(hasTimezone ? iso : `${iso}Z`);
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return toUtcDate(iso).toLocaleString();
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

export function scoreColor(score: number | null): string {
  if (score === null) return "bg-gray-800/80 text-gray-500 border border-dashed border-gray-700";
  if (score >= 70) return "bg-green-900/50 text-green-300 ring-1 ring-green-800/50";
  if (score >= 40) return "bg-yellow-900/50 text-yellow-300 ring-1 ring-yellow-800/50";
  return "bg-red-900/50 text-red-300 ring-1 ring-red-800/50";
}

export function priorityColor(p: string | null): string {
  if (p === "P1") return "bg-blue-900/50 text-blue-300";
  if (p === "P2") return "bg-purple-900/50 text-purple-300";
  if (p === "P3") return "bg-gray-700 text-gray-300";
  return "hidden";
}

export const APP_STATUS_COLORS: Record<ApplicationStatus, string> = {
  saved: "bg-gray-700 text-gray-300",
  applied: "bg-blue-900/50 text-blue-300",
  interview: "bg-yellow-900/50 text-yellow-300",
  offer: "bg-green-900/50 text-green-300",
  visa: "bg-emerald-900/50 text-emerald-300",
  rejected: "bg-red-900/50 text-red-400",
  archived: "bg-gray-800 text-gray-500",
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
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${APP_STATUS_COLORS[status]}`}
    >
      {APP_STATUS_LABELS[status]}
    </span>
  );
}

export function SkeletonStatCard() {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 animate-pulse">
      <div className="h-3 bg-gray-800 rounded w-16" />
      <div className="h-7 bg-gray-800 rounded w-10 mt-2" />
    </div>
  );
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
        <button
          onClick={onRetry}
          className="mt-4 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm font-medium text-gray-200 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}
