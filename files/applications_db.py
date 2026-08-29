"""CRUD + xlsx ingestion for the `applications` table in Supabase Postgres.

This is the "job tracker" half of the app — separate from the RAG/resume
content half (see resumes_db.py). Mirrors the earlier SQLite version's
ingest logic, just pointed at Supabase instead of a local file.
"""

from datetime import datetime, date
from io import BytesIO

import pandas as pd

from supabase_client import get_client

TABLE = "applications"


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key in ("s.no", "s no", "sno", "s_no"):
            rename_map[col] = "s_no"
        elif key == "company":
            rename_map[col] = "company"
        elif key == "role":
            rename_map[col] = "role"
        elif key == "url":
            rename_map[col] = "url"
        elif key == "resume":
            rename_map[col] = "resume_filename"
    df = df.rename(columns=rename_map)
    for needed in ["s_no", "company", "role", "url", "resume_filename"]:
        if needed not in df.columns:
            df[needed] = None
    return df[["s_no", "company", "role", "url", "resume_filename"]].dropna(how="all")


def ingest_excel(file_or_bytes, applied_date: date, source_name: str) -> tuple[int, int]:
    """Read an Apify xlsx export and upsert rows into Supabase.
    Duplicate (company, role, url, date_applied) rows are skipped via the
    table's UNIQUE constraint + upsert(on_conflict=...) ignoring duplicates.
    Returns (rows_in_file, rows_inserted)."""
    df = pd.read_excel(file_or_bytes)
    df = _normalize_columns(df)

    records = []
    for _, row in df.iterrows():
        records.append(
            {
                "s_no": None if pd.isna(row["s_no"]) else int(row["s_no"]),
                "company": None if pd.isna(row["company"]) else str(row["company"]),
                "role": None if pd.isna(row["role"]) else str(row["role"]),
                "url": None if pd.isna(row["url"]) else str(row["url"]),
                "resume_filename": None if pd.isna(row["resume_filename"]) else str(row["resume_filename"]),
                "date_applied": applied_date.isoformat(),
                "date_added": datetime.now().isoformat(),
                "source_file": source_name,
            }
        )

    if not records:
        return 0, 0

    client = get_client()
    # Count rows before, so we can tell how many were newly inserted vs skipped
    # as duplicates (upsert with ignore-duplicates doesn't report this directly).
    before = client.table(TABLE).select("id", count="exact").execute().count or 0

    client.table(TABLE).upsert(
        records,
        on_conflict="company,role,url,date_applied",
        ignore_duplicates=True,
    ).execute()

    after = client.table(TABLE).select("id", count="exact").execute().count or 0
    return len(records), after - before


def load_all() -> pd.DataFrame:
    client = get_client()
    rows = client.table(TABLE).select("*").order("date_applied", desc=True).execute().data
    return pd.DataFrame(rows)


def search(query: str = "", date_from: date | None = None, date_to: date | None = None) -> pd.DataFrame:
    client = get_client()
    q = client.table(TABLE).select("*")
    if date_from:
        q = q.gte("date_applied", date_from.isoformat())
    if date_to:
        q = q.lte("date_applied", date_to.isoformat())
    rows = q.order("date_applied", desc=True).execute().data
    df = pd.DataFrame(rows)

    if query.strip() and not df.empty:
        s = query.strip().lower()
        mask = (
            df["company"].astype(str).str.lower().str.contains(s, na=False)
            | df["role"].astype(str).str.lower().str.contains(s, na=False)
            | df["resume_filename"].astype(str).str.lower().str.contains(s, na=False)
            | df["url"].astype(str).str.lower().str.contains(s, na=False)
        )
        df = df[mask]
    return df


def delete_all() -> None:
    client = get_client()
    client.table(TABLE).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Applications")
    return buf.getvalue()
