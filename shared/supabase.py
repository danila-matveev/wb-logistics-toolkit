from __future__ import annotations

import os
import threading

from supabase import create_client, Client

_client: Client | None = None
_client_env: tuple[str, str] | None = None
_client_lock = threading.Lock()


def get_supabase_client() -> Client:
    """Return a cached Supabase client.

    Re-creates the client if SUPABASE_URL or SUPABASE_KEY have changed since
    last call. Thread-safe via double-checked locking. Reads credentials from environment.
    """
    global _client, _client_env
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set in environment. "
            "Copy .env.example to .env and fill in your credentials."
        )
    env_state = (url, key)
    if _client is not None and _client_env == env_state:
        return _client
    with _client_lock:
        if _client is not None and _client_env == env_state:
            return _client
        _client = create_client(url, key)
        _client_env = env_state
    return _client
