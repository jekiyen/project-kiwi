import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

function StatusBadge({ configured }: { configured: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium ${
        configured
          ? "bg-green-900/50 text-green-300 ring-1 ring-green-800/50"
          : "bg-gray-800 text-gray-400 ring-1 ring-gray-700"
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${configured ? "bg-green-400" : "bg-gray-500"}`} />
      {configured ? "Configured" : "Not Configured"}
    </span>
  );
}

const EVENTS = [
  { label: "High Match Job", description: "A newly scored job clears the high-match threshold." },
  { label: "Scan Completed", description: "A scan finishes — how many jobs found, new, high priority." },
  { label: "Scan Failed", description: "One or more scrapers failed during a scan." },
  { label: "Application Saved", description: "You save or apply to a job from the Jobs page." },
  { label: "Application Updated", description: "An application's status changes." },
];

export default function NotificationsPage() {
  const qc = useQueryClient();

  const { data: config, isLoading, isError } = useQuery({
    queryKey: ["notificationConfig"],
    queryFn: api.notificationConfig,
  });

  const testMutation = useMutation({
    mutationFn: api.sendTestNotification,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notificationConfig"] }),
  });

  const configured = config?.telegram.configured ?? false;
  const enabled = config?.telegram.enabled ?? false;

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-white">Notifications</h2>
        <p className="text-gray-500 text-sm mt-0.5">
          Alerts for high-match jobs, scan results, and application updates.
        </p>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <div className="flex items-center justify-between gap-3 mb-1">
          <h3 className="text-white font-medium">Telegram</h3>
          {isLoading ? (
            <span className="text-xs text-gray-600">Checking…</span>
          ) : isError ? (
            <span className="text-xs text-red-400">Couldn't load status</span>
          ) : (
            <StatusBadge configured={configured} />
          )}
        </div>

        {!isLoading && !isError && (
          <p className="text-gray-500 text-sm mt-2 leading-relaxed">
            {configured
              ? "Telegram is set up. You'll receive alerts for high-match jobs, scan results, and application updates."
              : enabled
              ? "TELEGRAM_ENABLED is on, but the bot token or chat ID is missing from your .env file."
              : "Telegram notifications aren't set up yet. Add TELEGRAM_ENABLED=true, TELEGRAM_BOT_TOKEN, and TELEGRAM_CHAT_ID to your .env file to enable them — bot setup instructions are coming in a follow-up phase. Until then the app runs normally with notifications silently disabled."}
          </p>
        )}

        <div className="flex items-center gap-3 mt-4">
          <button
            onClick={() => testMutation.mutate()}
            disabled={!configured || testMutation.isPending}
            title={!configured ? "Configure Telegram in .env first" : undefined}
            className={`text-sm px-4 py-2 rounded-lg font-medium transition-colors ${
              !configured
                ? "bg-blue-900/20 text-blue-400/40 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50"
            }`}
          >
            {testMutation.isPending ? "Sending…" : "Test Notification"}
          </button>
          {testMutation.data && (
            <p className={`text-sm ${testMutation.data.success ? "text-green-400" : "text-gray-500"}`}>
              {testMutation.data.message}
            </p>
          )}
          {testMutation.isError && (
            <p className="text-red-400 text-sm">Something went wrong sending the test notification.</p>
          )}
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 mt-4">
        <h3 className="text-white font-medium mb-3">Events</h3>
        <ul className="space-y-2.5">
          {EVENTS.map((e) => (
            <li key={e.label} className="flex flex-col sm:flex-row sm:items-baseline sm:gap-3">
              <span className="text-sm text-gray-300 font-medium sm:w-44 shrink-0">{e.label}</span>
              <span className="text-xs text-gray-500">{e.description}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
