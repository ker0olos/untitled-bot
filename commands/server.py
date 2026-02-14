"""Server configuration commands: setchannel, changename, changeavatar."""
import discord
from discord import app_commands
from discord.ext import commands

from supabase_client import get_supabase
from store import (
    watched_channels,
    webhook_by_server,
    webhook_name_by_server,
    webhook_avatar_by_server,
    personality_by_server,
    enabled_by_server,
)


def setup(bot: commands.Bot) -> None:
    """Register server commands with the bot."""

    @bot.tree.command(name='setchannel', description='Set this server\'s channel')
    @app_commands.default_permissions(manage_guild=True)
    async def setchannel(interaction: discord.Interaction):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                'This command can only be used in a text channel.',
                ephemeral=True,
            )
            return

        server_id = str(interaction.guild_id)
        channel_id = str(channel.id)
        try:
            supabase = get_supabase()
            if server_id in webhook_by_server:
                old_id, old_token = webhook_by_server[server_id]
                try:
                    old_webhook = discord.Webhook.partial(int(old_id), old_token, client=bot)
                    await old_webhook.delete()
                except Exception:
                    pass
                del webhook_by_server[server_id]

            webhook = await channel.create_webhook(name='Unnamed')

            payload = {
                'server_id': server_id,
                'channel_id': channel_id,
                'webhook_id': str(webhook.id),
                'webhook_token': webhook.token,
            }
            existing = supabase.table('servers').select('webhook_name, webhook_avatar_url, personality, enabled').eq('server_id', server_id).execute()
            if existing.data and len(existing.data) > 0:
                row = existing.data[0]
                if row.get('webhook_name') is not None:
                    payload['webhook_name'] = row['webhook_name']
                if row.get('webhook_avatar_url') is not None:
                    payload['webhook_avatar_url'] = row['webhook_avatar_url']
                if row.get('personality') is not None:
                    payload['personality'] = row['personality']
                if row.get('enabled') is not None:
                    payload['enabled'] = row['enabled']
            else:
                payload['enabled'] = True
            supabase.table('servers').upsert(payload, on_conflict='server_id').execute()

            watched_channels[server_id] = channel_id
            if webhook.token:
                webhook_by_server[server_id] = (str(webhook.id), webhook.token)
            print(f'Added to watch list: server {server_id}, channel {channel_id}, webhook {webhook.id}')

            await interaction.response.send_message(
                f'Channel set to {channel.mention} for this server (webhook created).',
            )
        except Exception as e:
            await interaction.response.send_message(
                f'Failed to save: {e}',
                ephemeral=True,
            )

    @bot.tree.command(name='changename', description='Set the display name used for webhook replies in this server')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(name='Display name for AI replies')
    async def changename(interaction: discord.Interaction, name: str):
        if not name or len(name.strip()) == 0:
            await interaction.response.send_message('Name cannot be empty.', ephemeral=True)
            return
        name = name.strip()[:80]
        server_id = str(interaction.guild_id)
        try:
            supabase = get_supabase()
            supabase.table('servers').update({'webhook_name': name}).eq('server_id', server_id).execute()
            webhook_name_by_server[server_id] = name
            await interaction.response.send_message(f'Bot Name set to **{name}**.')
        except Exception as e:
            await interaction.response.send_message(f'Failed to save: {e}', ephemeral=True)

    @bot.tree.command(name='changeavatar', description='Set the avatar URL used for webhook replies in this server')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(avatar_url='Image URL for the reply avatar (e.g. https://...)')
    async def changeavatar(interaction: discord.Interaction, avatar_url: str):
        url = (avatar_url or '').strip()
        if not url.lower().startswith(('http://', 'https://')):
            await interaction.response.send_message(
                'Please provide a valid HTTP or HTTPS URL.',
                ephemeral=True,
            )
            return
        server_id = str(interaction.guild_id)
        try:
            supabase = get_supabase()
            supabase.table('servers').update({'webhook_avatar_url': url}).eq('server_id', server_id).execute()
            webhook_avatar_by_server[server_id] = url
            await interaction.response.send_message('Bot Avatar updated')
        except Exception as e:
            await interaction.response.send_message(f'Failed to save: {e}', ephemeral=True)

    @bot.tree.command(name='setpersonality', description='Set the personality/instructions used for AI replies in this server')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(personality='Personality text (instructions for how the AI should behave)')
    async def setpersonality(interaction: discord.Interaction, personality: str):
        text = (personality or '').strip()
        if not text:
            await interaction.response.send_message(
                'Personality cannot be empty. Describe how the AI should behave.',
                ephemeral=True,
            )
            return
        server_id = str(interaction.guild_id)
        try:
            supabase = get_supabase()
            result = supabase.table('servers').update({'personality': text}).eq('server_id', server_id).execute()
            if not result.data:
                supabase.table('servers').upsert(
                    {'server_id': server_id, 'personality': text},
                    on_conflict='server_id',
                ).execute()
            personality_by_server[server_id] = text
            await interaction.response.send_message('Personality updated.')
        except Exception as e:
            await interaction.response.send_message(f'Failed to save: {e}', ephemeral=True)

    @bot.tree.command(name='toggle', description='Turn AI replies on or off for this server')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(on='Turn replies on (true) or off (false)')
    async def toggle(interaction: discord.Interaction, on: bool):
        server_id = str(interaction.guild_id)
        try:
            supabase = get_supabase()
            result = supabase.table('servers').update({'enabled': on}).eq('server_id', server_id).execute()
            if result.data and len(result.data) > 0:
                enabled_by_server[server_id] = on
                status = 'on' if on else 'off'
                await interaction.response.send_message(f'AI replies are now **{status}**.')
            else:
                await interaction.response.send_message(
                    'Set a channel with /setchannel first.',
                    ephemeral=True,
                )
        except Exception as e:
            await interaction.response.send_message(f'Failed to save: {e}', ephemeral=True)
