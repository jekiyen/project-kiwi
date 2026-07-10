import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Job } from "../api/client";
import { errorMessage } from "../shared";
import PromptPreviewModal from "./PromptPreviewModal";

// The AI Workspace is the foundation every future AI-assisted workflow in
// Kiwi will live in — not a wall of buttons, but a growing set of sections.
// Only "Available AI Actions" is implemented today; future sections (Analysis
// History, Saved AI Results, Visa Guidance, Application Review, ...) plug
// into the same WorkspaceSection wrapper without changing this page's shell.
// See docs/ROADMAP.md Phase 7.4.

function WorkspaceSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">{title}</h3>
      {children}
    </section>
  );
}

function ActionTile({
  icon,
  label,
  description,
  onClick,
  loading,
}: {
  icon: string;
  label: string;
  description: string;
  onClick: () => void;
  loading: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="text-left bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-600 hover:bg-gray-900/80 transition-colors disabled:opacity-50 disabled:cursor-wait"
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

export default function AIWorkspace({ job }: { job: Job }) {
  const [activeActionId, setActiveActionId] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ title: string; content: string } | null>(null);
  const [genError, setGenError] = useState<string | null>(null);

  const {
    data: actions = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["promptActions"],
    queryFn: api.promptActions,
    staleTime: 5 * 60_000,
  });

  const handleActionClick = async (actionId: string) => {
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
      <WorkspaceSection title="Available AI Actions">
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-20 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : isError ? (
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
          onClose={() => setPreview(null)}
        />
      )}
    </div>
  );
}
