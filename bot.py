import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix=None, intents=intents)


@bot.event
async def on_ready():
    print(f'{bot.user} has logged in!')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')


@bot.tree.command(name='ping', description='Responds with pong')
async def ping(interaction: discord.Interaction):
    """Responds with pong when pinged"""
    await interaction.response.send_message('Pong!')


# Run the bot
if __name__ == '__main__':
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found!")
        print("Please create a .env file with your bot token.")
        print("Copy .env.example to .env and add your token.")
        exit(1)
    
    bot.run(token)
