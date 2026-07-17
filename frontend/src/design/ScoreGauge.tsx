import { TONE_BAR_CLASSES, TONE_STROKE_CLASSES, TONE_TEXT_CLASSES, scoreTone, type Tone } from "./tokens";

// ScoreGauge — the one radial score visualization used everywhere a 0-100
// score appears (Job Discovery cards, Job Intelligence, Application
// Readiness). Replaces three previously-separate plain-number renderings
// with a single reusable component, so "72" always looks the same
// everywhere in the app.

const SIZE_PX: Record<"sm" | "md" | "lg", number> = { sm: 56, md: 88, lg: 112 };
const STROKE_WIDTH: Record<"sm" | "md" | "lg", number> = { sm: 5, md: 7, lg: 8 };
const NUMBER_TEXT_SIZE: Record<"sm" | "md" | "lg", string> = {
  sm: "text-base",
  md: "text-2xl",
  lg: "text-3xl",
};

export function ScoreGauge({
  score,
  size = "md",
  caption,
}: {
  /** 0-100, or null for a job that hasn't been scored yet. */
  score: number | null;
  size?: "sm" | "md" | "lg";
  /** Small uppercase label rendered below the ring, e.g. "Match" or "Readiness". */
  caption?: string;
}) {
  const px = SIZE_PX[size];
  const strokeWidth = STROKE_WIDTH[size];
  const radius = (px - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = score === null ? 0 : Math.max(0, Math.min(100, score));
  const dashOffset = circumference * (1 - clamped / 100);
  const tone: Tone = score === null ? "neutral" : scoreTone(clamped);

  return (
    <div className="inline-flex flex-col items-center">
      <div className="relative" style={{ width: px, height: px }}>
        <svg width={px} height={px} className="-rotate-90">
          <circle
            cx={px / 2}
            cy={px / 2}
            r={radius}
            strokeWidth={strokeWidth}
            fill="none"
            className="stroke-gray-800"
          />
          {score !== null && (
            <circle
              cx={px / 2}
              cy={px / 2}
              r={radius}
              strokeWidth={strokeWidth}
              fill="none"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              strokeLinecap="round"
              className={`transition-[stroke-dashoffset] duration-500 ${TONE_STROKE_CLASSES[tone]}`}
            />
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {score !== null ? (
            <>
              <span className={`font-bold leading-none ${NUMBER_TEXT_SIZE[size]} ${TONE_TEXT_CLASSES[tone]}`}>
                {Math.round(score)}
              </span>
              {size !== "sm" && <span className="text-[10px] text-gray-600 mt-0.5">/100</span>}
            </>
          ) : (
            <span className="text-[10px] text-gray-500 text-center px-1.5 leading-tight">Unscored</span>
          )}
        </div>
      </div>
      {caption && (
        <span className="mt-1.5 text-[10px] text-gray-500 uppercase tracking-wide">{caption}</span>
      )}
    </div>
  );
}

// ProgressBar — a thin linear progress track for "X of Y ready" style
// readouts (Application Kit's section checklist, Application Profile
// completeness). Deliberately simpler than ScoreGauge — a supporting
// visualization, not a second hero metric.

export function ProgressBar({
  value,
  max,
  tone = "brand",
  className = "",
}: {
  value: number;
  max: number;
  tone?: Tone;
  className?: string;
}) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div
      className={`w-full h-1.5 bg-gray-800 rounded-full overflow-hidden ${className}`}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
    >
      <div
        className={`h-full rounded-full transition-[width] duration-500 ${TONE_BAR_CLASSES[tone]}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
