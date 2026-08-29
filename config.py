"""Central place for configuration / secrets.

Reads dynamically from environment variables or Streamlit secrets (`.streamlit/secrets.toml`).
"""

import os


def _get_secret(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        try:
            import streamlit as st
            if key in st.secrets:
                val = str(st.secrets[key])
                os.environ[key] = val
        except Exception:
            pass
    return val


def __getattr__(name: str):
    if name in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "GEMINI_API_KEY"):
        return _get_secret(name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# Constant Models & Settings
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768  # truncated via MRL; matches `vector(768)` column in schema.sql
CHAT_MODEL = "gemini-2.5-flash"

RESUME_BUCKET = "resumes"

# Chunking
CHUNK_SIZE_CHARS = 1200
CHUNK_OVERLAP_CHARS = 200


def missing_config() -> list[str]:
    """Returns a list of human-readable names of any missing required config or placeholder values."""
    missing = []
    supabase_url = _get_secret("SUPABASE_URL")
    supabase_key = _get_secret("SUPABASE_SERVICE_KEY")
    gemini_key = _get_secret("GEMINI_API_KEY")

    if not supabase_url or "your-project" in supabase_url.lower():
        missing.append("SUPABASE_URL (needs real Supabase URL)")
    if not supabase_key or "your-supabase" in supabase_key.lower() or "your-service-role" in supabase_key.lower():
        missing.append("SUPABASE_SERVICE_KEY (needs real service_role key)")
    if not gemini_key or "your-gemini" in gemini_key.lower():
        missing.append("GEMINI_API_KEY (needs real Google AI Studio / Labs key)")
    return missing
