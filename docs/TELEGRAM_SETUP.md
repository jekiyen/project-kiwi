# Telegram Notification Setup

Project Kiwi can send you Telegram messages for high-match jobs, scan results,
and application updates. Notifications stay silently disabled until you
complete every step below — nothing sends until `TELEGRAM_ENABLED=true`.

No code changes are required. It's all `.env` + two buttons on the
**Notifications** page.

---

## Step 1 — Create the bot via BotFather

1. Open Telegram and search for **@BotFather**.
2. Start a conversation and send `/newbot`.
3. Choose a name: e.g. `Project Kiwi`.
4. Choose a username (must end in `bot`): e.g. `project_kiwi_yourname_bot`.
5. BotFather replies with a **bot token** — a string like `123456789:AAExampleTokenValueHere`.

Keep the token private. Don't paste it into chat, commit it to git, or share
it — anyone with it can send messages as your bot.

## Step 2 — Add the token to `.env`

Open `.env` (create it from `.env.example` if you haven't already) and set:

```bash
TELEGRAM_BOT_TOKEN=123456789:AAExampleTokenValueHere
```

Leave `TELEGRAM_ENABLED` and `TELEGRAM_CHAT_ID` alone for now, then restart
the backend so it picks up the new token:

```bash
uvicorn backend.main:app --reload
```

## Step 3 — Start a conversation with your bot

Telegram bots can't message you until you've messaged them first. Search for
your bot's username in Telegram and send it anything — `/start` is fine.

## Step 4 — Detect your Chat ID

Open the dashboard → **Notifications** page. Once the token is set and the
backend can reach Telegram, **Bot Status** shows **Connected**.

Click **Detect Chat ID**. This calls `GET /api/v1/notifications/chat-id`,
which asks Telegram for recent messages sent to your bot and lists every chat
it found — chat ID, type (private/group), and a display name. Nothing is
saved automatically; you copy the chat ID yourself.

For a personal bot, you're normally the only entry, type `private`. If
nothing shows up, you haven't messaged the bot yet — go back to Step 3 and
click Detect Chat ID again.

(If you'd rather not use the in-app detector, the same information is
available by opening
`https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates` in a browser and
reading the `"chat": {"id": ...}` field.)

## Step 5 — Add the Chat ID and enable notifications

Back in `.env`:

```bash
TELEGRAM_ENABLED=true
TELEGRAM_CHAT_ID=123456789
```

Restart the backend. The Notifications page should now show:

- **Bot Status:** Connected
- **Chat ID:** Detected
- Overall: **Configured**

## Step 6 — Send a test notification

Click **Test Notification** (or `curl -X POST http://localhost:8000/api/v1/notifications/test`).
You should receive this in Telegram within a few seconds:

```
🥝 Kiwi Test

Telegram integration successful.

Current time:
2026-07-10 14:32:10 UTC
```

If it doesn't arrive, check `logs/telegram.log` and `logs/notifications.log`
for the error.

---

## What triggers a notification

| Event | When |
|-------|------|
| High Match Job | A newly scored job clears `NOTIFY_HIGH_SCORE_THRESHOLD` (default 80) |
| Scan Completed | A scan finishes |
| Scan Failed | Every scraper in a scan fails |
| Application Saved | You save or apply to a job |
| Application Updated | An application's status changes |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Bot Status: Disconnected | Token is wrong, or the backend has no internet access |
| Detect Chat ID finds nothing | You haven't sent the bot a message yet — see Step 3 |
| `Unauthorized` error | Bot token is invalid — regenerate via `/mybots` in BotFather |
| Test Notification fails, Bot Status Connected | Chat ID is wrong, or it's for a different bot/account |
| Nothing happens at all, no error shown | `TELEGRAM_ENABLED` is still `false` |
| Notifications page shows "Not Configured" | One of `TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` is missing from `.env` |
