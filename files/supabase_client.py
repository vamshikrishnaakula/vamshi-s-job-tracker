"""Single shared Supabase client. Uses the service_role key because this app
runs server-side (Streamlit's Python process, not the user's browser) and is
built for a single user managing their own data — service_role bypasses RLS,
which is fine here since no untrusted browser code ever sees this key.
"""

from functools import lru_cache

from supabase import create_client, Client

import config


@lru_cache(maxsize=1)
def get_client() -> Client:
    if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_KEY:
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY "
            "(see README.md for where to find these in your Supabase project)."
        )
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
