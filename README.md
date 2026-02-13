# Discord Bot

A simple Discord bot with a ping/pong command.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a Discord bot application:
   - Go to https://discord.com/developers/applications
   - Create a new application
   - Go to the "Bot" section and create a bot
   - Copy the bot token

3. Set up your environment variables:
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` and replace `your-bot-token-here` with your actual bot token:
     ```
     DISCORD_BOT_TOKEN=your-actual-bot-token
     ```
   
   **Note:** The `.env` file is already in `.gitignore`, so your token won't be committed to git.

4. Invite the bot to your server:
   
   **Step-by-step:**
   
   a. Go to https://discord.com/developers/applications and select your application
   
   b. Click on **"OAuth2"** in the left sidebar, then click **"URL Generator"**
   
   c. Under **"SCOPES"**, check:
      - ✅ `bot`
      - ✅ `applications.commands`
   
   d. Under **"BOT PERMISSIONS"**, check:
      - ✅ `Send Messages` (required for slash commands)
      - (Optional) Add other permissions as needed
   
   e. Copy the generated URL at the bottom (it will look like: `https://discord.com/api/oauth2/authorize?client_id=...`)
   
   f. Open the URL in your browser
   
   g. Select the server you want to invite the bot to
   
   h. Click **"Authorize"** and complete any CAPTCHA if prompted
   
   **Note:** You need "Manage Server" permission on the server to invite bots.

5. Run the bot:
```bash
python bot.py
```

## Commands

- `/ping` - Responds with "Pong!"

## Notes

- Slash commands are automatically synced when the bot starts
- Commands may take a few minutes to appear in Discord after syncing
