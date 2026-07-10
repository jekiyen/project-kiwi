import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useToast } from "../hooks/useToast";
import { errorMessage } from "../shared";

function StatusBadge({ ok, onLabel, offLabel }: { ok: boolean; onLabel: string; offLabel: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium ${
        ok
          ? "bg-green-900/50 text-green-300 ring-1 ring-green-800/50"
          : "bg-gray-800 text-gray-400 ring-1 ring-gray-700"
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? "bg-green-400" : "bg-gray-500"}`} />
      {ok ? onLabel : offLabel}
    </span>
  );
}

function StatusRow({ label, ok, onLabel, offLabel }: { label: string; ok: boolean; onLabel: string; offLabel: string }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-gray-400">{label}</span>
      <StatusBadge ok={ok} onLabel={onLabel} offLabel={offLabel} />
    </div>
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
  const { push } = useToast();

  const { data: config, isLoading, isError } = useQuery({
    queryKey: ["notificationConfig"],
    queryFn: api.notificationConfig,
  });

  const testMutation = useMutation({
    mutationFn: api.sendTestNotification,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notificationConfig"] }),
    onError: (err) => push(`Couldn't send test notification: ${errorMessage(err)}`, "error"),
  });

  const detectMutation = useMutation({
    mutationFn: api.detectChatId,
    onError: (err) => push(`Couldn't detect chat ID: ${errorMessage(err)}`, "error"),
  });

  const telegram = config?.telegram;
  const configured = telegram?.configured ?? false;
  const botConnected = telegram?.bot_connected ?? false;
  const chatIdPresent = telegram?.chat_id_present ?? false;
  const botTokenPresent = telegram?.bot_token_present ?? false;

  let explanation: string;
  if (configured) {
    explanation = "Telegram is fully set up. You'll receive alerts for high-match jobs, scan results, and application updates.";
  } else if (!botTokenPresent) {
    explanation =
      "Telegram notifications aren't set up yet. Add TELEGRAM_BOT_TOKEN to your .env file, restart the backend, then use Detect Chat ID below.";
  } else if (!botConnected) {
    explanation = "A bot token is set, but Telegram couldn't be reached — double check TELEGRAM_BOT_TOKEN is correct.";
  } else if (!chatIdPresent) {
    explanation = "Bot is connected. Click Detect Chat ID below, message your bot on Telegram, then copy the chat ID into TELEGRAM_CHAT_ID in your .env file.";
  } else {
    explanation = "Everything is set except TELEGRAM_ENABLED — set it to true in your .env file and restart the backend.";
  }

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
            <StatusBadge ok={configured} onLabel="Configured" offLabel="Not Configured" />
          )}
        </div>

        {!isLoading && !isError && (
          <>
            <div className="divide-y divide-gray-800/70 mt-3">
              <StatusRow label="Bot Status" ok={botConnected} onLabel="Connected" offLabel="Disconnected" />
              <StatusRow label="Chat ID" ok={chatIdPresent} onLabel="Detected" offLabel="Not Configured" />
            </div>

            <p className="text-gray-500 text-sm mt-3 leading-relaxed">{explanation}</p>
          </>
        )}

        <div className="flex items-center gap-3 mt-4 flex-wrap">
          <button
            onClick={() => detectMutation.mutate()}
            disabled={!botTokenPresent || detectMutation.isPending}
            title={!botTokenPresent ? "Set TELEGRAM_BOT_TOKEN in .env first" : undefined}
            className={`text-sm px-4 py-2 rounded-lg font-medium transition-colors border ${
              !botTokenPresent
                ? "border-gray-800 text-gray-600 cursor-not-allowed"
                : "border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 disabled:opacity-50"
            }`}
          >
            {detectMutation.isPending ? "Detecting…" : "Detect Chat ID"}
          </button>

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
        </div>

        {testMutation.data && (
          <p className={`text-sm mt-2 ${testMutation.data.success ? "text-green-400" : "text-gray-500"}`}>
            {testMutation.data.message}
          </p>
        )}

        {detectMutation.data && (
          <div className="mt-3">
            <p className={`text-sm ${detectMutation.data.detected.length > 0 ? "text-gray-300" : "text-gray-500"}`}>
              {detectMutation.data.message}
            </p>
            {detectMutation.data.detected.length > 0 && (
              <ul className="mt-2 space-y-1.5">
                {detectMutation.data.detected.map((chat) => (
                  <li
                    key={chat.chat_id}
                    className="flex items-center justify-between gap-3 bg-gray-800/60 border border-gray-700 rounded px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="text-sm text-gray-200 truncate">{chat.display_name}</p>
                      <p className="text-xs text-gray-500">{chat.type}</p>
                    </div>
                    <code className="text-xs text-blue-300 bg-gray-900 px-2 py-1 rounded shrink-0">
                      {chat.chat_id}
                    </code>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
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
