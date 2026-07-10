import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Resume } from "../api/client";
import { useToast } from "../hooks/useToast";
import { ErrorBanner, errorMessage, formatDate } from "../shared";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Upload form ───────────────────────────────────────────────────────────────

function UploadForm({ onUploaded }: { onUploaded: (resume: Resume) => void }) {
  const qc = useQueryClient();
  const { push } = useToast();
  const [filename, setFilename] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadResume(file, filename || undefined),
    onSuccess: (resume) => {
      qc.invalidateQueries({ queryKey: ["resumes"] });
      push(`"${resume.filename}" uploaded.`, "success");
      setFilename("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      onUploaded(resume);
    },
    onError: (err) => push(`Upload failed: ${errorMessage(err)}`, "error"),
  });

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
      <h3 className="text-white font-medium mb-3">Upload Resume</h3>
      <div className="flex flex-wrap gap-3 items-end">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">
            Name (optional)
          </label>
          <input
            type="text"
            value={filename}
            onChange={(e) => setFilename(e.target.value)}
            placeholder="e.g. ATS Resume"
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500 transition-colors"
          />
        </div>
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadMutation.mutate(file);
            }}
            disabled={uploadMutation.isPending}
            className="text-sm text-gray-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-600 file:text-white hover:file:bg-blue-500 file:cursor-pointer file:transition-colors disabled:opacity-50"
          />
        </div>
      </div>
      {uploadMutation.isPending && <p className="text-xs text-gray-500 mt-3">Uploading…</p>}
      <p className="text-xs text-gray-600 mt-3">PDF or DOCX, up to 10MB.</p>
    </div>
  );
}

// ── Resume card ───────────────────────────────────────────────────────────────

interface ResumeCardProps {
  resume: Resume;
  featured?: boolean;
  onActivate: () => void;
  onDelete: () => void;
  onRename: (name: string) => void;
  onReplace: (file: File) => void;
  replacing: boolean;
}

function ResumeCard({ resume, featured, onActivate, onDelete, onRename, onReplace, replacing }: ResumeCardProps) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(resume.filename);
  const replaceInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => setName(resume.filename), [resume.filename]);

  return (
    <div
      className={`bg-gray-900 border rounded-lg p-5 ${
        featured ? "border-green-800/60" : "border-gray-800"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          {renaming ? (
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => {
                setRenaming(false);
                if (name.trim() && name !== resume.filename) onRename(name.trim());
              }}
              onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
              className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-white focus:outline-none focus:border-blue-500"
            />
          ) : (
            <h3 className="text-white font-medium text-lg truncate">{resume.filename}</h3>
          )}
          <p className="text-gray-500 text-xs truncate mt-0.5">{resume.original_filename}</p>
        </div>
        {resume.is_active && (
          <span className="flex-none inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium bg-green-900/50 text-green-300 ring-1 ring-green-800/50">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
            Active
          </span>
        )}
      </div>

      <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
        <span>
          Uploaded: <span className="text-gray-400">{formatDate(resume.uploaded_at)}</span>
        </span>
        <span>
          Size: <span className="text-gray-400">{formatFileSize(resume.file_size)}</span>
        </span>
        <span className="uppercase text-gray-600">{resume.file_type}</span>
      </div>

      <div className="flex items-center gap-2 mt-4 flex-wrap">
        <a
          href={api.resumePreviewUrl(resume.id)}
          target="_blank"
          rel="noreferrer"
          className="text-xs px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 transition-colors"
        >
          Preview
        </a>
        <a
          href={api.resumeDownloadUrl(resume.id)}
          className="text-xs px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 transition-colors"
        >
          Download
        </a>
        <button
          onClick={() => replaceInputRef.current?.click()}
          disabled={replacing}
          className="text-xs px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 transition-colors disabled:opacity-50"
        >
          {replacing ? "Replacing…" : "Replace"}
        </button>
        <input
          ref={replaceInputRef}
          type="file"
          accept=".pdf,.docx"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onReplace(file);
            e.target.value = "";
          }}
        />
        {!resume.is_active && (
          <button
            onClick={onActivate}
            className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors"
          >
            Set Active
          </button>
        )}
        <button
          onClick={() => setRenaming(true)}
          className="text-xs px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 transition-colors"
        >
          Rename
        </button>
        <button
          onClick={onDelete}
          className="text-xs px-3 py-1.5 rounded-lg text-gray-500 hover:text-red-400 transition-colors ml-auto"
        >
          Delete
        </button>
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function ResumePage() {
  const qc = useQueryClient();
  const { push } = useToast();
  const [replacingId, setReplacingId] = useState<number | null>(null);

  const { data: resumes = [], isLoading, isError, error, refetch } = useQuery({
    queryKey: ["resumes"],
    queryFn: api.resumes,
  });

  const activateMutation = useMutation({
    mutationFn: (id: number) => api.activateResume(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["resumes"] });
      push("Active resume updated", "success");
    },
    onError: (err) => push(`Couldn't set active resume: ${errorMessage(err)}`, "error"),
  });

  const renameMutation = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) => api.patchResume(id, { filename: name }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["resumes"] }),
    onError: (err) => push(`Couldn't rename resume: ${errorMessage(err)}`, "error"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteResume(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["resumes"] });
      push("Resume deleted", "success");
    },
    onError: (err) => push(`Couldn't delete resume: ${errorMessage(err)}`, "error"),
  });

  const replaceMutation = useMutation({
    mutationFn: ({ id, file }: { id: number; file: File }) => api.replaceResume(id, file),
    onMutate: ({ id }) => setReplacingId(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["resumes"] });
      push("Resume replaced", "success");
    },
    onError: (err) => push(`Couldn't replace resume: ${errorMessage(err)}`, "error"),
    onSettled: () => setReplacingId(null),
  });

  const active = resumes.find((r) => r.is_active);
  const others = resumes.filter((r) => !r.is_active);

  const cardActions = (resume: Resume) => ({
    onActivate: () => activateMutation.mutate(resume.id),
    onDelete: () => {
      if (window.confirm(`Delete "${resume.filename}"? This can't be undone.`)) {
        deleteMutation.mutate(resume.id);
      }
    },
    onRename: (name: string) => renameMutation.mutate({ id: resume.id, name }),
    onReplace: (file: File) => replaceMutation.mutate({ id: resume.id, file }),
    replacing: replacingId === resume.id,
  });

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-white">Resume Vault</h2>
        <p className="text-gray-500 text-sm mt-0.5">
          {resumes.length} {resumes.length === 1 ? "resume" : "resumes"} stored. Kiwi keeps the original
          document — no parsing, no AI.
        </p>
      </div>

      <div className="mb-5">
        <UploadForm onUploaded={() => {}} />
      </div>

      {isLoading ? (
        <p className="text-gray-500 text-sm">Loading…</p>
      ) : isError ? (
        <ErrorBanner title="Couldn't load resumes" message={errorMessage(error)} onRetry={() => refetch()} />
      ) : resumes.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
          <p className="text-gray-500 text-sm">No resumes yet. Upload one above to get started.</p>
        </div>
      ) : (
        <div className="space-y-6">
          <div>
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-2">Active Resume</h3>
            {active ? (
              <ResumeCard resume={active} featured {...cardActions(active)} />
            ) : (
              <div className="bg-gray-900 border border-gray-800 border-dashed rounded-lg p-6 text-center">
                <p className="text-gray-500 text-sm">
                  No active resume set. Click "Set Active" on a resume below.
                </p>
              </div>
            )}
          </div>

          {others.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-2">Other Resumes</h3>
              <div className="space-y-3">
                {others.map((resume) => (
                  <ResumeCard key={resume.id} resume={resume} {...cardActions(resume)} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
