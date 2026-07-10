import { useEffect, useState } from "react";
import { useToast } from "../hooks/useToast";

const CLAUDE_NEW_CHAT_URL = "https://claude.ai/new";

interface PromptPreviewModalProps {
  title: string;
  content: string;
  onClose: () => void;
}

// Displays a rendered prompt for the user to copy and paste into Claude by
// hand. Kiwi never talks to an AI provider directly — see docs/ROADMAP.md
// Phase 7.4.
export default function PromptPreviewModal({ title, content, onClose }: PromptPreviewModalProps) {
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
            className="text-gray-500 hover:text-gray-300 transition-colors text-lg leading-none"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          <pre className="whitespace-pre-wrap break-words text-sm text-gray-300 font-sans leading-relaxed">
            {content}
          </pre>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-gray-800">
          <button
            onClick={onClose}
            className="text-xs px-3 py-1.5 rounded-lg border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleCopy}
            className="text-xs px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 transition-colors"
          >
            {copied ? "Copied ✓" : "Copy Prompt"}
          </button>
          <button
            onClick={handleOpenClaude}
            className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors"
          >
            Open Claude →
          </button>
        </div>
      </div>
    </div>
  );
}
