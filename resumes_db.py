"""Handles resume files: upload to Supabase Storage (so you can download the original),
plus extract -> chunk -> embed -> store in `resume_chunks` for RAG search/chat.
"""

import uuid
from datetime import date, datetime

import pandas as pd

import config
import chunking
import gemini_client
import text_extract
from supabase_client import get_client

APPLICATIONS_TABLE = "applications"
CHUNKS_TABLE = "resume_chunks"


def upload_resume(
    file_bytes: bytes,
    filename: str,
    company: str,
    role: str,
    date_applied: date,
    url: str = "",
) -> dict:
    """Uploads a resume file + creates/updates its application row + indexes
    its text content for RAG search. Returns a summary dict for the UI."""
    client = get_client()

    # 1. Extract text before anything else — fail fast if the file is unusable
    text = text_extract.extract_text(file_bytes, filename)

    # 2. Upload raw file to Storage so the original is downloadable
    storage_path = f"{uuid.uuid4()}-{filename}"
    client.storage.from_(config.RESUME_BUCKET).upload(
        storage_path,
        file_bytes,
        file_options={"content-type": _guess_content_type(filename)},
    )

    # 3. Create or upsert application row
    record = {
        "company": company.strip(),
        "role": role.strip(),
        "url": url.strip() or None,
        "resume_filename": filename,
        "resume_storage_path": storage_path,
        "date_applied": date_applied.isoformat(),
        "date_added": datetime.now().isoformat(),
        "source_file": "manual_resume_upload",
    }
    result = (
        client.table(APPLICATIONS_TABLE)
        .upsert(record, on_conflict="company,role,url,date_applied")
        .execute()
    )
    application_id = result.data[0]["id"]

    # 4. Chunk + embed + store for RAG
    chunks = chunking.chunk_text(text)
    if chunks:
        # Clear any prior chunks for this application if re-uploaded
        client.table(CHUNKS_TABLE).delete().eq("application_id", application_id).execute()

        embeddings = gemini_client.embed_texts(chunks, task_type="RETRIEVAL_DOCUMENT")
        chunk_rows = [
            {
                "application_id": application_id,
                "resume_filename": filename,
                "chunk_index": i,
                "content": chunk,
                "embedding": emb,
            }
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
        ]
        client.table(CHUNKS_TABLE).insert(chunk_rows).execute()

    return {
        "application_id": application_id,
        "chunks_indexed": len(chunks),
        "storage_path": storage_path,
    }


def _guess_content_type(filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    return {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "md": "text/markdown",
    }.get(ext, "application/octet-stream")


def get_download_url(storage_path: str, expires_in: int = 3600) -> str:
    """Signed URL for downloading a private-bucket resume file."""
    client = get_client()
    resp = client.storage.from_(config.RESUME_BUCKET).create_signed_url(storage_path, expires_in)
    if isinstance(resp, dict):
        return resp.get("signedURL") or resp.get("signed_url") or ""
    return str(resp)


def list_resumes() -> pd.DataFrame:
    """All applications that have an actual resume file attached."""
    client = get_client()
    rows = (
        client.table(APPLICATIONS_TABLE)
        .select("*")
        .not_.is_("resume_storage_path", "null")
        .order("date_applied", desc=True)
        .execute()
        .data
    )
    return pd.DataFrame(rows)


def search_similar_chunks(query: str, match_count: int = 5) -> list[dict]:
    """Core RAG retrieval step: embed the query, then use the match_resume_chunks
    Postgres function (pgvector cosine similarity) via Supabase RPC."""
    client = get_client()
    query_embedding = gemini_client.embed_query(query)

    matches = client.rpc(
        "match_resume_chunks",
        {"query_embedding": query_embedding, "match_count": match_count},
    ).execute().data

    if not matches:
        return []

    # Enrich each match with company/role from the applications table
    application_ids = list({m["application_id"] for m in matches if m.get("application_id")})
    apps_by_id = {}
    if application_ids:
        apps = (
            client.table(APPLICATIONS_TABLE)
            .select("id,company,role")
            .in_("id", application_ids)
            .execute()
            .data
        )
        apps_by_id = {a["id"]: a for a in apps}

    for m in matches:
        app = apps_by_id.get(m.get("application_id"), {})
        m["company"] = app.get("company", "?")
        m["role"] = app.get("role", "?")

    return matches


def delete_resume(application_id: str, storage_path: str | None) -> None:
    client = get_client()
    if storage_path:
        try:
            client.storage.from_(config.RESUME_BUCKET).remove([storage_path])
        except Exception:
            pass
    client.table(CHUNKS_TABLE).delete().eq("application_id", application_id).execute()
    client.table(APPLICATIONS_TABLE).delete().eq("id", application_id).execute()
