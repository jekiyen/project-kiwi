// Design tokens — Project Kiwi Design System (UI/UX Polish workstream).
//
// A small, centralized presentation-layer vocabulary so every badge, gauge,
// and button across the app draws from the same semantic palette instead of
// each screen picking its own colors. Deliberately reuses the exact Tailwind
// color values already in use throughout the app (emerald/blue/amber/red/
// gray) — this is a naming/consolidation layer, not a visual re-theme.
//
// Presentation only: nothing here touches data, routing, or business logic.

export type Tone = "success" | "info" | "warning" | "danger" | "neutral" | "brand";

/** Background + text classes for a filled pill (badges). */
export const TONE_FILL_CLASSES: Record<Tone, string> = {
  success: "bg-emerald-900/50 text-emerald-300",
  info: "bg-blue-900/50 text-blue-300",
  warning: "bg-amber-900/50 text-amber-300",
  danger: "bg-red-900/50 text-red-400",
  neutral: "bg-gray-800 text-gray-400",
  brand: "bg-violet-900/50 text-violet-300",
};

/** Solid dot color per tone — used for live/status indicators inside badges. */
export const TONE_DOT_CLASSES: Record<Tone, string> = {
  success: "bg-emerald-400",
  info: "bg-blue-400",
  warning: "bg-amber-400",
  danger: "bg-red-400",
  neutral: "bg-gray-500",
  brand: "bg-violet-400",
};

/** Text-only color per tone — used for gauge numbers, icons, inline emphasis. */
export const TONE_TEXT_CLASSES: Record<Tone, string> = {
  success: "text-emerald-300",
  info: "text-blue-300",
  warning: "text-amber-300",
  danger: "text-red-400",
  neutral: "text-gray-400",
  brand: "text-violet-300",
};

/** SVG stroke color per tone — used by ScoreGauge's ring. */
export const TONE_STROKE_CLASSES: Record<Tone, string> = {
  success: "stroke-emerald-400",
  info: "stroke-blue-400",
  warning: "stroke-amber-400",
  danger: "stroke-red-400",
  neutral: "stroke-gray-600",
  brand: "stroke-violet-400",
};

/** Progress-bar fill color per tone. */
export const TONE_BAR_CLASSES: Record<Tone, string> = {
  success: "bg-emerald-400",
  info: "bg-blue-400",
  warning: "bg-amber-400",
  danger: "bg-red-400",
  neutral: "bg-gray-500",
  brand: "bg-violet-400",
};

/** The one 0-100 score → tone mapping, reused by every score-driven surface
 * (JobCard, Job Intelligence, Application Readiness) so a "70" always reads
 * as the same color everywhere in the app. */
export function scoreTone(score: number): Tone {
  if (score >= 70) return "success";
  if (score >= 40) return "warning";
  return "danger";
}

export type ButtonVariant = "primary" | "secondary" | "subtle" | "destructive";

const BUTTON_VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: "bg-brand hover:bg-brand-hover text-white shadow-sm shadow-blue-950/40",
  secondary: "border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 bg-transparent",
  subtle: "text-gray-400 hover:text-gray-200 bg-transparent",
  destructive: "text-gray-500 hover:text-red-400 bg-transparent",
};

const BUTTON_SIZE_CLASSES = {
  sm: "text-xs px-3 py-1.5",
  md: "text-sm px-4 py-2",
} as const;

export type ButtonSize = keyof typeof BUTTON_SIZE_CLASSES;

/** Shared class recipe for anything that should look like a button —
 * `<button>`, `<Link>`, or `<a>` alike — so every CTA in the app (regardless
 * of the element it renders as) draws from the same four-variant hierarchy:
 * primary / secondary / subtle / destructive. */
export function buttonClasses(variant: ButtonVariant = "primary", size: ButtonSize = "md"): string {
  return [
    "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors",
    "disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none",
    BUTTON_SIZE_CLASSES[size],
    BUTTON_VARIANT_CLASSES[variant],
  ].join(" ");
}
