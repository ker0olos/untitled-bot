import discord
from discord import app_commands
from discord.ext import commands
import os
from typing import Optional, Dict
from dotenv import load_dotenv

from supabase_client import get_supabase

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
intents.messages = True  # Required to receive message events
bot = commands.Bot(command_prefix="~", intents=intents)

# Track watched channels: dict mapping server_id -> channel_id
watched_channels: Dict[str, str] = {}


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
    """Log messages from watched channels."""
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
    
    # Process commands (required for commands.Bot)
    # await bot.process_commands(message)


# Run the bot
if __name__ == '__main__':
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found!")
        print("Please create a .env file with your bot token.")
        print("Copy .env.example to .env and add your token.")
        exit(1)
    
    bot.run(token)
