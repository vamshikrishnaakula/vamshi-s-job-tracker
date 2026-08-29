"""
Hosted Job Application + Resume RAG Dashboard
----------------------------------------------
Built with Streamlit, Python, Supabase (Postgres + pgvector + Storage), and Google Gemini RAG.

Run locally with:
    streamlit run app.py
"""

import os
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

# --- Load secrets into env vars before importing modules that read them ---
try:
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "GEMINI_API_KEY"):
        if key in st.secrets:
            os.environ[key] = str(st.secrets[key])
except Exception:
    pass

import config  # noqa: E402

st.set_page_config(
    page_title="Job Tracker + Resume RAG",
    layout="wide",
    page_icon="💼",
    initial_sidebar_state="expanded"
)

# Custom CSS for polished aesthetic + hover popover card
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }

    /* Metric Cards Styling */
    .metric-card-box {
        background: #1E293B;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 14px 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
        transition: transform 0.2s ease, border-color 0.2s ease;
        position: relative;
    }

    .metric-card-box:hover {
        border-color: #6366F1;
        transform: translateY(-2px);
    }

    .metric-card-title {
        font-size: 0.8rem;
        font-weight: 600;
        color: #94A3B8;
        margin-bottom: 4px;
    }

    .metric-card-val {
        font-size: 1.7rem;
        font-weight: 800;
        color: #F8FAFC;
        line-height: 1.1;
    }

    .metric-card-sub {
        font-size: 0.75rem;
        color: #38BDF8;
        margin-top: 4px;
        font-weight: 600;
    }

    /* Hover popover for Weekly Applications card */
    .weekly-hover-container {
        position: relative;
        cursor: pointer;
    }

    .weekly-hover-container .hover-popover-box {
        visibility: hidden;
        opacity: 0;
        position: absolute;
        bottom: 108%;
        left: 50%;
        transform: translateX(-50%);
        width: 250px;
        background: #0F172A;
        border: 1.5px solid #6366F1;
        border-radius: 12px;
        padding: 12px 14px;
        box-shadow: 0 14px 35px rgba(0, 0, 0, 0.85);
        z-index: 999999;
        transition: opacity 0.25s ease, visibility 0.25s ease;
        pointer-events: none;
    }

    .weekly-hover-container:hover .hover-popover-box {
        visibility: visible;
        opacity: 1;
    }

    .popover-header {
        font-size: 0.75rem;
        font-weight: 700;
        color: #818CF8;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        padding-bottom: 5px;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .popover-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.8rem;
        padding: 3px 0;
        color: #E2E8F0;
    }

    .popover-badge {
        background: rgba(99, 102, 241, 0.25);
        color: #38BDF8;
        padding: 1px 8px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.75rem;
    }

    /* Reduce left nav (sidebar) width */
    [data-testid="stSidebar"], section[data-testid="stSidebar"] {
        width: 180px !important;
        min-width: 180px !important;
    }
    [data-testid="stSidebar"] > div:first-child, section[data-testid="stSidebar"] > div {
        width: 180px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

missing = config.missing_config()
if missing:
    st.error("⚠️ **Configuration Required Before Connecting:**")
    for m in missing:
        st.markdown(f"- ❌ `{m}`")

    st.warning(
        "Please edit `.streamlit/secrets.toml` in your project folder (`d:\\laragon\\www\\Jobtracker\\.streamlit\\secrets.toml`) "
        "and replace the placeholders with your actual credentials:\n\n"
        "```toml\n"
        'SUPABASE_URL = "https://YOUR-ACTUAL-PROJECT.supabase.co"\n'
        'SUPABASE_SERVICE_KEY = "YOUR-ACTUAL-SERVICE-ROLE-KEY"\n'
        'GEMINI_API_KEY = "YOUR-ACTUAL-GOOGLE-AI-LABS-KEY"\n'
        "```"
    )
    st.info(
        "💡 **Key Setup Guide:**\n"
        "1. **Google AI Studio / Labs LLM Key**: Get your free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)\n"
        "2. **Supabase URL & Key**: Found in Supabase Dashboard → **Project Settings → API** (use the `service_role` secret key)"
    )
    st.stop()

import applications_db  # noqa: E402
import resumes_db  # noqa: E402
import rag  # noqa: E402

def get_daily_weekly_breakdown(df: pd.DataFrame):
    """Calculates today's count, weekly count (last 7 days), and daily date breakdown."""
    if df.empty or "date_applied" not in df.columns:
        return 0, 0, []

    today = date.today()
    seven_days_ago = today - timedelta(days=6)

    try:
        dates_series = pd.to_datetime(df["date_applied"]).dt.date
    except Exception:
        return 0, 0, []

    today_count = int((dates_series == today).sum())
    weekly_count = int((dates_series >= seven_days_ago).sum())

    daily_list = []
    for i in range(7):
        current_day = today - timedelta(days=i)
        count_for_day = int((dates_series == current_day).sum())

        if i == 0:
            label = f"Today ({current_day.strftime('%b %d')})"
        elif i == 1:
            label = f"Yesterday ({current_day.strftime('%b %d')})"
        else:
            label = current_day.strftime("%a, %b %d")

        daily_list.append({
            "label": label,
            "count": count_for_day
        })

    return today_count, weekly_count, daily_list

# Sidebar configuration status
with st.sidebar:
    st.title("vamshi's Job Tracker")
    st.divider()

st.markdown('<div class="main-header">Job Tracker & Resume RAG Dashboard</div>', unsafe_allow_html=True)

tab_dashboard, tab_add, tab_chat, tab_import = st.tabs(
    ["📊 Dashboard", "Add Resume", "RAG Chat", "Daily Import"]
)

# ============================================================================
# TAB 1: Dashboard — Cards ABOVE, Search & Filters BELOW
# ============================================================================
with tab_dashboard:
    # 1. Load initial dataset for top cards
    try:
        all_results = applications_db.load_all()
    except Exception as e:
        all_results = pd.DataFrame()

    today_count, weekly_count, daily_breakdown = get_daily_weekly_breakdown(all_results)

    popover_rows_html = "".join([
        f'<div class="popover-item"><span>{item["label"]}</span><span class="popover-badge">{item["count"]} applied</span></div>'
        for item in daily_breakdown
    ])

    # --- TOP SECTION: KPI Metric Cards ---
    st.subheader("📊 Application Analytics")
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.markdown(
            f"""
            <div class="metric-card-box">
                <div class="metric-card-title">📅 Today's Applications</div>
                <div class="metric-card-val">{today_count}</div>
                <div class="metric-card-sub">Sent today</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c2:
        st.markdown(
            f"""
            <div class="metric-card-box weekly-hover-container">
                <div class="metric-card-title">🗓️ Weekly Applications</div>
                <div class="metric-card-val">{weekly_count}</div>
                <div class="metric-card-sub">Last 7 days (hover details)</div>
                <div class="hover-popover-box">
                    <div class="popover-header">📊 Day-Wise Breakdown</div>
                    {popover_rows_html}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c3:
        st.markdown(
            f"""
            <div class="metric-card-box">
                <div class="metric-card-title">📊 Total Applications</div>
                <div class="metric-card-val">{len(all_results)}</div>
                <div class="metric-card-sub">Total tracked apps</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c4:
        unique_companies = all_results["company"].nunique() if (not all_results.empty and "company" in all_results) else 0
        st.markdown(
            f"""
            <div class="metric-card-box">
                <div class="metric-card-title">🏢 Unique Companies</div>
                <div class="metric-card-val">{unique_companies}</div>
                <div class="metric-card-sub">Companies applied</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c5:
        unique_roles = all_results["role"].nunique() if (not all_results.empty and "role" in all_results) else 0
        st.markdown(
            f"""
            <div class="metric-card-box">
                <div class="metric-card-title">🎯 Unique Roles</div>
                <div class="metric-card-val">{unique_roles}</div>
                <div class="metric-card-sub">Positions targeted</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.divider()

    # --- MIDDLE SECTION: Search & Filter Controls (BELOW CARDS) ---
    st.subheader("🔍 Filter & Search Applications")
    st.caption("Filter by job role, company name, resume filename, or date range.")

    with st.expander("🛠️ Advanced Search Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            search_query = st.text_input("🔎 Keyword Search", placeholder="e.g. React, Engineer, Amazon...", key="dash_search")
        with col2:
            existing_companies = ["All Companies"] + applications_db.get_unique_companies()
            selected_company_option = st.selectbox("🏢 Filter by Company", options=existing_companies, key="dash_company_select")
            company_filter = "" if selected_company_option == "All Companies" else selected_company_option

        with col3:
            existing_roles = ["All Roles"] + applications_db.get_unique_roles()
            selected_role_option = st.selectbox("🎯 Filter by Job Role", options=existing_roles, key="dash_role_select")
            role_filter = "" if selected_role_option == "All Roles" else selected_role_option

        col4, col5, col6 = st.columns(3)
        with col4:
            resume_filter = st.text_input("📄 Filter by Resume Filename", placeholder="e.g. backend_v2.pdf", key="dash_resume")
        with col5:
            date_from = st.date_input("📅 Date From", value=None, key="dash_from")
        with col6:
            date_to = st.date_input("📅 Date To", value=None, key="dash_to")

    # Perform search filtering
    try:
        results = applications_db.search(
            query=search_query,
            company_filter=company_filter,
            role_filter=role_filter,
            resume_filter=resume_filter,
            date_from=date_from or None,
            date_to=date_to or None,
        )
    except Exception as e:
        st.error(f"Error loading applications database: {e}")
        results = pd.DataFrame()

    if results.empty:
        st.info("No applications match your search filters. Import daily Excel logs or add a resume to get started.")
    else:
        st.caption(f"Showing **{len(results)}** matching applications:")
        display_cols = [c for c in ["date_applied", "company", "role", "resume_filename", "url", "source_file"] if c in results.columns]
        
        st.dataframe(
            results[display_cols].rename(
                columns={
                    "date_applied": "Date Applied",
                    "company": "Company",
                    "role": "Role",
                    "resume_filename": "Resume File",
                    "url": "Job URL",
                    "source_file": "Import Source",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        d_col1, d_col2 = st.columns([1, 4])
        with d_col1:
            st.download_button(
                "⬇️ Export to Excel (.xlsx)",
                data=applications_db.to_excel_bytes(results[display_cols]),
                file_name=f"job_applications_{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

    st.divider()
    st.subheader("📁 Resume Storage & Downloads")
    st.caption("Download original resume PDF/DOCX files directly from Supabase Storage.")

    try:
        resume_files = resumes_db.list_resumes()
    except Exception as e:
        st.error(f"Couldn't load resume files list: {e}")
        resume_files = pd.DataFrame()

    if resume_files.empty:
        st.info("No resume files uploaded yet. Use the 'Add Resume' tab to upload PDF/DOCX resumes.")
    else:
        file_search = st.text_input("🔍 Search stored resume files", key="file_search")
        filtered_files = resume_files
        if file_search.strip():
            filtered_files = resume_files[
                resume_files["resume_filename"].astype(str).str.lower().str.contains(file_search.strip().lower(), na=False)
            ]

        for _, row in filtered_files.iterrows():
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            c1.write(f"📄 **{row.get('resume_filename', '(no filename)')}**")
            c2.write(f"🏢 {row.get('company', '-')}")
            c3.write(f"📅 {row.get('date_applied', '-')}")
            if row.get("resume_storage_path"):
                try:
                    url = resumes_db.get_download_url(row["resume_storage_path"])
                    if url:
                        c4.link_button("Download", url)
                    else:
                        c4.write("—")
                except Exception:
                    c4.write("—")

# ============================================================================
# TAB 2: Add Resume — upload file, extract text & index vectors for RAG
# ============================================================================
with tab_add:
    st.subheader("➕ Upload Resume & Index for RAG Search")
    st.caption("Uploads the original file to Supabase Storage and creates vector embeddings for RAG chat.")

    with st.form("add_resume_form", clear_on_submit=True):
        f1, f2 = st.columns(2)
        with f1:
            company = st.text_input("Company Name *", placeholder="e.g. Google, Microsoft, Startup Inc")
            role = st.text_input("Job Role / Position", placeholder="e.g. Senior Software Engineer")
        with f2:
            applied_date = st.date_input("Date Applied", value=date.today())
            url = st.text_input("Job Posting URL", placeholder="https://...")

        resume_file = st.file_uploader("Upload Resume File * (PDF, DOCX, TXT, MD)", type=["pdf", "docx", "txt", "md"])
        submitted = st.form_submit_button("🚀 Upload & Build RAG Index", type="primary")

        if submitted:
            if not company.strip() or resume_file is None:
                st.warning("⚠️ Both Company Name and a Resume file are required.")
            else:
                with st.spinner("Processing resume: extracting text, uploading to Supabase Storage, and generating Gemini embeddings..."):
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
                            f"🎉 Successfully uploaded and indexed **'{resume_file.name}'**!\n\n"
                            f"• **Chunks Indexed for RAG**: {summary['chunks_indexed']}\n"
                            f"• **Stored in Bucket**: `{summary['storage_path']}`"
                        )
                    except Exception as e:
                        st.error(f"❌ Upload failed: {e}")

# ============================================================================
# TAB 3: RAG Chat — vector search + Gemini grounded AI answer
# ============================================================================
with tab_chat:
    st.subheader("💬 AI Resume Assistant (RAG Chat)")
    st.caption("Ask questions across all your uploaded resumes. Powered by pgvector similarity search & Google Gemini.")

    st.markdown("**Suggested Questions:**")
    q_cols = st.columns(3)
    p1 = q_cols[0].button("💡 Which resume highlights Python & AI?")
    p2 = q_cols[1].button("💡 What backend projects are listed?")
    p3 = q_cols[2].button("💡 Compare my resumes for Lead roles")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for turn in st.session_state.chat_history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

    selected_prompt = None
    if p1:
        selected_prompt = "Which resume highlights Python & AI?"
    elif p2:
        selected_prompt = "What backend projects are listed in my resumes?"
    elif p3:
        selected_prompt = "Compare my resumes for Lead roles."

    user_question = st.chat_input("Ask anything about your resumes (e.g. 'What experience do I have with AWS?')")
    question_to_process = selected_prompt or user_question

    if question_to_process:
        st.session_state.chat_history.append({"role": "user", "content": question_to_process})
        with st.chat_message("user"):
            st.markdown(question_to_process)

        with st.chat_message("assistant"):
            with st.spinner("🔍 Searching pgvector index and querying Gemini..."):
                try:
                    result = rag.ask(question_to_process)
                    st.markdown(result["answer"])

                    if result["sources"]:
                        with st.expander(f"📎 Grounded in {len(result['sources'])} retrieved resume chunk(s)"):
                            for i, src in enumerate(result["sources"], 1):
                                sim_pct = float(src.get("similarity", 0)) * 100
                                st.markdown(
                                    f"**Chunk #{i}** | 📄 `{src.get('resume_filename', '?')}` "
                                    f"({src.get('company', '?')} — {src.get('role', '?')}) "
                                    f"• **Similarity**: `{sim_pct:.1f}%`"
                                )
                                st.info(src["content"])
                    st.session_state.chat_history.append({"role": "assistant", "content": result["answer"]})
                except Exception as e:
                    error_msg = f"⚠️ RAG Search Error: {e}"
                    st.error(error_msg)
                    st.session_state.chat_history.append({"role": "assistant", "content": error_msg})

    if st.session_state.chat_history:
        if st.button("🗑️ Clear Chat History"):
            st.session_state.chat_history = []
            st.rerun()

# ============================================================================
# TAB 4: Daily Import — Bulk Upload Excel logs from Apify / spreadsheets
# ============================================================================
with tab_import:
    st.subheader("📥 Daily Excel Batch Import")
    st.caption("Upload daily `.xlsx` application logs (e.g. from Apify scrapers or manual logs). Automatically normalizes columns and ignores duplicates.")

    import_date = st.date_input("📅 Date Applications Were Sent", value=date.today(), key="import_date")
    uploaded_xlsx = st.file_uploader("Upload Daily `.xlsx` File", type=["xlsx"], key="import_xlsx")

    if uploaded_xlsx is not None:
        try:
            preview_df = pd.read_excel(uploaded_xlsx)
            st.markdown("**Preview of Excel File:**")
            st.dataframe(preview_df.head(5), use_container_width=True)

            if st.button("📥 Start Daily Import", type="primary"):
                with st.spinner("Importing and deduplicating applications in Supabase..."):
                    uploaded_xlsx.seek(0)
                    total, inserted = applications_db.ingest_excel(uploaded_xlsx, import_date, uploaded_xlsx.name)
                    skipped = total - inserted
                    st.success(f"🎉 Successfully imported **{inserted}** new applications!")
                    if skipped > 0:
                        st.info(f"ℹ️ Skipped **{skipped}** duplicate application(s) already in database.")
        except Exception as e:
            st.error(f"Error reading Excel file: {e}")

    st.divider()
    with st.expander("⚠️ Danger Zone"):
        st.warning("Deleting all applications will clear the tracking table.")
        confirm = st.checkbox("I confirm I want to permanently delete all tracked applications.")
        if st.button("🔴 Delete ALL Applications", disabled=not confirm):
            applications_db.delete_all()
            st.success("All application records deleted.")
            st.rerun()
