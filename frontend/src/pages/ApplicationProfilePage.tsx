import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Car, Globe, Handshake, IdCard } from "lucide-react";
import {
  api,
  type ApplicationProfile,
  type ApplicationProfileUpdate,
  type ApplicationReferenceInput,
} from "../api/client";
import { useToast } from "../hooks/useToast";
import { ErrorBanner, errorMessage, formatDate } from "../shared";
import { ScoreGauge, ProgressBar } from "../design/ScoreGauge";
import { Surface, SectionLabel } from "../design/Surface";
import { buttonClasses, scoreTone } from "../design/tokens";

// The Application Profile is the single source of truth for reusable
// applicant information — the foundation future ATS autofill will read from
// (`application_profile`) without caring where the data came from. It never
// duplicates Resume Vault data; the Resume section here only links to it.
// No AI calls, no generation — a structured, editable, persisted profile.
//
// "Application Readiness Foundation" — a completeness meter at the top ties
// this page back into the same readiness language used in the Application
// Kit (this is a simpler, profile-only completeness check computed from
// what's already loaded here; the full per-job Application Readiness Score
// still lives solely in backend/core/application_readiness.py).

type FormState = Omit<ApplicationProfileUpdate, "references">;

const EMPTY_FORM: FormState = {
  full_name: null,
  preferred_name: null,
  email: null,
  phone: null,
  current_address: null,
  city: null,
  country: null,
  nationality: null,
  work_rights_current_country: null,
  visa_status: null,
  eligible_to_work_nz: false,
  need_sponsorship: false,
  driver_license: false,
  own_vehicle: false,
  linkedin_url: null,
  portfolio_url: null,
  github_url: null,
  website_url: null,
  emergency_contact_name: null,
  emergency_contact_relationship: null,
  emergency_contact_phone: null,
  notes: null,
};

function toFormState(profile: ApplicationProfile): FormState {
  return {
    full_name: profile.full_name,
    preferred_name: profile.preferred_name,
    email: profile.email,
    phone: profile.phone,
    current_address: profile.current_address,
    city: profile.city,
    country: profile.country,
    nationality: profile.nationality,
    work_rights_current_country: profile.work_rights_current_country,
    visa_status: profile.visa_status,
    eligible_to_work_nz: profile.eligible_to_work_nz,
    need_sponsorship: profile.need_sponsorship,
    driver_license: profile.driver_license,
    own_vehicle: profile.own_vehicle,
    linkedin_url: profile.linkedin_url,
    portfolio_url: profile.portfolio_url,
    github_url: profile.github_url,
    website_url: profile.website_url,
    emergency_contact_name: profile.emergency_contact_name,
    emergency_contact_relationship: profile.emergency_contact_relationship,
    emergency_contact_phone: profile.emergency_contact_phone,
    notes: profile.notes,
  };
}

function toReferenceInputs(profile: ApplicationProfile): ApplicationReferenceInput[] {
  return profile.references.map((r) => ({
    name: r.name,
    company: r.company,
    relationship: r.relationship,
    email: r.email,
    phone: r.phone,
  }));
}

// ── Field atoms ───────────────────────────────────────────────────────────────

function TextField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string | null;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</label>
      <input
        type="text"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500 transition-colors"
      />
    </div>
  );
}

function CheckboxField({
  label,
  checked,
  onChange,
  icon: Icon,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  icon: typeof Car;
}) {
  return (
    <label
      className={`flex items-center gap-2.5 text-sm rounded-lg border px-3 py-2.5 cursor-pointer select-none transition-colors ${
        checked ? "border-blue-800/50 bg-blue-950/20 text-gray-200" : "border-gray-800 text-gray-400"
      }`}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="w-4 h-4 rounded border-gray-700 bg-gray-800 text-blue-600 focus:ring-0 focus:ring-offset-0 cursor-pointer"
      />
      <Icon className={`w-4 h-4 flex-none ${checked ? "text-blue-400" : "text-gray-600"}`} strokeWidth={1.75} />
      {label}
    </label>
  );
}

function SectionCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Surface>
      <SectionLabel className="mb-4">{title}</SectionLabel>
      {children}
    </Surface>
  );
}

// ── References ────────────────────────────────────────────────────────────────

function ReferenceRow({
  reference,
  onChange,
  onRemove,
}: {
  reference: ApplicationReferenceInput;
  onChange: (ref: ApplicationReferenceInput) => void;
  onRemove: () => void;
}) {
  return (
    <div className="border border-gray-800 rounded-lg p-4 space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <TextField
          label="Name"
          value={reference.name}
          onChange={(v) => onChange({ ...reference, name: v })}
        />
        <TextField
          label="Company"
          value={reference.company}
          onChange={(v) => onChange({ ...reference, company: v })}
        />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <TextField
          label="Relationship"
          value={reference.relationship}
          onChange={(v) => onChange({ ...reference, relationship: v })}
        />
        <TextField
          label="Email"
          value={reference.email}
          onChange={(v) => onChange({ ...reference, email: v })}
        />
        <TextField
          label="Phone"
          value={reference.phone}
          onChange={(v) => onChange({ ...reference, phone: v })}
        />
      </div>
      <button
        type="button"
        onClick={onRemove}
        className="text-xs text-gray-500 hover:text-red-400 transition-colors"
      >
        Remove reference
      </button>
    </div>
  );
}

// ── Resume Vault shortcut ─────────────────────────────────────────────────────

function ResumeSection() {
  const { data: resumes = [], isLoading } = useQuery({
    queryKey: ["resumes"],
    queryFn: api.resumes,
  });

  const active = resumes.find((r) => r.is_active);

  return (
    <SectionCard title="Resume">
      {isLoading ? (
        <div className="h-10 bg-gray-800 rounded animate-pulse" />
      ) : active ? (
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <p className="text-sm text-gray-200 font-medium">{active.filename}</p>
            <p className="text-xs text-gray-500 mt-0.5">
              {active.file_type.toUpperCase()} · Uploaded {formatDate(active.uploaded_at)}
            </p>
          </div>
          <Link to="/resume" className={buttonClasses("secondary", "sm")}>
            Go to Resume Vault
          </Link>
        </div>
      ) : (
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <p className="text-sm text-gray-500">No active resume set in the Resume Vault.</p>
          <Link to="/resume" className={buttonClasses("primary", "sm")}>
            Go to Resume Vault
          </Link>
        </div>
      )}
    </SectionCard>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function ApplicationProfilePage() {
  const qc = useQueryClient();
  const { push } = useToast();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [references, setReferences] = useState<ApplicationReferenceInput[]>([]);
  const [hydrated, setHydrated] = useState(false);

  const { data: profile, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["applicationProfile"],
    queryFn: api.applicationProfile,
  });

  // Shared with ResumeSection's own query below via the same cache key.
  const { data: resumes = [] } = useQuery({ queryKey: ["resumes"], queryFn: api.resumes });
  const hasActiveResume = resumes.some((r) => r.is_active);

  useEffect(() => {
    if (profile && !hydrated) {
      setForm(toFormState(profile));
      setReferences(toReferenceInputs(profile));
      setHydrated(true);
    }
  }, [profile, hydrated]);

  const saveMutation = useMutation({
    mutationFn: () => api.updateApplicationProfile({ ...form, references }),
    onSuccess: (updated) => {
      qc.setQueryData(["applicationProfile"], updated);
      setForm(toFormState(updated));
      setReferences(toReferenceInputs(updated));
      push("Application Profile saved", "success");
    },
    onError: (err) => push(`Couldn't save: ${errorMessage(err)}`, "error"),
  });

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const completeness = useMemo(() => {
    const checks = [
      !!(form.full_name && form.email && form.phone),
      !!(form.visa_status || form.work_rights_current_country),
      !!(form.linkedin_url || form.portfolio_url || form.github_url || form.website_url),
      hasActiveResume,
      references.length > 0,
      !!form.emergency_contact_name,
    ];
    return { count: checks.filter(Boolean).length, total: checks.length };
  }, [form, references, hasActiveResume]);

  if (isLoading) {
    return (
      <div className="p-6 max-w-4xl mx-auto space-y-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-40 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (isError || !profile) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <ErrorBanner
          title="Couldn't load Application Profile"
          message={errorMessage(error)}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const completenessScore = Math.round((completeness.count / completeness.total) * 100);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div>
          <h2 className="text-xl font-bold text-white">Application Profile</h2>
          <p className="text-gray-500 text-sm mt-0.5">
            The single source of truth for information reused across job applications.
          </p>
        </div>
        <button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          className={buttonClasses("primary")}
        >
          {saveMutation.isPending ? "Saving…" : "Save Profile"}
        </button>
      </div>

      <Surface tier="primary" className="mb-5">
        <div className="flex items-start gap-5 flex-wrap">
          <ScoreGauge score={completenessScore} size="md" caption="Complete" />
          <div className="flex-1 min-w-[220px]">
            <SectionLabel>
              {completeness.count} of {completeness.total} sections complete
            </SectionLabel>
            <ProgressBar
              value={completeness.count}
              max={completeness.total}
              tone={scoreTone(completenessScore)}
              className="mt-2"
            />
            <p className="text-xs text-gray-500 mt-3 leading-relaxed">
              This profile feeds the Application Readiness Score shown in every job's Application Kit —
              the more complete it is, the faster you can launch new applications.
            </p>
          </div>
        </div>
      </Surface>

      <div className="space-y-5">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
          <SectionCard title="Personal Information">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <TextField label="Full Name" value={form.full_name} onChange={(v) => set("full_name", v)} />
              <TextField label="Preferred Name" value={form.preferred_name} onChange={(v) => set("preferred_name", v)} />
              <TextField label="Email" value={form.email} onChange={(v) => set("email", v)} />
              <TextField label="Phone" value={form.phone} onChange={(v) => set("phone", v)} />
              <TextField
                label="Current Address"
                value={form.current_address}
                onChange={(v) => set("current_address", v)}
              />
              <TextField label="City" value={form.city} onChange={(v) => set("city", v)} />
              <TextField label="Country" value={form.country} onChange={(v) => set("country", v)} />
              <TextField label="Nationality" value={form.nationality} onChange={(v) => set("nationality", v)} />
            </div>
          </SectionCard>

          <SectionCard title="Work Rights">
            <div className="grid grid-cols-1 gap-3 mb-4">
              <TextField
                label="Current Country"
                value={form.work_rights_current_country}
                onChange={(v) => set("work_rights_current_country", v)}
              />
              <TextField label="Visa Status" value={form.visa_status} onChange={(v) => set("visa_status", v)} />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <CheckboxField
                label="Eligible to work in NZ"
                checked={form.eligible_to_work_nz}
                onChange={(v) => set("eligible_to_work_nz", v)}
                icon={Globe}
              />
              <CheckboxField
                label="Need Sponsorship"
                checked={form.need_sponsorship}
                onChange={(v) => set("need_sponsorship", v)}
                icon={Handshake}
              />
              <CheckboxField
                label="Driver License"
                checked={form.driver_license}
                onChange={(v) => set("driver_license", v)}
                icon={IdCard}
              />
              <CheckboxField
                label="Own Vehicle"
                checked={form.own_vehicle}
                onChange={(v) => set("own_vehicle", v)}
                icon={Car}
              />
            </div>
          </SectionCard>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
          <SectionCard title="Professional Links">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <TextField
                label="LinkedIn"
                value={form.linkedin_url}
                onChange={(v) => set("linkedin_url", v)}
                placeholder="https://linkedin.com/in/…"
              />
              <TextField
                label="Portfolio"
                value={form.portfolio_url}
                onChange={(v) => set("portfolio_url", v)}
                placeholder="https://…"
              />
              <TextField
                label="Github"
                value={form.github_url}
                onChange={(v) => set("github_url", v)}
                placeholder="https://github.com/…"
              />
              <TextField
                label="Website"
                value={form.website_url}
                onChange={(v) => set("website_url", v)}
                placeholder="https://…"
              />
            </div>
          </SectionCard>

          <SectionCard title="Emergency Contact">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <TextField
                label="Name"
                value={form.emergency_contact_name}
                onChange={(v) => set("emergency_contact_name", v)}
              />
              <TextField
                label="Relationship"
                value={form.emergency_contact_relationship}
                onChange={(v) => set("emergency_contact_relationship", v)}
              />
              <TextField
                label="Phone"
                value={form.emergency_contact_phone}
                onChange={(v) => set("emergency_contact_phone", v)}
              />
            </div>
          </SectionCard>
        </div>

        <ResumeSection />

        <SectionCard title="References">
          <div className="space-y-3">
            {references.length === 0 && (
              <p className="text-sm text-gray-500">No references added yet.</p>
            )}
            {references.map((ref, i) => (
              <ReferenceRow
                key={i}
                reference={ref}
                onChange={(updated) =>
                  setReferences((refs) => refs.map((r, idx) => (idx === i ? updated : r)))
                }
                onRemove={() => setReferences((refs) => refs.filter((_, idx) => idx !== i))}
              />
            ))}
            <button
              type="button"
              onClick={() =>
                setReferences((refs) => [
                  ...refs,
                  { name: "", company: null, relationship: null, email: null, phone: null },
                ])
              }
              className={buttonClasses("secondary", "sm")}
            >
              + Add Reference
            </button>
          </div>
        </SectionCard>

        <SectionCard title="Notes">
          <textarea
            value={form.notes ?? ""}
            onChange={(e) => set("notes", e.target.value)}
            rows={4}
            placeholder="Anything else worth remembering across applications…"
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-500 transition-colors resize-y"
          />
        </SectionCard>
      </div>

      <div className="flex justify-end mt-5">
        <button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          className={buttonClasses("primary")}
        >
          {saveMutation.isPending ? "Saving…" : "Save Profile"}
        </button>
      </div>
    </div>
  );
}
