import discord
from discord import app_commands
from discord.ext import commands
import os
from typing import Optional
from dotenv import load_dotenv

from supabase_client import get_supabase

load_dotenv()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="~", intents=intents)


@bot.event
async def on_ready():
    print(f'{bot.user} has logged in!')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')


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
        await interaction.response.send_message(
            f'Channel set to {channel.mention} for this server.',
            ephemeral=True,
        )
    except Exception as e:
        await interaction.response.send_message(
            f'Failed to save: {e}',
            ephemeral=True,
        )


# Run the bot
if __name__ == '__main__':
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found!")
        print("Please create a .env file with your bot token.")
        print("Copy .env.example to .env and add your token.")
        exit(1)
    
    bot.run(token)
