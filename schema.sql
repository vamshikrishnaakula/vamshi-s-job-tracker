-- Run this once in your Supabase project: Dashboard → SQL Editor → New query → paste → Run.

-- 1. Enable pgvector (Supabase ships this extension, just needs turning on)
create extension if not exists vector;

-- 2. Applications table: your job-tracker rows (one per application)
create table if not exists applications (
    id uuid primary key default gen_random_uuid(),
    s_no int,
    company text,
    role text,
    url text,
    resume_filename text,          -- original filename, e.g. "vamsi_backend_v3.pdf"
    resume_storage_path text,      -- path inside the "resumes" storage bucket
    date_applied date not null,
    date_added timestamptz not null default now(),
    source_file text,              -- which xlsx import (or "manual") this row came from
    unique (company, role, url, date_applied)
);

create index if not exists idx_applications_date_applied on applications (date_applied);
create index if not exists idx_applications_company on applications using gin (to_tsvector('english', coalesce(company, '')));

-- 3. Resume chunks table: extracted resume text, split into chunks, each with an embedding
create table if not exists resume_chunks (
    id bigint generated always as identity primary key,
    application_id uuid references applications (id) on delete cascade,
    resume_filename text,
    chunk_index int,
    content text,
    embedding vector (768)         -- gemini-embedding-001, truncated to 768 dims (MRL)
);

-- Vector index for fast similarity search (cosine distance)
create index if not exists idx_resume_chunks_embedding
    on resume_chunks using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

create index if not exists idx_resume_chunks_application_id on resume_chunks (application_id);

-- 4. Similarity search function — called from Python via supabase.rpc(...)
create or replace function match_resume_chunks (
    query_embedding vector (768),
    match_count int default 5
)
returns table (
    id bigint,
    application_id uuid,
    resume_filename text,
    content text,
    similarity float
)
language sql stable
as $$
    select
        resume_chunks.id,
        resume_chunks.application_id,
        resume_chunks.resume_filename,
        resume_chunks.content,
        1 - (resume_chunks.embedding <=> query_embedding) as similarity
    from resume_chunks
    order by resume_chunks.embedding <=> query_embedding
    limit match_count;
$$;

-- 5. Storage bucket for the actual resume files (PDF/DOCX originals)
-- Run this too — creates a private bucket named "resumes".
insert into storage.buckets (id, name, public)
values ('resumes', 'resumes', false)
on conflict (id) do nothing;

-- Storage policies: since this is a single-user personal tool authenticated
-- via the service_role key from Streamlit (server-side), no per-row RLS
-- policies are required for that key — service_role bypasses RLS by design.
-- If you later add Supabase Auth / multiple users, add RLS policies here
-- scoped to auth.uid().
