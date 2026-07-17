import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  DollarSign,
  FileText,
  Mail,
  Mic,
  PenLine,
  Search,
  Sparkles,
  Target,
  type LucideIcon,
} from "lucide-react";
import { api, type AIReadiness, type AIReadinessStatus, type Job, type PatchJobBody } from "../api/client";
import { useToast } from "../hooks/useToast";
import { errorMessage } from "../shared";
import { Badge } from "../design/Badge";
import { Surface, SectionLabel } from "../design/Surface";
import { buttonClasses, type Tone } from "../design/tokens";
import PromptPreviewModal from "./PromptPreviewModal";

// The AI Workspace is the foundation every future AI-assisted workflow in
// Kiwi will live in — not a wall of buttons, but a growing set of sections.
// Only "Available AI Actions" is implemented today; future sections (Analysis
// History, Saved AI Results, Visa Guidance, Application Review, ...) plug
// into the same WorkspaceSection wrapper without changing this page's shell.
// See docs/ROADMAP.md Phase 7.4.
//
// The AI Readiness card (Phase 7.5) sits above everything else — it's the
// single place that explains why AI output quality may be limited, and
// gates the action tiles below it so a low-quality prompt is never
// generated silently. It reflects the same evaluator the backend's Prompt
// Guard uses (backend/core/ai_readiness.py), so the two can't disagree.

function WorkspaceSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <SectionLabel className="mb-3">{title}</SectionLabel>
      {children}
    </section>
  );
}

const READINESS_TONE: Record<AIReadinessStatus, Tone> = {
  ready: "success",
  partial: "warning",
  not_ready: "danger",
};

const READINESS_LABEL: Record<AIReadinessStatus, string> = {
  ready: "Ready",
  partial: "Partial",
  not_ready: "Not Ready",
};

// A prompt action's icon is chosen here on the frontend rather than trusting
// the emoji string the backend's actions.json config returns — Kiwi's
// registry stays config-driven (no code change needed to add an action),
// but the UI's icon language stays a single consistent set. Unmapped ids
// (e.g. a brand-new action) fall back to a generic sparkle rather than
// breaking.
const ACTION_ICONS: Record<string, LucideIcon> = {
  good_fit: Target,
  resume_analysis: Search,
  resume_improvement: PenLine,
  cover_letter: FileText,
  interview: Mic,
  recruiter_message: Mail,
  salary_negotiation: DollarSign,
};

// ── Inline Edit Job form ─────────────────────────────────────────────────────
// The fast path referenced in the readiness card's "Edit Job" action — no
// modal, no navigating away from the AI Workspace tab.

function EditJobForm({ job, onDone }: { job: Job; onDone: () => void }) {
  const qc = useQueryClient();
  const { push } = useToast();
  const [title, setTitle] = useState(job.title);
  const [employer, setEmployer] = useState(job.employer);
  const [location, setLocation] = useState(job.location);
  const [description, setDescription] = useState(job.description ?? "");

  const saveMutation = useMutation({
    mutationFn: () => {
      const body: PatchJobBody = {};
      if (title !== job.title) body.title = title;
      if (employer !== job.employer) body.employer = employer;
      if (location !== job.location) body.location = location;
      if (description !== (job.description ?? "")) body.description = description;
      return api.patchJob(job.id, body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job", job.id] });
      qc.invalidateQueries({ queryKey: ["aiReadiness", job.id] });
      qc.invalidateQueries({ queryKey: ["jobChanges", job.id] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
      push("Job updated", "success");
      onDone();
    },
    onError: (err) => push(`Couldn't save: ${errorMessage(err)}`, "error"),
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const unchanged =
          title === job.title &&
          employer === job.employer &&
          location === job.location &&
          description === (job.description ?? "");
        if (unchanged) {
          onDone();
          return;
        }
        saveMutation.mutate();
      }}
      className="mt-4 pt-4 border-t border-gray-800 space-y-3"
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">Job Title</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-gray-500 transition-colors"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">Company</label>
          <input
            value={employer}
            onChange={(e) => setEmployer(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-gray-500 transition-colors"
          />
        </div>
      </div>
      <div>
        <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">Location</label>
        <input
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-gray-500 transition-colors"
        />
      </div>
      <div>
        <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">Job Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={5}
          placeholder="Paste the job description here…"
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500 transition-colors resize-y"
        />
      </div>
      <div className="flex items-center gap-2">
        <button type="submit" disabled={saveMutation.isPending} className={buttonClasses("primary", "sm")}>
          {saveMutation.isPending ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={onDone}
          disabled={saveMutation.isPending}
          className={buttonClasses("secondary", "sm")}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

// ── AI Readiness card ────────────────────────────────────────────────────────

function AIReadinessCard({ job, readiness }: { job: Job; readiness: AIReadiness }) {
  const [editing, setEditing] = useState(false);
  const needsResume = readiness.missing.includes("Active Resume");
  const needsJobFields = readiness.missing.some((m) => m !== "Active Resume");

  return (
    <Surface className="p-4">
      <div className="flex items-center justify-between gap-3">
        <SectionLabel>AI Readiness</SectionLabel>
        <Badge tone={READINESS_TONE[readiness.status]} dot>
          {READINESS_LABEL[readiness.status]}
        </Badge>
      </div>

      {readiness.missing.length > 0 && (
        <div className="mt-3">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Missing</p>
          <ul className="text-sm text-gray-300 space-y-0.5">
            {readiness.missing.map((m) => (
              <li key={m}>• {m}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-xs text-gray-500 leading-relaxed mt-3">{readiness.impact}</p>

      {(needsJobFields || needsResume) && !editing && (
        <div className="flex items-center gap-2 mt-3">
          {needsJobFields && (
            <button onClick={() => setEditing(true)} className={buttonClasses("primary", "sm")}>
              Edit Job
            </button>
          )}
          {needsResume && (
            <Link to="/resume" className={buttonClasses("secondary", "sm")}>
              Go to Resume Vault
            </Link>
          )}
        </div>
      )}

      {editing && <EditJobForm job={job} onDone={() => setEditing(false)} />}
    </Surface>
  );
}

// ── Action tiles ─────────────────────────────────────────────────────────────

function ActionTile({
  icon: Icon,
  label,
  description,
  onClick,
  loading,
  disabled,
  recommended,
}: {
  icon: LucideIcon;
  label: string;
  description: string;
  onClick: () => void;
  loading: boolean;
  disabled: boolean;
  recommended?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      title={disabled ? "Resolve the missing items above before generating this prompt" : undefined}
      className={`relative text-left bg-gray-900 rounded-xl p-4 transition-colors disabled:opacity-40 disabled:hover:border-gray-800 disabled:cursor-not-allowed ${
        recommended
          ? "border border-blue-800/60 hover:border-blue-600 ring-1 ring-blue-900/30"
          : "border border-gray-800 hover:border-gray-600 hover:bg-gray-900/80"
      }`}
    >
      {recommended && (
        <span className="absolute top-3 right-3">
          <Badge tone="info">Suggested</Badge>
        </span>
      )}
      <div className="flex items-start gap-3">
        <Icon className="w-5 h-5 text-gray-400 flex-none mt-0.5" strokeWidth={1.75} />
        <div className="min-w-0">
          <p className="text-white text-sm font-medium">{label}</p>
          <p className="text-gray-500 text-xs mt-1 leading-relaxed">{description}</p>
        </div>
      </div>
      {loading && <p className="text-xs text-blue-400 mt-3">Generating prompt…</p>}
    </button>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function AIWorkspace({ job }: { job: Job }) {
  const [activeActionId, setActiveActionId] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ title: string; content: string; disclaimer: string | null } | null>(
    null,
  );
  const [genError, setGenError] = useState<string | null>(null);

  const {
    data: actions = [],
    isLoading: actionsLoading,
    isError: actionsError,
  } = useQuery({
    queryKey: ["promptActions"],
    queryFn: api.promptActions,
    staleTime: 5 * 60_000,
  });

  const {
    data: readiness,
    isLoading: readinessLoading,
    isError: readinessError,
  } = useQuery({
    queryKey: ["aiReadiness", job.id],
    queryFn: () => api.aiReadiness(job.id),
  });

  const notReady = readiness?.status === "not_ready";
  // The one deterministic "what's next" signal Kiwi already tracks: a cover
  // letter prompt that hasn't been generated for this job yet (Phase 8's
  // Job.cover_letter_generated_at). No new AI logic — just surfacing
  // existing state as a suggestion.
  const suggestedActionId = !job.cover_letter_generated_at ? "cover_letter" : null;

  const handleActionClick = async (actionId: string) => {
    if (notReady) return;
    setActiveActionId(actionId);
    setGenError(null);
    try {
      const prompt = await api.generateJobPrompt(job.id, actionId);
      setPreview(prompt);
    } catch (err) {
      setGenError(errorMessage(err));
    } finally {
      setActiveActionId(null);
    }
  };

  return (
    <div className="space-y-6">
      {readinessLoading ? (
        <div className="h-32 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
      ) : readinessError || !readiness ? (
        <p className="text-sm text-red-400">Couldn't load AI Readiness.</p>
      ) : (
        <AIReadinessCard job={job} readiness={readiness} />
      )}

      <WorkspaceSection title="Available AI Actions">
        {actionsLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-20 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : actionsError ? (
          <p className="text-sm text-red-400">Couldn't load AI actions.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {actions.map((action) => (
              <ActionTile
                key={action.id}
                icon={ACTION_ICONS[action.id] ?? Sparkles}
                label={action.label}
                description={action.description}
                onClick={() => handleActionClick(action.id)}
                loading={activeActionId === action.id}
                disabled={notReady || readinessLoading}
                recommended={action.id === suggestedActionId}
              />
            ))}
          </div>
        )}
        {genError && <p className="text-xs text-red-400 mt-3">{genError}</p>}
      </WorkspaceSection>

      {preview && (
        <PromptPreviewModal
          title={preview.title}
          content={preview.content}
          disclaimer={preview.disclaimer}
          onClose={() => setPreview(null)}
        />
      )}
    </div>
  );
}
