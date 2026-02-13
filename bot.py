import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, List
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from supabase_client import get_supabase
from ai.rules import SYSTEM_PROMPT

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
intents.messages = True  # Required to receive message events
bot = commands.Bot(command_prefix="!", intents=intents)

# Track watched channels: dict mapping server_id -> channel_id
watched_channels: Dict[str, str] = {}

# 25% chance to reply in watched channels
REPLY_CHANCE = 1.0
CONTEXT_MESSAGE_COUNT = 10
_executor = ThreadPoolExecutor(max_workers=2)

llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=1,
)


def get_media_urls_from_message(message: discord.Message) -> List[str]:
    """Collect attachment URLs and embed image/thumbnail/video URLs from a message."""
    urls: List[str] = []
    for att in message.attachments:
        urls.append(att.url)
    for embed in message.embeds:
        if getattr(embed.image, "url", None):
            urls.append(embed.image.url)
        if getattr(embed.thumbnail, "url", None):
            urls.append(embed.thumbnail.url)
        if getattr(getattr(embed, "video", None), "url", None):
            urls.append(embed.video.url)
    return urls


def build_context_from_messages(messages: List[discord.Message]) -> str:
    """Format last N messages as context for the model (text + attachment/embed URLs)."""
    lines = []
    for msg in messages:
        author = msg.author.display_name if hasattr(msg.author, 'display_name') else str(msg.author)
        content = (msg.content or "(no text)").strip()
        if not content and (msg.attachments or msg.embeds):
            content = "(media)"
        extra: List[str] = []
        for att in msg.attachments:
            extra.append(att.url)
        for embed in msg.embeds:
            if embed.image.url:
                extra.append(embed.image.url)
            if embed.thumbnail.url:
                extra.append(embed.thumbnail.url)
            if getattr(embed.video, "url", None):
                extra.append(embed.video.url)
        if extra:
            content = f"{content} [media: {' '.join(extra)}]"
        lines.append(f"{author}: {content}")
    return "\n".join(lines) if lines else "(no previous messages)"


def get_gemini_reply(
    user_message: str,
    context: str,
    media_urls: Optional[List[str]] = None,
) -> Optional[str]:
    """Call Gemini with system prompt, context, and optional attachment/embed URLs; return reply text or None."""
    system_text = SYSTEM_PROMPT.format(context=context)
    # Build user content: text plus any media as image_url / file URLs so the model can see them
    if media_urls:
        # For Google GenAI, pass content as a list of content parts with proper format
        content_parts: List = [
            {"type": "text", "text": user_message}
        ]
        for url in media_urls:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": url, "detail": "auto"}
            })
        human_content = content_parts
    else:
        human_content = user_message
    messages = [
        SystemMessage(content=system_text),
        HumanMessage(content=human_content),
    ]
    try:
        response = llm.invoke(messages)
        if response and hasattr(response, "content") and response.content:
            # Handle both string and list responses
            if isinstance(response.content, str):
                return response.content.strip()
            elif isinstance(response.content, list):
                # If content is a list, extract text parts and join them
                text_parts = []
                for part in response.content:
                    if isinstance(part, str):
                        text_parts.append(part)
                    elif isinstance(part, dict) and "text" in part:
                        text_parts.append(part["text"])
                return " ".join(text_parts).strip() if text_parts else None
            else:
                return str(response.content).strip()
    except Exception as e:
        print(f"Gemini API error: {e}")
        import traceback
        traceback.print_exc()
    return None


@bot.event
async def on_ready():
    print(f'{bot.user} has logged in!')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')
    
    # Load watched channels from Supabase
    await load_watched_channels()
    print(f'Loaded {len(watched_channels)} watched channel(s) from database')


async def load_watched_channels():
    """Load all watched channels from Supabase on startup."""
    global watched_channels
    try:
        supabase = get_supabase()
        response = supabase.table('servers').select('server_id, channel_id').execute()
        
        watched_channels.clear()
        for row in response.data:
            server_id = str(row.get('server_id'))
            channel_id = str(row.get('channel_id'))
            if server_id and channel_id:
                watched_channels[server_id] = channel_id
                print(f'  - Watching server {server_id}, channel {channel_id}')
    except Exception as e:
        print(f'Failed to load watched channels: {e}')


@bot.tree.command(name='setchannel', description='Set this server\'s channel')
@app_commands.default_permissions(manage_guild=True)  # Only users with "Manage Server" see/use this by default
async def setchannel(
    interaction: discord.Interaction,
):
    channel = interaction.channel
  
    server_id = str(interaction.guild_id)
    channel_id = str(channel.id)
    try:
        supabase = get_supabase()
        supabase.table('servers').upsert(
            {'server_id': server_id, 'channel_id': channel_id},
            on_conflict='server_id',
        ).execute()
        
        # Update the watched channels dict
        watched_channels[server_id] = channel_id
        print(f'Added to watch list: server {server_id}, channel {channel_id}')
        
        await interaction.response.send_message(
            f'Channel set to {channel.mention} for this server.',
        )
    except Exception as e:
        await interaction.response.send_message(
            f'Failed to save: {e}',
            ephemeral=True,
        )


@bot.event
async def on_message(message: discord.Message):
    """Log messages from watched channels; 25% chance to reply via Gemini."""
    # Ignore messages from bots (including ourselves)
    if message.author.bot:
        return

    # Check if this channel is being watched
    if message.guild is None:  # Ignore DMs
        return

    server_id = str(message.guild.id)
    channel_id = str(message.channel.id)

    # Check if this server is being watched and if this is the watched channel
    if server_id in watched_channels and watched_channels[server_id] == channel_id:
        # Log the message to console
        print(f'[{message.guild.name} | #{message.channel.name}] {message.author.name}: {message.content}')

        # 25% chance to trigger an AI reply
        if random.random() < REPLY_CHANCE:
            try:
                # Fetch last 10 messages in this channel (newest first, then we reverse for chronological context)
                history: List[discord.Message] = []
                async for msg in message.channel.history(limit=CONTEXT_MESSAGE_COUNT):
                    if not msg.author.bot:
                        history.append(msg)
                history.reverse()  # oldest first for context
                context = build_context_from_messages(history)
                print(f"Context: {context}")

                user_content = (message.content or "").strip() or "(no text)"
                media_urls = get_media_urls_from_message(message)
                if media_urls.__len__() > 0: print(f"Media URLs: {media_urls}")
                reply_text = await asyncio.get_event_loop().run_in_executor(
                    _executor, get_gemini_reply, user_content, context, media_urls
                )
                print(f"Reply text: {reply_text}")
                if reply_text:
                    # Support multi-message format: first part is the Discord reply, rest as follow-ups
                    parts = [p.strip() for p in reply_text.split("|||") if p.strip()]
                    if parts:
                        await message.reply(parts[0])
                        for part in parts[1:]:
                            await message.channel.send(part)
            except Exception as e:
                print(f"Error during AI reply: {e}")

# Run the bot
if __name__ == '__main__':
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found!")
        exit(1)
    bot.run(token)
