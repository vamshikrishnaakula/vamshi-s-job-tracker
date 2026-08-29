"""Central place for configuration / secrets.

Reads from environment variables. When running under Streamlit, these are
best supplied via `.streamlit/secrets.toml` (Streamlit auto-loads secrets
into `os.environ` is NOT automatic, so app.py copies st.secrets -> os.environ
at startup — see app.py). Locally, a plain `.env` file + `python-dotenv`
also works fine for scripts/tests.
"""

import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")  # service_role key, server-side only
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Models (see README for why these specific ones)
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768  # truncated via MRL; must match the `vector(768)` column in schema.sql
CHAT_MODEL = "gemini-2.5-flash"

RESUME_BUCKET = "resumes"

# Chunking
CHUNK_SIZE_CHARS = 1200
CHUNK_OVERLAP_CHARS = 200


def missing_config() -> list[str]:
    """Returns a list of human-readable names of any missing required config,
    so the UI can show a clear setup message instead of a stack trace."""
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_KEY:
        missing.append("SUPABASE_SERVICE_KEY")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    return missing
