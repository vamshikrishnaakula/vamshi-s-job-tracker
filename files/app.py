"""
Job Application + Resume RAG Dashboard
---------------------------------------
Hosted on Streamlit, backed entirely by Supabase (Postgres + pgvector +
Storage) so it works the same locally and deployed. Gemini (free tier)
provides embeddings + chat for the RAG search.

Run locally with:
    streamlit run app.py
"""

import os
from datetime import date

import pandas as pd
import streamlit as st

# --- Load secrets into env vars before importing modules that read them ---
# Locally: put these in .streamlit/secrets.toml. On Streamlit Community
# Cloud: set them in the app's "Secrets" settings (same TOML format).
for key in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "GEMINI_API_KEY"):
    if key in st.secrets:
        os.environ.setdefault(key, st.secrets[key])

import config  # noqa: E402  (must come after secrets are loaded into env)

st.set_page_config(page_title="Resume Dashboard + RAG", layout="wide", page_icon="📄")

missing = config.missing_config()
if missing:
    st.error(
        f"Missing configuration: {', '.join(missing)}. "
        "Add these in `.streamlit/secrets.toml` locally, or in your Streamlit "
        "Cloud app's Secrets settings. See README.md for where to find each value."
    )
    st.stop()

import applications_db  # noqa: E402
import resumes_db  # noqa: E402
import rag  # noqa: E402

st.title("📄 Job Application + Resume Dashboard")
st.caption("Track applications, store resumes, and search/chat over their content — all backed by Supabase.")

tab_dashboard, tab_add, tab_chat, tab_import = st.tabs(
    ["📊 Dashboard", "➕ Add Resume", "💬 RAG Chat", "📥 Daily Import"]
)

# ============================================================================
# TAB 1: Dashboard — search, filter, download
# ============================================================================
with tab_dashboard:
    st.subheader("Search & filter your applications")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        query = st.text_input("🔍 Search (company, role, resume filename, or URL)", key="dash_search")
    with col2:
        date_from = st.date_input("From", value=None, key="dash_from")
    with col3:
        date_to = st.date_input("To", value=None, key="dash_to")

    try:
        results = applications_db.search(query=query or "", date_from=date_from or None, date_to=date_to or None)
    except Exception as e:
        st.error(f"Couldn't load applications: {e}")
        results = pd.DataFrame()

    if results.empty:
        st.info("No applications found yet. Add one via 'Add Resume' or import from the 'Daily Import' tab.")
    else:
        m1, m2 = st.columns(2)
        m1.metric("Matching applications", len(results))
        m2.metric("Unique companies", results["company"].nunique())

        display_cols = [c for c in ["date_applied", "company", "role", "resume_filename", "url"] if c in results.columns]
        st.dataframe(
            results[display_cols].rename(
                columns={
                    "date_applied": "Date Applied",
                    "company": "Company",
                    "role": "Role",
                    "resume_filename": "Resume",
                    "url": "URL",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "⬇️ Download results as .xlsx",
            data=applications_db.to_excel_bytes(results[display_cols]),
            file_name=f"applications_{date.today().isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.divider()
    st.subheader("📂 Resume files (download originals)")
    st.caption("Every resume you've uploaded via 'Add Resume' — search by filename or date, download the original file.")

    try:
        resume_files = resumes_db.list_resumes()
    except Exception as e:
        st.error(f"Couldn't load resume files: {e}")
        resume_files = pd.DataFrame()

    if resume_files.empty:
        st.info("No resume files uploaded yet.")
    else:
        file_search = st.text_input("🔍 Filter by filename", key="file_search")
        filtered_files = resume_files
        if file_search.strip():
            filtered_files = resume_files[
                resume_files["resume_filename"].astype(str).str.lower().str.contains(file_search.strip().lower(), na=False)
            ]

        for _, row in filtered_files.iterrows():
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            c1.write(f"**{row.get('resume_filename', '(no filename)')}**")
            c2.write(row.get("company", ""))
            c3.write(row.get("date_applied", ""))
            if row.get("resume_storage_path"):
                try:
                    url = resumes_db.get_download_url(row["resume_storage_path"])
                    c4.link_button("Download", url)
                except Exception:
                    c4.write("—")

# ============================================================================
# TAB 2: Add Resume — upload a file, index it for RAG
# ============================================================================
with tab_add:
    st.subheader("Add a resume")
    st.caption("Uploads the file to Supabase Storage and indexes its text for semantic search / chat.")

    with st.form("add_resume_form", clear_on_submit=True):
        f1, f2 = st.columns(2)
        with f1:
            company = st.text_input("Company *")
            role = st.text_input("Role")
        with f2:
            applied_date = st.date_input("Date applied", value=date.today())
            url = st.text_input("Job posting URL")

        resume_file = st.file_uploader("Resume file *", type=["pdf", "docx", "txt", "md"])
        submitted = st.form_submit_button("Upload & index", type="primary")

        if submitted:
            if not company.strip() or resume_file is None:
                st.warning("Company and a resume file are required.")
            else:
                with st.spinner("Extracting text, embedding, and uploading..."):
                    try:
                        summary = resumes_db.upload_resume(
                            file_bytes=resume_file.read(),
                            filename=resume_file.name,
                            company=company.strip(),
                            role=role.strip(),
                            date_applied=applied_date,
                            url=url.strip(),
                        )
                        st.success(
                            f"Uploaded and indexed '{resume_file.name}' — "
                            f"{summary['chunks_indexed']} chunks embedded for search."
                        )
                    except Exception as e:
                        st.error(f"Upload failed: {e}")

# ============================================================================
# TAB 3: RAG Chat — semantic search + Q&A over resume content
# ============================================================================
with tab_chat:
    st.subheader("Ask about your resumes")
    st.caption("Semantic search + chat over everything you've uploaded, powered by Gemini.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for turn in st.session_state.chat_history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

    question = st.chat_input("e.g. 'Which resume emphasizes React?' or 'What projects did I list for backend roles?'")
    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Searching your resumes..."):
                try:
                    result = rag.ask(question)
                    st.markdown(result["answer"])
                    if result["sources"]:
                        with st.expander(f"📎 {len(result['sources'])} source chunk(s) used"):
                            for src in result["sources"]:
                                st.markdown(
                                    f"**{src.get('resume_filename', '?')}** "
                                    f"({src.get('company', '?')} — {src.get('role', '?')}) "
                                    f"· similarity {src.get('similarity', 0):.2f}"
                                )
                                st.text(src["content"][:400] + ("..." if len(src["content"]) > 400 else ""))
                    st.session_state.chat_history.append({"role": "assistant", "content": result["answer"]})
                except Exception as e:
                    error_msg = f"Something went wrong: {e}"
                    st.error(error_msg)
                    st.session_state.chat_history.append({"role": "assistant", "content": error_msg})

    if st.session_state.chat_history:
        if st.button("Clear chat"):
            st.session_state.chat_history = []
            st.rerun()

# ============================================================================
# TAB 4: Daily Import — bulk xlsx from Apify
# ============================================================================
with tab_import:
    st.subheader("Import today's Apify export")
    st.caption("Upload the .xlsx Apify produces (columns: S.No, Company, Role, Url, Resume) to bulk-append rows.")

    import_date = st.date_input("Date these applications were sent", value=date.today(), key="import_date")
    uploaded_xlsx = st.file_uploader("Apify .xlsx export", type=["xlsx"], key="import_xlsx")

    if uploaded_xlsx is not None and st.button("Import", type="primary"):
        with st.spinner("Importing..."):
            try:
                total, inserted = applications_db.ingest_excel(uploaded_xlsx, import_date, uploaded_xlsx.name)
                skipped = total - inserted
                st.success(f"Imported {inserted} new rows.")
                if skipped:
                    st.info(f"Skipped {skipped} duplicate rows (already in the dashboard).")
            except Exception as e:
                st.error(f"Import failed: {e}")

    st.divider()
    with st.expander("⚠️ Danger zone"):
        confirm = st.checkbox("I understand this permanently deletes all applications.")
        if st.button("Delete ALL applications", disabled=not confirm):
            applications_db.delete_all()
            st.warning("All applications deleted.")
            st.rerun()
