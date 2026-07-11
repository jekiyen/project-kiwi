import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type AIReadiness, type AIReadinessStatus, type Job, type PatchJobBody } from "../api/client";
import { useToast } from "../hooks/useToast";
import { errorMessage } from "../shared";
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
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">{title}</h3>
      {children}
    </section>
  );
}

const READINESS_CONFIG: Record<AIReadinessStatus, { label: string; icon: string; cls: string }> = {
  ready: { label: "Ready", icon: "🟢", cls: "text-green-400" },
  partial: { label: "Partial", icon: "🟡", cls: "text-yellow-400" },
  not_ready: { label: "Not Ready", icon: "🔴", cls: "text-red-400" },
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
        <button
          type="submit"
          disabled={saveMutation.isPending}
          className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium transition-colors"
        >
          {saveMutation.isPending ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={onDone}
          disabled={saveMutation.isPending}
          className="text-xs px-3 py-1.5 rounded-lg border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500 transition-colors"
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
  const cfg = READINESS_CONFIG[readiness.status];
  const needsResume = readiness.missing.includes("Active Resume");
  const needsJobFields = readiness.missing.some((m) => m !== "Active Resume");

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">AI Readiness</p>
        <span className={`inline-flex items-center gap-1.5 text-sm font-medium ${cfg.cls}`}>
          <span>{cfg.icon}</span>
          {cfg.label}
        </span>
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
            <button
              onClick={() => setEditing(true)}
              className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors"
            >
              Edit Job
            </button>
          )}
          {needsResume && (
            <Link
              to="/resume"
              className="text-xs px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 transition-colors"
            >
              Go to Resume Vault
            </Link>
          )}
        </div>
      )}

      {editing && <EditJobForm job={job} onDone={() => setEditing(false)} />}
    </div>
  );
}

// ── Action tiles ─────────────────────────────────────────────────────────────

function ActionTile({
  icon,
  label,
  description,
  onClick,
  loading,
  disabled,
}: {
  icon: string;
  label: string;
  description: string;
  onClick: () => void;
  loading: boolean;
  disabled: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      title={disabled ? "Resolve the missing items above before generating this prompt" : undefined}
      className="text-left bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-600 hover:bg-gray-900/80 transition-colors disabled:opacity-40 disabled:hover:border-gray-800 disabled:hover:bg-gray-900 disabled:cursor-not-allowed"
    >
      <div className="flex items-start gap-3">
        <span className="text-xl leading-none">{icon}</span>
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
                icon={action.icon}
                label={action.label}
                description={action.description}
                onClick={() => handleActionClick(action.id)}
                loading={activeActionId === action.id}
                disabled={notReady || readinessLoading}
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
