# Job Application + Resume RAG Dashboard

Tracks your daily job applications, stores your actual resume files, and lets
you **semantically search and chat** over their content — "which resume
emphasizes backend work?", "what did I say about my AWS experience?" — not
just filter by filename. Backed entirely by Supabase, so it's hostable
(no local database file to worry about).

## What's in this app

| Tab | What it does |
|---|---|
| 📊 Dashboard | Search/filter your application log by company, role, resume filename, or date. Browse and download original resume files. |
| ➕ Add Resume | Upload a PDF/DOCX/TXT resume for a specific application — it's stored in Supabase Storage (for download) and indexed for RAG search. |
| 💬 RAG Chat | Ask natural-language questions; Gemini answers using the most relevant resume chunks it retrieves via vector search. |
| 📥 Daily Import | Bulk-upload your daily Apify `.xlsx` export (columns: `S.No, Company, Role, Url, Resume`) — appends new rows, skips duplicates automatically. |

## Architecture

```
Supabase (Postgres + pgvector + Storage)
 ├─ applications table   → your job tracker rows
 ├─ resume_chunks table  → extracted resume text, chunked + embedded (pgvector)
 └─ "resumes" bucket     → original PDF/DOCX files, for download

Streamlit app (this repo)
 ├─ Dashboard tab   → reads/searches `applications`
 ├─ Add Resume tab  → uploads file to Storage, extracts text, embeds, writes `resume_chunks`
 ├─ RAG Chat tab    → embeds your question → pgvector similarity search → Gemini Flash answers
 └─ Daily Import    → bulk-appends `applications` rows from an xlsx

Google Gemini API (free tier)
 ├─ gemini-embedding-001 → turns resume text / your question into vectors
 └─ gemini-2.5-flash     → generates the chat answer, grounded in retrieved chunks
```

## 1. Set up Supabase (~5 minutes)

1. Create a free project at [supabase.com](https://supabase.com).
2. Go to **SQL Editor** → **New query**, paste the entire contents of
   [`schema.sql`](./schema.sql) from this repo, and click **Run**. This creates:
   - the `applications` and `resume_chunks` tables
   - the `pgvector` extension + similarity search function
   - a private Storage bucket named `resumes`
3. Go to **Project Settings → API**. You'll need two values:
   - **Project URL** → `SUPABASE_URL`
   - **`service_role` secret key** (not the `anon` key — this app runs
     server-side, so it needs the elevated key) → `SUPABASE_SERVICE_KEY`

⚠️ The `service_role` key bypasses all row-level security — never expose it
to a browser or commit it to a public repo. It's meant for exactly this kind
of server-side app.

## 2. Get a free Gemini API key (~1 minute)

Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey), sign
in with a Google account, and create a key. The free tier covers embeddings
and Flash-model chat generously for personal use — no card required.

## 3. Configure secrets

Copy the example file and fill in the three values from steps 1–2:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml`:
```toml
SUPABASE_URL = "https://your-project-ref.supabase.co"
SUPABASE_SERVICE_KEY = "your-service-role-key"
GEMINI_API_KEY = "your-gemini-api-key"
```

## 4. Run locally

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`.

## 5. Deploy (so it's hosted, not just local)

**Streamlit Community Cloud (free, easiest):**
1. Push this folder to a GitHub repo (`.streamlit/secrets.toml` is gitignored
   automatically — don't force-add it).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** →
   point it at your repo and `app.py`.
3. In the app's **Settings → Secrets**, paste the same three key-value pairs
   from your local `secrets.toml`.
4. Deploy. You now have a hosted URL you can open from anywhere.

Any other host that runs a long-lived Python process works too (Render,
Railway, Fly.io, a VPS) — just set the same three environment variables and
run `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`.

## Daily workflow

1. Pull today's export from Apify (however you currently get the `.xlsx`).
2. Open the dashboard → **Daily Import** tab → pick the date → upload → Import.
3. For any application where you want the actual resume file searchable/
   downloadable later, use **Add Resume** to upload the PDF/DOCX for that
   company + role.
4. Use **Dashboard** to search/filter/download, or **RAG Chat** to ask
   questions across everything you've uploaded.

## Notes on the RAG design

- **Chunking**: resumes are short, so most fit in a single chunk (full
  context, nothing fragmented). Longer resumes are split on paragraph/section
  boundaries with overlap, so context isn't lost at chunk edges.
- **Embeddings**: `gemini-embedding-001`, truncated to 768 dimensions (via
  Matryoshka Representation Learning) to keep storage/query costs low while
  staying accurate. Uses Gemini's `RETRIEVAL_DOCUMENT` vs `RETRIEVAL_QUERY`
  task types — this asymmetric embedding tuning measurably improves search
  quality over embedding both sides the same way.
- **Retrieval**: pgvector cosine similarity via a Postgres function
  (`match_resume_chunks`), called through Supabase's `.rpc()` — the vector
  math runs in the database, not in Python.
- **Generation**: `gemini-2.5-flash` (not Pro — Google removed Pro models
  from the free tier in April 2026). The prompt instructs the model to
  answer only from retrieved context and say so plainly if the answer isn't
  there, to avoid confidently making things up about your own resume history.

## Extending this later

- **Multi-user**: add Supabase Auth, switch from the `service_role` key to
  per-user JWTs, and add RLS policies scoped to `auth.uid()` (the schema
  leaves room for this).
- **Automated daily pull**: instead of manually uploading the xlsx, a
  scheduled script (cron / GitHub Action) can call the Apify API
  (`GET /v2/datasets/{id}/items?format=xlsx`) and call
  `applications_db.ingest_excel()` directly — ask if you want this built out.
