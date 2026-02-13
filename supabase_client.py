"""Supabase client. Uses SUPABASE_URL and SUPABASE_KEY from environment."""
import os
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

_client: Optional[Client] = None


def get_supabase() -> Client:
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    global _client
    if _client is None:
        _client = create_client(url, key)
    return _client
