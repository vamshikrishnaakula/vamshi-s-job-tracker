"""CRUD + xlsx ingestion for the `applications` table in Supabase Postgres.

Provides search, filter, and daily Excel import functionality.
"""

from datetime import datetime, date
from io import BytesIO

import pandas as pd

from supabase_client import get_client

TABLE = "applications"


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    date_col_found = None

    for col in df.columns:
        key = str(col).strip().lower().replace("_", "").replace(".", "").replace(" ", "")
        if key in ("sno", "sno", "serialno", "id", "index", "no"):
            rename_map[col] = "s_no"
        elif key in ("company", "companyname", "organization", "firm", "employer"):
            rename_map[col] = "company"
        elif key in ("role", "jobrole", "jobtitle", "position", "title", "designation"):
            rename_map[col] = "role"
        elif key in ("url", "joburl", "link", "joblink", "postingurl", "applylink"):
            rename_map[col] = "url"
        elif key in ("resume", "resumename", "resumefilename", "cv", "cvname", "filename"):
            rename_map[col] = "resume_filename"
        elif key in ("dateapplied", "date", "applieddate", "applicationdate", "appliedon"):
            rename_map[col] = "date_applied_col"
            date_col_found = "date_applied_col"

    df = df.rename(columns=rename_map)

    for needed in ["s_no", "company", "role", "url", "resume_filename"]:
        if needed not in df.columns:
            df[needed] = None

    cols = ["s_no", "company", "role", "url", "resume_filename"]
    if date_col_found and date_col_found in df.columns:
        cols.append(date_col_found)

    return df[cols].dropna(how="all")


def ingest_excel(file_or_bytes, default_applied_date: date, source_name: str) -> tuple[int, int]:
    """Read an xlsx export and upsert rows into Supabase."""
    df = pd.read_excel(file_or_bytes)
    df = _normalize_columns(df)

    records = []
    for _, row in df.iterrows():
        applied_dt = default_applied_date
        if "date_applied_col" in df.columns and pd.notna(row.get("date_applied_col")):
            try:
                parsed_dt = pd.to_datetime(row["date_applied_col"]).date()
                if parsed_dt:
                    applied_dt = parsed_dt
            except Exception:
                pass

        company_val = None if pd.isna(row["company"]) else str(row["company"]).strip()
        role_val = None if pd.isna(row["role"]) else str(row["role"]).strip()
        url_val = None if pd.isna(row["url"]) else str(row["url"]).strip()
        resume_val = None if pd.isna(row["resume_filename"]) else str(row["resume_filename"]).strip()

        if not company_val and not role_val:
            continue

        records.append(
            {
                "s_no": None if pd.isna(row["s_no"]) else int(row["s_no"]),
                "company": company_val,
                "role": role_val,
                "url": url_val,
                "resume_filename": resume_val,
                "date_applied": applied_dt.isoformat(),
                "date_added": datetime.now().isoformat(),
                "source_file": source_name,
            }
        )

    if not records:
        return 0, 0

    client = get_client()
    before = client.table(TABLE).select("id", count="exact").execute().count or 0

    client.table(TABLE).upsert(
        records,
        on_conflict="company,role,url,date_applied",
        ignore_duplicates=True,
    ).execute()

    after = client.table(TABLE).select("id", count="exact").execute().count or 0
    inserted = max(0, after - before)
    return len(records), inserted


def load_all() -> pd.DataFrame:
    client = get_client()
    rows = client.table(TABLE).select("*").order("date_applied", desc=True).execute().data
    return pd.DataFrame(rows)


def search(
    query: str = "",
    company_filter: str = "",
    role_filter: str = "",
    resume_filter: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Filter applications by search query, company, job role, resume filename, and date range."""
    client = get_client()
    q = client.table(TABLE).select("*")

    if date_from:
        q = q.gte("date_applied", date_from.isoformat())
    if date_to:
        q = q.lte("date_applied", date_to.isoformat())

    rows = q.order("date_applied", desc=True).execute().data
    df = pd.DataFrame(rows)

    if df.empty:
        return df

    mask = pd.Series([True] * len(df), index=df.index)

    if query.strip():
        s = query.strip().lower()
        query_mask = (
            df["company"].astype(str).str.lower().str.contains(s, na=False)
            | df["role"].astype(str).str.lower().str.contains(s, na=False)
            | df["resume_filename"].astype(str).str.lower().str.contains(s, na=False)
            | df["url"].astype(str).str.lower().str.contains(s, na=False)
        )
        mask = mask & query_mask

    if company_filter.strip():
        c = company_filter.strip().lower()
        mask = mask & df["company"].astype(str).str.lower().str.contains(c, na=False)

    if role_filter.strip():
        r = role_filter.strip().lower()
        mask = mask & df["role"].astype(str).str.lower().str.contains(r, na=False)

    if resume_filter.strip():
        res = resume_filter.strip().lower()
        mask = mask & df["resume_filename"].astype(str).str.lower().str.contains(res, na=False)

    return df[mask]


def get_unique_companies() -> list[str]:
    """Return sorted list of unique company names for dropdown filters."""
    try:
        df = load_all()
        if df.empty or "company" not in df.columns:
            return []
        companies = df["company"].dropna().astype(str).str.strip().unique()
        return sorted([c for c in companies if c])
    except Exception:
        return []


def get_unique_roles() -> list[str]:
    """Return sorted list of unique role names for dropdown filters."""
    try:
        df = load_all()
        if df.empty or "role" not in df.columns:
            return []
        roles = df["role"].dropna().astype(str).str.strip().unique()
        return sorted([r for r in roles if r])
    except Exception:
        return []


def delete_all() -> None:
    client = get_client()
    client.table(TABLE).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Applications")
    return buf.getvalue()
