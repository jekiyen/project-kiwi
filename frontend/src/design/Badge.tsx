import type { ReactNode } from "react";
import { TONE_DOT_CLASSES, TONE_FILL_CLASSES, type Tone } from "./tokens";

// The single Badge primitive — consolidates what used to be six independent
// status-pill implementations (AppStatusBadge, WorkflowBadge,
// RecommendationBadge, ScanStatusBadge, ScraperStatusBadge, and the
// Notifications page's local status pill), each with its own palette. Every
// status/recommendation indicator in the app now renders through this one
// component; screens only choose a `tone` + optional `dot`.

export function Badge({
  tone = "neutral",
  dot = false,
  pulse = false,
  children,
  className = "",
}: {
  tone?: Tone;
  dot?: boolean;
  pulse?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${TONE_FILL_CLASSES[tone]} ${className}`}
    >
      {dot && (
        <span className={`w-1.5 h-1.5 rounded-full flex-none ${TONE_DOT_CLASSES[tone]} ${pulse ? "animate-pulse" : ""}`} />
      )}
      {children}
    </span>
  );
}
