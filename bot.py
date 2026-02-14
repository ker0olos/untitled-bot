import asyncio
import os
import random
from concurrent.futures import ThreadPoolExecutor
from typing import List

import discord
from dotenv import load_dotenv
from discord.ext import commands

from store import (
    watched_channels,
    webhook_by_server,
    webhook_name_by_server,
    webhook_avatar_by_server,
    personality_by_server,
    load_watched_channels,
)
from ai.gemini import (
    get_media_urls_from_message,
    build_context_from_messages,
    get_gemini_reply,
    strip_custom_emojis,
)
from commands.server import setup as setup_server_commands

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

REPLY_CHANCE = 0.25
CONTEXT_MESSAGE_COUNT = 10
_executor = ThreadPoolExecutor(max_workers=2)


@bot.event
async def on_ready():
    print(f'{bot.user} has logged in!')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

    await load_watched_channels()
    print(f'Loaded {len(watched_channels)} watched channel(s) from database')


@bot.event
async def on_message(message):
    """Log messages from watched channels; trigger AI reply via webhook."""
    if message.guild is None:
        return

    server_id = str(message.guild.id)
    channel_id = str(message.channel.id)

    if server_id in watched_channels and watched_channels[server_id] == channel_id:
        print(f'[{message.guild.name} | #{message.channel.name}] {message.author.name}: {message.content}')

        reply_name = webhook_name_by_server.get(server_id) or "Untitled"
        content_lower = (message.content or "").strip().lower()
        mentioned_by_name = reply_name and reply_name.strip().lower() in content_lower

        # Reply if this message is a reply to something the bot/webhook sent
        is_reply_to_bot = False
        if message.reference and message.reference.message_id:
            ref = message.reference.resolved
            if ref is None:
                try:
                    ref = await message.channel.fetch_message(message.reference.message_id)
                except Exception:
                    ref = None
            if ref is not None:
                if server_id in webhook_by_server:
                    wh_id, _ = webhook_by_server[server_id]
                    if getattr(ref, "webhook_id", None) is not None and ref.webhook_id == int(wh_id):
                        is_reply_to_bot = True
                if ref.author == bot.user:
                    is_reply_to_bot = True

        should_reply = mentioned_by_name or is_reply_to_bot or random.random() < REPLY_CHANCE

        if should_reply:
            try:
                # Previous messages only (exclude current — that's the one we're replying to)
                history: List = []
                async for msg in message.channel.history(limit=CONTEXT_MESSAGE_COUNT + 1):
                    if msg.id != message.id:
                        history.append(msg)
                history.reverse()
                additional_context = build_context_from_messages(history, include_media=False)
                print(f"Additional context: {additional_context}")

                user_content = strip_custom_emojis((message.content or "").strip()) or "(no text)"
                media_urls = get_media_urls_from_message(message)
                if media_urls:
                    print(f"Media URLs: {media_urls}")
                reply_name = webhook_name_by_server.get(server_id) or "Untitled"
                personality = personality_by_server.get(server_id)
                reply_text = await asyncio.get_event_loop().run_in_executor(
                    _executor, get_gemini_reply, user_content, additional_context, media_urls, personality, reply_name
                )
                print(f"Reply text: {reply_text}")
                if reply_text:
                    parts = [p.strip() for p in reply_text.split("|||") if p.strip()]
                    if parts and server_id in webhook_by_server:
                        wh_id, wh_token = webhook_by_server[server_id]
                        webhook = discord.Webhook.partial(int(wh_id), wh_token, client=bot)
                        username = webhook_name_by_server.get(server_id)
                        avatar_url = webhook_avatar_by_server.get(server_id)
                        for part in parts:
                            await webhook.send(
                                content=part,
                                username=username,
                                avatar_url=avatar_url,
                            )
            except Exception as e:
                print(f"Error during AI reply: {e}")


# Register commands
setup_server_commands(bot)

if __name__ == '__main__':
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found!")
        exit(1)
    bot.run(token)
