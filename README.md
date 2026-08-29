# 💼 Hosted Job Tracker + Resume RAG System

A hosted job application tracker and **AI-powered Resume RAG System** built with **Streamlit**, **Python**, **Supabase (Postgres + pgvector + Storage)**, and **Google Gemini AI**.

---

## 🌟 Key Features

1. **📊 Application Dashboard & Searchable Filters**:
   - Filter your job application log specifically by **Job Role**, **Company Name**, **Resume Filename**, or **Date Range** (From - To).
   - Global keyword search across all fields (Company, Role, Resume, Job URL).
   - Real-time metric cards (Total Applications, Unique Companies, Unique Roles, Linked Resumes).
   - Export filtered or full application list to **Excel (`.xlsx`)**.
   - Browse and download original uploaded PDF/DOCX resume files via secure signed URLs from Supabase Storage.

2. **➕ Resume Upload & Automatic Vector Indexing**:
   - Upload PDF, DOCX, TXT, or MD resume files for any job application.
   - Text is extracted, split into overlapping chunks, embedded using `gemini-embedding-001` (768 dims), and stored in Supabase `resume_chunks` (`pgvector`).
   - Original file is safely saved in Supabase private Storage bucket `resumes`.

3. **💬 AI Resume RAG Chat Assistant**:
   - Ask natural language questions across all your uploaded resumes (e.g., *"Which resume emphasizes React and Cloud?"*, *"What backend projects did I list for Senior roles?"*).
   - Powered by Supabase `pgvector` similarity search (`match_resume_chunks` RPC) and Google `gemini-2.5-flash`.
   - Displays exact similarity percentage scores and source chunk citations.

4. **📥 Daily Excel Batch Upload**:
   - Bulk import daily application logs (e.g. from Apify scrapers or Excel sheets).
   - Normalizes columns automatically (`S.No`, `Company`, `Role`, `Job Title`, `URL`, `Resume`, `Date Applied`).
   - Deduplicates records using Supabase unique constraints — skips existing applications automatically and reports exact new rows added.

---

## 🗄️ Database Schema (`schema.sql`)

Run `schema.sql` in your **Supabase SQL Editor** to create:

- `pgvector` extension.
- `applications` table: stores job application records.
- `resume_chunks` table: stores vector embeddings (768 dims).
- `match_resume_chunks` function: performs cosine similarity vector search.
- `resumes` storage bucket: holds original uploaded resume files.

---

## 🚀 Quick Start Guide

### 1. Setup Supabase
1. Create a free project at [supabase.com](https://supabase.com).
2. Open **SQL Editor** -> **New Query**, copy the contents of `schema.sql`, and click **Run**.
3. In **Project Settings → API**, copy:
   - **Project URL** (`SUPABASE_URL`)
   - **`service_role` Secret Key** (`SUPABASE_SERVICE_KEY`)

### 2. Get Gemini API Key
1. Get a free API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

### 3. Configure Secrets
Create `.streamlit/secrets.toml` in the project root:

```toml
SUPABASE_URL = "https://your-project-ref.supabase.co"
SUPABASE_SERVICE_KEY = "your-supabase-service-role-secret-key"
GEMINI_API_KEY = "your-gemini-api-key"
```

### 4. Run Locally
```bash
python -m venv venv
venv\Scripts\activate       # On Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
App will launch at `http://localhost:8501`.

---

## 🌐 How to Host / Deploy

### Streamlit Community Cloud (Free & Easy)
1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and log in.
3. Click **New App** -> Select your repo and `app.py`.
4. Open **Advanced Settings → Secrets** and paste your `secrets.toml` content (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GEMINI_API_KEY`).
5. Click **Deploy**! Your Job Tracker RAG app is live and hosted.
