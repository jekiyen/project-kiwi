import { useEffect, useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import { useToast } from "../hooks/useToast";
import { buttonClasses } from "../design/tokens";

const CLAUDE_NEW_CHAT_URL = "https://claude.ai/new";

interface PromptPreviewModalProps {
  title: string;
  content: string;
  disclaimer?: string | null;
  onClose: () => void;
}

// Displays a rendered prompt for the user to copy and paste into Claude by
// hand. Kiwi never talks to an AI provider directly — see docs/ROADMAP.md
// Phase 7.4. The optional disclaimer (Phase 7.5 — AI Readiness) surfaces
// when the prompt was generated with incomplete job data.
export default function PromptPreviewModal({ title, content, disclaimer, onClose }: PromptPreviewModalProps) {
  const { push } = useToast();
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      push("Prompt copied to clipboard", "success");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      push("Couldn't copy — select and copy the text manually", "error");
    }
  };

  const handleOpenClaude = () => {
    window.open(CLAUDE_NEW_CHAT_URL, "_blank", "noreferrer");
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="bg-gray-900 border border-gray-800 rounded-xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <h2 className="text-white font-medium">{title}</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {disclaimer && (
            <div className="flex items-start gap-2 bg-amber-950/30 border border-amber-900/50 rounded-lg px-3 py-2 mb-4">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500 flex-none mt-0.5" />
              <p className="text-amber-200/90 text-xs leading-relaxed">{disclaimer}</p>
            </div>
          )}
          <pre className="whitespace-pre-wrap break-words text-sm text-gray-300 font-sans leading-relaxed">
            {content}
          </pre>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-gray-800">
          <button onClick={onClose} className={buttonClasses("subtle", "sm")}>
            Cancel
          </button>
          <button onClick={handleCopy} className={buttonClasses("secondary", "sm")}>
            {copied ? "Copied ✓" : "Copy Prompt"}
          </button>
          <button onClick={handleOpenClaude} className={buttonClasses("primary", "sm")}>
            Open Claude →
          </button>
        </div>
      </div>
    </div>
  );
}
