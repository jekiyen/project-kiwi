import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type EducationEntry,
  type ExperienceEntry,
  type Resume,
} from "../api/client";
import { useToast } from "../hooks/useToast";
import { ErrorBanner, errorMessage, formatDate } from "../shared";

// ── Badges ────────────────────────────────────────────────────────────────────

function ActiveBadge({ active }: { active: boolean }) {
  if (!active) return null;
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium bg-green-900/50 text-green-300 ring-1 ring-green-800/50">
      <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
      Active
    </span>
  );
}

const PARSE_STATUS_STYLES: Record<string, string> = {
  parsed: "bg-green-900/40 text-green-400",
  pending: "bg-yellow-900/40 text-yellow-400",
  failed: "bg-red-900/40 text-red-400",
};

function ParseStatusBadge({ status }: { status: string }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium capitalize ${PARSE_STATUS_STYLES[status] ?? "bg-gray-800 text-gray-400"}`}>
      {status}
    </span>
  );
}

// ── Upload form ───────────────────────────────────────────────────────────────

function UploadForm({ onUploaded }: { onUploaded: (resume: Resume) => void }) {
  const qc = useQueryClient();
  const { push } = useToast();
  const [versionName, setVersionName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadResume(file, versionName || undefined),
    onSuccess: (resume) => {
      qc.invalidateQueries({ queryKey: ["resumes"] });
      const status = resume.parse_status === "failed" ? "info" : "success";
      push(
        resume.parse_status === "failed"
          ? `Uploaded, but parsing failed: ${resume.parse_error ?? "unknown error"}`
          : `"${resume.version_name}" uploaded and parsed.`,
        status,
      );
      setVersionName("");
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
            Version Name (optional)
          </label>
          <input
            type="text"
            value={versionName}
            onChange={(e) => setVersionName(e.target.value)}
            placeholder="e.g. Warehouse Application v2"
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
      {uploadMutation.isPending && (
        <p className="text-xs text-gray-500 mt-3">Uploading and parsing…</p>
      )}
      <p className="text-xs text-gray-600 mt-3">PDF or DOCX, up to 10MB.</p>
    </div>
  );
}

// ── Resume card ───────────────────────────────────────────────────────────────

interface ResumeCardProps {
  resume: Resume;
  selected: boolean;
  onSelect: () => void;
  onActivate: () => void;
  onDelete: () => void;
  onRename: (name: string) => void;
}

function ResumeCard({ resume, selected, onSelect, onActivate, onDelete, onRename }: ResumeCardProps) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(resume.version_name);

  useEffect(() => setName(resume.version_name), [resume.version_name]);

  return (
    <div
      onClick={onSelect}
      className={`bg-gray-900 border rounded-lg p-4 cursor-pointer transition-colors ${
        selected ? "border-blue-600" : "border-gray-800 hover:border-gray-700"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          {renaming ? (
            <input
              autoFocus
              value={name}
              onClick={(e) => e.stopPropagation()}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => {
                setRenaming(false);
                if (name.trim() && name !== resume.version_name) onRename(name.trim());
              }}
              onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
              className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500"
            />
          ) : (
            <h3 className="text-white font-medium truncate">{resume.version_name}</h3>
          )}
          <p className="text-gray-500 text-xs truncate mt-0.5">{resume.original_filename}</p>
        </div>
        <ActiveBadge active={resume.is_active} />
      </div>

      <div className="flex items-center gap-2 mt-2">
        <ParseStatusBadge status={resume.parse_status} />
        <span className="text-xs text-gray-600">{formatDate(resume.uploaded_at)}</span>
      </div>

      <div className="flex items-center gap-3 mt-3 text-xs">
        {!resume.is_active && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onActivate();
            }}
            className="text-blue-400 hover:text-blue-300 transition-colors"
          >
            Set Active
          </button>
        )}
        <button
          onClick={(e) => {
            e.stopPropagation();
            setRenaming(true);
          }}
          className="text-gray-400 hover:text-gray-200 transition-colors"
        >
          Rename
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="text-gray-600 hover:text-red-400 transition-colors ml-auto"
        >
          Delete
        </button>
      </div>
    </div>
  );
}

// ── Detail — profile fields ──────────────────────────────────────────────────

function ProfileField({
  label,
  value,
  onSave,
}: {
  label: string;
  value: string | null;
  onSave: (value: string) => void;
}) {
  const [text, setText] = useState(value ?? "");
  useEffect(() => setText(value ?? ""), [value]);
  return (
    <div>
      <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</label>
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => {
          if (text !== (value ?? "")) onSave(text);
        }}
        placeholder="Not detected"
        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500 transition-colors"
      />
    </div>
  );
}

function ListField({
  label,
  values,
  onSave,
}: {
  label: string;
  values: string[];
  onSave: (values: string[]) => void;
}) {
  const [text, setText] = useState(values.join(", "));
  useEffect(() => setText(values.join(", ")), [values]);
  return (
    <div>
      <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</label>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => {
          const next = text.split(",").map((s) => s.trim()).filter(Boolean);
          if (JSON.stringify(next) !== JSON.stringify(values)) onSave(next);
        }}
        placeholder="Comma-separated"
        rows={2}
        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 resize-none focus:outline-none focus:border-gray-500 transition-colors"
      />
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {values.map((v) => (
            <span key={v} className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-300">
              {v}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Detail — experience / education editor ──────────────────────────────────

function ExperienceEditor({
  entries,
  onSave,
}: {
  entries: ExperienceEntry[];
  onSave: (entries: ExperienceEntry[]) => void;
}) {
  const [items, setItems] = useState(entries);
  useEffect(() => setItems(entries), [entries]);

  const update = (i: number, patch: Partial<ExperienceEntry>) => {
    setItems((prev) => prev.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));
  };

  return (
    <div className="space-y-3">
      {items.map((item, i) => (
        <div key={i} className="bg-gray-800/60 border border-gray-700 rounded p-3 space-y-2">
          <div className="flex flex-wrap gap-2">
            <input
              value={item.title}
              onChange={(e) => update(i, { title: e.target.value })}
              placeholder="Title"
              className="flex-1 min-w-[140px] bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500"
            />
            <input
              value={item.company}
              onChange={(e) => update(i, { company: e.target.value })}
              placeholder="Company"
              className="flex-1 min-w-[140px] bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500"
            />
            <input
              value={item.dates}
              onChange={(e) => update(i, { dates: e.target.value })}
              placeholder="Dates"
              className="w-32 bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500"
            />
          </div>
          <textarea
            value={item.description}
            onChange={(e) => update(i, { description: e.target.value })}
            placeholder="Description"
            rows={2}
            className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 placeholder-gray-600 resize-none focus:outline-none focus:border-gray-500"
          />
          <button
            onClick={() => setItems((prev) => prev.filter((_, idx) => idx !== i))}
            className="text-xs text-gray-600 hover:text-red-400 transition-colors"
          >
            Remove
          </button>
        </div>
      ))}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setItems((prev) => [...prev, { title: "", company: "", dates: "", description: "" }])}
          className="text-xs text-gray-400 hover:text-gray-200 border border-gray-700 rounded px-3 py-1.5 transition-colors"
        >
          + Add Experience
        </button>
        <button
          onClick={() => onSave(items)}
          className="text-xs bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-1.5 transition-colors"
        >
          Save Experience
        </button>
      </div>
    </div>
  );
}

function EducationEditor({
  entries,
  onSave,
}: {
  entries: EducationEntry[];
  onSave: (entries: EducationEntry[]) => void;
}) {
  const [items, setItems] = useState(entries);
  useEffect(() => setItems(entries), [entries]);

  const update = (i: number, patch: Partial<EducationEntry>) => {
    setItems((prev) => prev.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));
  };

  return (
    <div className="space-y-3">
      {items.map((item, i) => (
        <div key={i} className="bg-gray-800/60 border border-gray-700 rounded p-3 flex flex-wrap gap-2 items-start">
          <input
            value={item.institution}
            onChange={(e) => update(i, { institution: e.target.value })}
            placeholder="Institution"
            className="flex-1 min-w-[140px] bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500"
          />
          <input
            value={item.qualification}
            onChange={(e) => update(i, { qualification: e.target.value })}
            placeholder="Qualification"
            className="flex-1 min-w-[140px] bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500"
          />
          <input
            value={item.dates}
            onChange={(e) => update(i, { dates: e.target.value })}
            placeholder="Dates"
            className="w-32 bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500"
          />
          <button
            onClick={() => setItems((prev) => prev.filter((_, idx) => idx !== i))}
            className="text-xs text-gray-600 hover:text-red-400 transition-colors"
          >
            Remove
          </button>
        </div>
      ))}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setItems((prev) => [...prev, { institution: "", qualification: "", dates: "" }])}
          className="text-xs text-gray-400 hover:text-gray-200 border border-gray-700 rounded px-3 py-1.5 transition-colors"
        >
          + Add Education
        </button>
        <button
          onClick={() => onSave(items)}
          className="text-xs bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-1.5 transition-colors"
        >
          Save Education
        </button>
      </div>
    </div>
  );
}

// ── Detail panel ──────────────────────────────────────────────────────────────

function ResumeDetail({ resume }: { resume: Resume }) {
  const qc = useQueryClient();
  const { push } = useToast();

  const patchMutation = useMutation({
    mutationFn: (body: Parameters<typeof api.patchResume>[1]) => api.patchResume(resume.id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["resumes"] });
      push("Saved", "success");
    },
    onError: (err) => push(`Couldn't save changes: ${errorMessage(err)}`, "error"),
  });

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-medium">Parsed Profile</h3>
        {resume.parse_status === "failed" && (
          <span className="text-xs text-red-400">{resume.parse_error}</span>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <ProfileField label="Name" value={resume.parsed_name} onSave={(v) => patchMutation.mutate({ parsed_name: v })} />
        <ProfileField label="Email" value={resume.parsed_email} onSave={(v) => patchMutation.mutate({ parsed_email: v })} />
        <ProfileField label="Phone" value={resume.parsed_phone} onSave={(v) => patchMutation.mutate({ parsed_phone: v })} />
        <ProfileField label="LinkedIn" value={resume.parsed_linkedin} onSave={(v) => patchMutation.mutate({ parsed_linkedin: v })} />
        <ProfileField label="Portfolio" value={resume.parsed_portfolio} onSave={(v) => patchMutation.mutate({ parsed_portfolio: v })} />
      </div>

      <div className="mt-4">
        <ListField label="Skills" values={resume.parsed_skills} onSave={(v) => patchMutation.mutate({ parsed_skills: v })} />
      </div>

      <div className="mt-5">
        <h4 className="text-white font-medium text-sm mb-2">Experience</h4>
        <ExperienceEditor
          entries={resume.parsed_experience}
          onSave={(v) => patchMutation.mutate({ parsed_experience: v })}
        />
      </div>

      <div className="mt-5">
        <h4 className="text-white font-medium text-sm mb-2">Education</h4>
        <EducationEditor
          entries={resume.parsed_education}
          onSave={(v) => patchMutation.mutate({ parsed_education: v })}
        />
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function ResumePage() {
  const qc = useQueryClient();
  const { push } = useToast();
  const [selectedId, setSelectedId] = useState<number | null>(null);

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
    mutationFn: ({ id, name }: { id: number; name: string }) => api.patchResume(id, { version_name: name }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["resumes"] }),
    onError: (err) => push(`Couldn't rename resume: ${errorMessage(err)}`, "error"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteResume(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ["resumes"] });
      setSelectedId((prev) => (prev === id ? null : prev));
      push("Resume deleted", "success");
    },
    onError: (err) => push(`Couldn't delete resume: ${errorMessage(err)}`, "error"),
  });

  const selected = resumes.find((r) => r.id === selectedId) ?? resumes.find((r) => r.is_active) ?? resumes[0];

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-white">Resume</h2>
        <p className="text-gray-500 text-sm mt-0.5">
          {resumes.length} {resumes.length === 1 ? "resume" : "resumes"} · manage versions and parsed profile data.
        </p>
      </div>

      <div className="mb-5">
        <UploadForm onUploaded={(resume) => setSelectedId(resume.id)} />
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
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 content-start">
            {resumes.map((resume) => (
              <ResumeCard
                key={resume.id}
                resume={resume}
                selected={resume.id === selected?.id}
                onSelect={() => setSelectedId(resume.id)}
                onActivate={() => activateMutation.mutate(resume.id)}
                onDelete={() => {
                  if (window.confirm(`Delete "${resume.version_name}"? This can't be undone.`)) {
                    deleteMutation.mutate(resume.id);
                  }
                }}
                onRename={(name) => renameMutation.mutate({ id: resume.id, name })}
              />
            ))}
          </div>

          <div>{selected && <ResumeDetail key={selected.id} resume={selected} />}</div>
        </div>
      )}
    </div>
  );
}
