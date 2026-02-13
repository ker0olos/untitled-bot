# Yuuki

A Discord bot that joins a channel and replies with AI-generated messages (Google Gemini). Each server can set a watched channel, custom name/avatar for replies, and a personality. State is stored in Supabase.

---

## How it works

1. **Watched channels**  
   Admins use `/setchannel` in a text channel. The bot creates a webhook in that channel and stores the server’s channel + webhook in Supabase. On startup, the bot loads all watched channels from Supabase.

2. **Messages**  
   When someone sends a message in a watched channel (and the author is not a bot), the bot:
   - Logs the message.
   - Either **always** replies if the message mentions the bot’s display name, or replies with a **25% random chance** otherwise.
   - Fetches recent conversation history (last 10 non-bot messages), builds context, and optionally collects media URLs (attachments, embeds, stickers, custom emojis).
   - Calls **Gemini** (LangChain + `langchain-google-genai`) with:
     - A system prompt that includes the server’s **personality** and **name** and rules (short messages, no bullet points, no “I’m an AI”, etc.).
     - The current message (and media URLs) as user input.
     - Recent messages as additional context.
   - Splits the model reply by `|||` and sends each part as a separate message via the **webhook**, using the server’s custom name and avatar.

3. **Per-server config**  
   Stored in Supabase (`servers` table): `server_id`, `channel_id`, webhook id/token, `webhook_name`, `webhook_avatar_url`, `personality`. The bot keeps in-memory caches (`store.py`) and loads them on startup.

4. **AI**  
   - **Gemini**: `ai/gemini.py` — strips custom emojis, builds context, sends text + optional image URLs to Gemini, returns reply text.  
   - **Rules**: `ai/rules.py` — system prompt template and default personality (e.g. tsundere-style).

---

## Project commands

### Run the bot (local)

```bash
# Create and use a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (copy .env.example to .env and fill in)
# Required: DISCORD_BOT_TOKEN, GOOGLE_API_KEY, SUPABASE_URL, SUPABASE_KEY

# Start the bot
python bot.py
```

### Environment variables

| Variable            | Description                          |
|---------------------|--------------------------------------|
| `DISCORD_BOT_TOKEN` | Bot token from Discord Developer Portal |
| `GOOGLE_API_KEY`    | Google AI (Gemini) API key           |
| `SUPABASE_URL`      | Supabase project URL                 |
| `SUPABASE_KEY`      | Supabase anon or service role key    |

Copy `.env.example` to `.env` and fill these in.

### Discord slash commands (require “Manage Server”)

| Command           | Description |
|-------------------|-------------|
| `/setchannel`     | Set this server’s watched channel (creates webhook, saves to Supabase). |
| `/changename`     | Set the display name used for AI replies in this server. |
| `/changeavatar`   | Set the avatar URL used for webhook replies. |
| `/setpersonality` | Set the personality/instructions for AI replies in this server. |

---

## Deploy on Render

This bot is a **long-running process** (no HTTP server). On Render you should use a **Background Worker**, not a Web Service. Background workers are **not** available on the free tier; you need a paid plan (e.g. **Starter**).

### Option A: Render Dashboard (manual)

1. **Create a Background Worker**
   - [Render Dashboard](https://dashboard.render.com) → **New** → **Background Worker**.
   - Connect your Git repo (e.g. GitHub) and select this repository.

2. **Configure the service**
   - **Name**: e.g. `discord-bot`.
   - **Runtime**: **Python 3**.
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
   - **Plan**: e.g. **Starter** (required; free tier does not support workers).

3. **Environment variables**  
   In the service’s **Environment** tab, add:
   - `DISCORD_BOT_TOKEN`
   - `GOOGLE_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`

4. **Deploy**  
   Save and let Render build and start the worker. The bot will run until the service is stopped or redeployed.

### Notes for Render

- **Do not** deploy this as a **Web Service**. Web services expect an HTTP server and are built for zero-downtime deploys; a Discord bot process can conflict with that and may be stopped after a short time.
- **Discord rate limits**: Some users have seen Discord rate-limit (e.g. 429) traffic from Render. If that happens, consider another host or reduce reply frequency.
- **Secrets**: Never commit `.env` or real tokens. Use Render’s environment variables (or Environment Groups) for all secrets.

---

## Supabase

The bot expects a **Supabase** project and a table that stores per-server config. Typical shape:

- **Table**: `servers`
- **Columns**: `server_id` (PK), `channel_id`, `webhook_id`, `webhook_token`, `webhook_name`, `webhook_avatar_url`, `personality` (and any timestamps you use).

Exact schema should match what `store.py` and `commands/server.py` read and write (e.g. `server_id`, `channel_id`, `webhook_id`, `webhook_token`, `webhook_name`, `webhook_avatar_url`, `personality`).
