# Telegram Bot Setup

Project Kiwi uses Telegram for personal notifications. This guide walks through creating the bot from scratch.

---

## Step 1 — Create the Bot via BotFather

1. Open Telegram and search for **@BotFather**
2. Start a conversation and send: `/newbot`
3. When prompted, choose a name: `Project Kiwi`
4. When prompted, choose a username (must end in `bot`): e.g. `project_kiwi_YOUR_NAME_bot`
5. BotFather will respond with your **Bot Token** — save it immediately

---

## Step 2 — Get Your Chat ID

1. Start a conversation with your new bot (search for its username and click Start)
2. Send any message to the bot (e.g. "hello")
3. Open this URL in your browser, replacing `<YOUR_BOT_TOKEN>`:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. Find the `"id"` field inside `"chat"` in the response — that is your **Chat ID**

---

## Step 3 — Add Credentials to .env

Open your `.env` file and fill in:

```
TELEGRAM_BOT_TOKEN=your_token_from_botfather
TELEGRAM_CHAT_ID=your_chat_id_from_step_2
```

---

## Step 4 — Send a Test Notification

With the backend running, either:
- Click **Send Test Notification** in the dashboard, or
- Make a POST request: `curl -X POST http://localhost:8000/api/v1/notifications/test`

You should receive this message in Telegram:
> 🥝 **Project Kiwi** is online. Notifications are working correctly.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No message received | Confirm the bot token and chat ID in `.env` are correct |
| `Chat not found` error | Make sure you started a conversation with the bot first (Step 2, Step 1) |
| `Unauthorized` error | Bot token is invalid — regenerate via `/mybots` in BotFather |
| Dashboard shows "Telegram not configured" | `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` is missing from `.env` |
