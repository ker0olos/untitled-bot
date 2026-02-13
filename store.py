"""Server state: watched channels, webhooks, and custom name/avatar per server."""
from typing import Dict

from supabase_client import get_supabase

# server_id -> channel_id
watched_channels: Dict[str, str] = {}
# server_id -> (webhook_id, webhook_token)
webhook_by_server: Dict[str, tuple] = {}
# server_id -> display name for webhook replies
webhook_name_by_server: Dict[str, str] = {}
# server_id -> avatar URL for webhook replies
webhook_avatar_by_server: Dict[str, str] = {}


async def load_watched_channels() -> None:
    """Load all watched channels and webhook config from Supabase on startup."""
    try:
        supabase = get_supabase()
        response = supabase.table('servers').select('*').execute()

        watched_channels.clear()
        webhook_by_server.clear()
        webhook_name_by_server.clear()
        webhook_avatar_by_server.clear()

        for row in response.data:
            server_id = str(row.get('server_id'))
            channel_id = str(row.get('channel_id'))
            wh_id = row.get('webhook_id')
            wh_token = row.get('webhook_token')
            if server_id and channel_id:
                if wh_id and wh_token:
                    watched_channels[server_id] = channel_id
                    webhook_by_server[server_id] = (str(wh_id), str(wh_token))
                name = row.get('webhook_name')
                avatar = row.get('webhook_avatar_url')
                if name:
                    webhook_name_by_server[server_id] = name
                if avatar:
                    webhook_avatar_by_server[server_id] = avatar
                print(f'  - Watching server {server_id}, channel {channel_id}')
    except Exception as e:
        print(f'Failed to load watched channels: {e}')
