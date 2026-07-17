import type { ReactNode } from "react";

// Surface — the shared card-tier convention. Every content block in the app
// used to render with the exact same weight (bg-gray-900/border-gray-800),
// which made a page of six unrelated cards look like one undifferentiated
// stack. `secondary` is that same existing recipe, unchanged, so anything
// not explicitly promoted stays pixel-identical to before. `primary` is a
// deliberately subtle lift (a hairline lighter border + soft ring/shadow —
// not a color change) reserved for the one or two surfaces per page that
// should read as "the main point": a decision hero, a launch CTA, a score.

export type SurfaceTier = "primary" | "secondary";

const TIER_CLASSES: Record<SurfaceTier, string> = {
  primary: "bg-gray-900 border border-gray-700/80 ring-1 ring-white/[0.03] shadow-lg shadow-black/20",
  secondary: "bg-gray-900 border border-gray-800",
};

export function Surface({
  tier = "secondary",
  className = "",
  children,
}: {
  tier?: SurfaceTier;
  className?: string;
  children: ReactNode;
}) {
  return <div className={`rounded-xl p-5 ${TIER_CLASSES[tier]} ${className}`}>{children}</div>;
}

/** The small uppercase "eyebrow" label used to title a card's content
 * (e.g. "Quick Facts," "Why This Job") — already a de facto convention
 * across the app; centralized here so it stays consistent. */
export function SectionLabel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <p className={`text-xs font-semibold text-gray-500 uppercase tracking-wide ${className}`}>{children}</p>
  );
}
