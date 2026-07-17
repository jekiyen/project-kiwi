import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, History } from "lucide-react";
import { api, type Scan, type ScraperRun } from "../api/client";
import { ErrorBanner, formatDate, formatRelativeTime, sourceLabel } from "../shared";
import { Badge } from "../design/Badge";
import type { Tone } from "../design/tokens";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const rem = Math.round(s % 60);
  return `${m}m ${rem}s`;
}

// ── Status badges — shared Badge primitive, tokens shared with the rest of the app ─

const SCAN_STATUS_TONE: Record<string, Tone> = {
  completed: "success",
  running: "warning",
  failed: "danger",
};

const SCRAPER_STATUS_TONE: Record<string, Tone> = {
  success: "success",
  partial: "warning",
  failed: "danger",
};

function ScanStatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={SCAN_STATUS_TONE[status] ?? "neutral"} className="capitalize">
      {status}
    </Badge>
  );
}

function ScraperStatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={SCRAPER_STATUS_TONE[status] ?? "neutral"} dot className="capitalize">
      {status}
    </Badge>
  );
}

// ── Scraper run row ───────────────────────────────────────────────────────────

function ScraperRunRow({ run }: { run: ScraperRun }) {
  return (
    <tr className="border-t border-gray-800/60">
      <td className="py-2 pr-3 pl-4">
        <span className="text-gray-300 text-sm font-medium">{sourceLabel(run.source)}</span>
      </td>
      <td className="py-2 pr-3">
        <ScraperStatusBadge status={run.status} />
      </td>
      <td className="py-2 pr-3 text-gray-400 text-sm tabular-nums">{formatDuration(run.duration_ms)}</td>
      <td className="py-2 pr-3 text-gray-300 text-sm tabular-nums">{run.jobs_found}</td>
      <td className="py-2 pr-3 text-green-400 text-sm tabular-nums">{run.jobs_inserted}</td>
      <td className="py-2 pr-3 text-gray-500 text-sm tabular-nums">{run.duplicates_skipped}</td>
      <td className="py-2 pr-3">
        {run.errors ? (
          <span className="text-red-400 text-xs truncate max-w-xs block" title={run.errors}>
            {run.errors.length > 60 ? run.errors.slice(0, 60) + "…" : run.errors}
          </span>
        ) : (
          <span className="text-gray-700 text-xs">—</span>
        )}
      </td>
    </tr>
  );
}

// ── Scan card ─────────────────────────────────────────────────────────────────

function ScanCard({ scan }: { scan: Scan }) {
  const [expanded, setExpanded] = useState(false);
  const hasRuns = scan.scraper_runs.length > 0;
  const failedCount = scan.scraper_runs.filter((r) => r.status === "failed").length;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      {/* Header row */}
      <button
        type="button"
        onClick={() => hasRuns && setExpanded((v) => !v)}
        className={`w-full text-left px-5 py-4 flex items-center gap-4 flex-wrap transition-colors ${
          hasRuns ? "hover:bg-gray-800/40 cursor-pointer" : "cursor-default"
        }`}
      >
        {/* Status */}
        <div className="flex-none">
          <ScanStatusBadge status={scan.status} />
        </div>

        {/* Timestamps */}
        <div className="flex-1 min-w-0">
          <span
            className="text-white text-sm font-medium"
            title={formatDate(scan.started_at)}
          >
            {formatRelativeTime(scan.started_at)}
          </span>
          {scan.completed_at && (
            <span className="text-gray-600 text-xs ml-2" title={formatDate(scan.completed_at)}>
              → {formatRelativeTime(scan.completed_at)}
            </span>
          )}
        </div>

        {/* Metrics */}
        <div className="flex items-center gap-5 flex-wrap text-sm">
          <MetricPill label="Duration" value={formatDuration(scan.duration_ms)} />
          <MetricPill label="Found" value={scan.jobs_found} />
          <MetricPill label="New" value={scan.new_jobs} accent="text-green-400" />
          <MetricPill label="Dupes" value={scan.total_duplicates} accent="text-gray-500" />
          {scan.total_errors > 0 && (
            <MetricPill label="Errors" value={scan.total_errors} accent="text-red-400" />
          )}
        </div>

        {/* Expand chevron */}
        {hasRuns && (
          <ChevronRight
            className={`flex-none w-4 h-4 text-gray-600 transition-transform ${expanded ? "rotate-90" : ""}`}
          />
        )}
      </button>

      {/* Per-scraper breakdown */}
      {expanded && hasRuns && (
        <div className="border-t border-gray-800 bg-gray-950/50">
          {failedCount > 0 && (
            <div className="px-5 py-2 flex items-center gap-2">
              <span className="text-red-400 text-xs">
                {failedCount} scraper{failedCount !== 1 ? "s" : ""} failed — remaining scrapers completed successfully.
              </span>
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px]">
              <thead>
                <tr className="border-b border-gray-800/60">
                  {["Scraper", "Status", "Duration", "Found", "Inserted", "Dupes", "Error"].map(
                    (h) => (
                      <th
                        key={h}
                        className="text-left text-xs text-gray-600 uppercase tracking-wide py-2 pr-3 pl-4 first:pl-4 font-medium"
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {scan.scraper_runs.map((run) => (
                  <ScraperRunRow key={run.id} run={run} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricPill({
  label,
  value,
  accent = "text-white",
}: {
  label: string;
  value: string | number;
  accent?: string;
}) {
  return (
    <div className="flex flex-col items-end">
      <span className={`font-semibold tabular-nums ${accent}`}>{value}</span>
      <span className="text-gray-600 text-[10px] uppercase tracking-wide">{label}</span>
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function SkeletonScanCard() {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-center gap-4 animate-pulse">
      <div className="h-5 w-20 bg-gray-800 rounded-full" />
      <div className="flex-1 h-4 bg-gray-800 rounded w-32" />
      <div className="h-4 bg-gray-800 rounded w-16" />
      <div className="h-4 bg-gray-800 rounded w-12" />
      <div className="h-4 bg-gray-800 rounded w-10" />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ScanHistoryPage() {
  const {
    data: scans = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["scans"],
    queryFn: api.scans,
    refetchInterval: 15_000,
  });

  const running = scans.filter((s) => s.status === "running");

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-white">Scan History</h1>
        <p className="text-gray-500 text-sm mt-1">
          {isLoading
            ? "Loading…"
            : scans.length === 0
            ? "No scans yet — trigger one from the Jobs page."
            : `${scans.length} scan${scans.length !== 1 ? "s" : ""} · click any row to expand per-scraper details`}
        </p>
      </header>

      {running.length > 0 && (
        <div className="mb-4">
          <Badge tone="warning" dot pulse>
            {running.length === 1 ? "A scan is running…" : `${running.length} scans running…`}
          </Badge>
        </div>
      )}

      {isLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <SkeletonScanCard key={i} />
          ))}
        </div>
      ) : isError ? (
        <ErrorBanner
          title="Couldn't load scan history"
          message={error instanceof Error ? error.message : undefined}
          onRetry={() => refetch()}
        />
      ) : scans.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 border-dashed rounded-xl p-10 text-center">
          <History className="w-9 h-9 text-gray-700 mx-auto mb-3" strokeWidth={1.5} />
          <p className="text-gray-400 font-medium">No scan history yet</p>
          <p className="text-gray-600 text-sm mt-1">
            Trigger a scan from the Jobs page to see activity here.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {scans.map((scan) => (
            <ScanCard key={scan.id} scan={scan} />
          ))}
        </div>
      )}
    </div>
  );
}
