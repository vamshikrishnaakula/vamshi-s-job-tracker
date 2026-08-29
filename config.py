"""Central place for configuration / secrets.

Reads from environment variables. When running under Streamlit, these are
supplied via `.streamlit/secrets.toml`.
"""

import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")  # service_role key, server-side only
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Models
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
    if not SUPABASE_URL or "your-project" in SUPABASE_URL.lower():
        missing.append("SUPABASE_URL (needs real Supabase URL)")
    if not SUPABASE_SERVICE_KEY or "your-supabase" in SUPABASE_SERVICE_KEY.lower() or "your-service-role" in SUPABASE_SERVICE_KEY.lower():
        missing.append("SUPABASE_SERVICE_KEY (needs real service_role key)")
    if not GEMINI_API_KEY or "your-gemini" in GEMINI_API_KEY.lower():
        missing.append("GEMINI_API_KEY (needs real Google AI Studio / Labs key)")
    return missing
